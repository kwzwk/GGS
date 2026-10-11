import io
import json
import os
import shutil
import tempfile
from unittest import mock

import httpx
import pypdfium2 as pdfium
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from children.models import Child
from jobs import queue
from jobs.models import Job
from llm import client as llm
from llm.models import OllamaSettings

from .images import MAX_EDGE, InvalidUpload, pages_from_bytes
from .models import Page, Upload, Week

User = get_user_model()
MEDIA = tempfile.mkdtemp()


def png_bytes(size=(2400, 1200), color="white"):
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return out.getvalue()


def pdf_bytes(pages=2):
    pdf = pdfium.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(595, 842)
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


class ImageTests(TestCase):
    def test_photo_is_scaled_to_jpeg(self):
        [page] = pages_from_bytes(png_bytes())
        image = Image.open(page)
        self.assertEqual(image.format, "JPEG")
        self.assertEqual(max(image.size), MAX_EDGE)

    def test_pdf_pages(self):
        pages = pages_from_bytes(pdf_bytes(3))
        self.assertEqual(len(pages), 3)
        self.assertEqual(max(Image.open(pages[0]).size), MAX_EDGE)

    def test_heic_from_iphone(self):
        out = io.BytesIO()
        Image.new("RGB", (800, 600), "red").save(out, "HEIF")
        [page] = pages_from_bytes(out.getvalue())
        self.assertEqual(Image.open(page).size, (800, 600))

    def test_garbage_is_rejected(self):
        with self.assertRaises(InvalidUpload):
            pages_from_bytes(b"hello")


@override_settings(MEDIA_ROOT=MEDIA)
class UploadTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.anna = User.objects.create_user("anna", password="x")
        self.mia = Child.objects.create(parent=self.anna, name="Mia", class_level=2)
        self.client.force_login(self.anna)
        self.base = f"/children/{self.mia.pk}/worksheets/"

    def upload(self, *files, week="2026-10-14", follow=False):
        return self.client.post(self.base + "upload/", {"week": week, "files": list(files)}, follow=follow)

    def test_upload_photo_and_pdf(self):
        response = self.upload(
            SimpleUploadedFile("a.png", png_bytes(), "image/png"),
            SimpleUploadedFile("b.pdf", pdf_bytes(2), "application/pdf"),
        )
        week = Week.objects.get()
        self.assertEqual(week.week_start.isoformat(), "2026-10-12")  # normalised to Monday
        self.assertRedirects(response, self.base + "week/2026-10-12/")
        self.assertEqual(Upload.objects.count(), 2)
        self.assertEqual(Page.objects.count(), 3)
        self.assertEqual(Job.objects.filter(kind="worksheets.analyse_page").count(), 3)

        detail = self.client.get(self.base + "week/2026-10-12/")
        self.assertContains(detail, "Warten auf Analyse")
        page = Page.objects.first()
        image = self.client.get(self.base + f"pages/{page.pk}/image/")
        self.assertEqual(image["Content-Type"], "image/jpeg")

    def test_unreadable_file_is_reported(self):
        response = self.upload(SimpleUploadedFile("x.png", b"nope", "image/png"), follow=True)
        self.assertEqual(Page.objects.count(), 0)
        self.assertContains(response, "x.png")

    def test_other_parents_cannot_see_or_upload(self):
        self.upload(SimpleUploadedFile("a.png", png_bytes(), "image/png"))
        page = Page.objects.get()
        ben = User.objects.create_user("ben", password="x")
        self.client.force_login(ben)
        self.assertEqual(self.client.get(self.base).status_code, 404)
        self.assertEqual(self.client.get(self.base + "week/2026-10-12/").status_code, 404)
        self.assertEqual(self.client.get(self.base + f"pages/{page.pk}/image/").status_code, 404)
        self.assertEqual(self.client.post(self.base + f"pages/{page.pk}/delete/").status_code, 404)
        tom = Child.objects.create(parent=ben, name="Tom", class_level=1)
        # Ben's own child in the URL doesn't open Anna's page either.
        url = f"/children/{tom.pk}/worksheets/pages/{page.pk}/image/"
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_delete_page_removes_files(self):
        self.upload(SimpleUploadedFile("a.png", png_bytes(), "image/png"))
        page = Page.objects.get()
        image_path, original_path = page.image.path, page.upload.file.path
        self.client.post(self.base + f"pages/{page.pk}/delete/")
        self.assertFalse(Upload.objects.exists())
        self.assertFalse(os.path.exists(image_path))
        self.assertFalse(os.path.exists(original_path))

    def _run_analysis(self, handle):
        OllamaSettings.objects.update_or_create(pk=1, defaults={"base_url": "http://gpu:11434"})
        real = llm.get_client

        def fake(settings=None):
            c = real(settings)
            c.transport = httpx.MockTransport(handle)
            return c

        with mock.patch.object(llm, "get_client", fake):
            job = queue.claim_next()
            return queue.run(job)

    def test_analysis_success(self):
        self.upload(SimpleUploadedFile("a.png", png_bytes(), "image/png"))
        answer = {
            "is_worksheet": True,
            "subject": "math",
            "topics": ["Einmaleins mit 5"],
            "task_types": ["rechnen"],
            "examples": ["3 · 5 = __"],
            "difficulty": "medium",
            "summary": "Mia übt die 5er-Reihe.",
        }

        def handle(request):
            self.assertIn("Klasse 2", request.content.decode())
            return httpx.Response(200, json={"message": {"content": json.dumps(answer)}})

        self.assertTrue(self._run_analysis(handle))
        page = Page.objects.get()
        self.assertEqual(page.status, Page.Status.DONE)
        self.assertEqual(page.analysis["topics"], ["Einmaleins mit 5"])
        detail = self.client.get(self.base + "week/2026-10-12/")
        self.assertContains(detail, "Mathe")
        self.assertContains(detail, "Einmaleins mit 5")

    def test_analysis_waits_while_server_is_off(self):
        self.upload(SimpleUploadedFile("a.png", png_bytes(), "image/png"))

        def handle(request):
            raise httpx.ConnectError("no route to host")

        self.assertFalse(self._run_analysis(handle))
        page = Page.objects.get()
        self.assertEqual(page.status, Page.Status.QUEUED)
        self.assertEqual(Job.objects.get().attempts, 0)
        detail = self.client.get(self.base + "week/2026-10-12/")
        self.assertContains(detail, "Warten auf den Analyse-Server")
