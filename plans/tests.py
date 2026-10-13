import datetime
import json
import re
import shutil
import tempfile
from unittest import mock

import httpx
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from children.models import Child
from jobs import queue
from jobs.models import Job
from llm import client as llm
from llm.models import OllamaSettings
from worksheets.models import Page, Upload, Week

from . import planner, writer
from .models import Plan

User = get_user_model()
MEDIA = tempfile.mkdtemp()
MONDAY = datetime.date(2026, 10, 12)


def add_page(week, subject, topic, examples=("3 · 5 = __",)):
    upload = Upload.objects.create(week=week, original_name=f"{topic}.jpg")
    upload.file.save("x.jpg", ContentFile(b"x"), save=True)
    page = Page(upload=upload, status=Page.Status.DONE)
    page.image.save("x.jpg", ContentFile(b"x"), save=False)
    page.analysis = {
        "is_worksheet": True,
        "subject": subject,
        "topics": [topic],
        "task_types": [],
        "examples": list(examples),
        "difficulty": "medium",
        "summary": f"Übt {topic}.",
    }
    page.save()
    return page


WEEKDAY_ANSWER = {
    "title": "Einmaleins mit 2",
    "recall": ["4 × 2 = ___", "Was fressen Igel?", "Schreib richtig: die b__ne"],
    "puzzle": "Rate zuerst: Sind 6 Paar Socken mehr als 10 Socken?",
    "main_intro": "Hol Socken und lege sie in Paaren hin.",
    "choice_a": {"title": "Mit Bildern", "text": "Male 1 bis 10 Sockenpaare."},
    "choice_b": {"title": "Mit Zahlen", "text": "Schreibe die 2er-Reihe."},
    "explain": "Warum sind 5 × 2 und 2 × 5 gleich viel?",
}
FRIDAY_ANSWER = {"quiz": ["2 × 6 = ___", "Was fressen Igel?", "Schreib richtig: Biene"]}


def fake_ollama(request):
    body = json.loads(request.content)
    if "texts" in body["format"]["properties"]:
        count = int(re.search(r"exactly (\d+) translated", body["messages"][0]["content"]).group(1))
        texts = ["Times table with 2"] + [f"English text {i}" for i in range(1, count)]
        return httpx.Response(200, json={"message": {"content": json.dumps({"texts": texts})}})
    friday = "quiz" in body["format"]["properties"]
    answer = FRIDAY_ANSWER if friday else WEEKDAY_ANSWER
    return httpx.Response(200, json={"message": {"content": json.dumps(answer)}})


class OutlineTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_user("anna", password="x")
        self.mia = Child.objects.create(parent=self.parent, name="Mia", class_level=2)

    def test_budget_never_exceeds_cap(self):
        for cap in range(5, 46):
            for template in (planner.WEEKDAY_TEMPLATE, planner.FRIDAY_TEMPLATE, planner.WEEKDAY_TEMPLATE_K1):
                blocks = planner.budget(template, cap)
                self.assertLessEqual(sum(m for _, m in blocks), cap)
                self.assertTrue(all(m >= 1 for _, m in blocks))
        self.assertEqual(sum(m for _, m in planner.budget(planner.WEEKDAY_TEMPLATE, 20)), 20)

    @override_settings(MEDIA_ROOT=MEDIA)
    def test_outline_spacing_and_due_topics(self):
        week = Week.objects.create(child=self.mia, week_start=MONDAY)
        add_page(week, "math", "Einmaleins mit 2")
        add_page(week, "german", "Wörter mit ie")
        add_page(week, "math", "Einmaleins mit 2")  # same topic twice
        earlier = Week.objects.create(child=self.mia, week_start=MONDAY - datetime.timedelta(weeks=2))
        add_page(earlier, "german", "Nomen groß schreiben")

        days = planner.build_outline(week, 20)
        self.assertEqual([d["weekday"] for d in days], [0, 1, 2, 3, 4])
        self.assertEqual(
            [d["main"]["topic"] for d in days[:4]],
            ["Einmaleins mit 2", "Wörter mit ie", "Einmaleins mit 2", "Wörter mit ie"],
        )
        self.assertEqual(len(days[0]["main"]["page_ids"]), 2)
        # Monday recalls the due topic from two weeks ago; Tuesday recalls Monday.
        self.assertEqual([t["topic"] for t in days[0]["recall"]], ["Nomen groß schreiben"])
        self.assertEqual(days[1]["recall"][0]["topic"], "Einmaleins mit 2")
        quiz = [t["topic"] for t in days[4]["recall"]]
        self.assertIn("Nomen groß schreiben", quiz)
        self.assertIsNone(days[4]["main"])

    @override_settings(MEDIA_ROOT=MEDIA)
    def test_klasse1_and_lower_cap(self):
        self.mia.class_level = 1
        self.mia.daily_minutes = 12
        self.mia.save()
        week = Week.objects.create(child=self.mia, week_start=MONDAY)
        add_page(week, "german", "Anlaut M")
        days = planner.build_outline(week, self.mia.daily_minutes)
        for day in days:
            self.assertLessEqual(sum(m for _, m in day["blocks"]), 12)


@override_settings(MEDIA_ROOT=MEDIA)
class PlanFlowTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.anna = User.objects.create_user("anna", password="x")
        self.mia = Child.objects.create(parent=self.anna, name="Mia", class_level=2)
        self.week = Week.objects.create(child=self.mia, week_start=MONDAY)
        self.page = add_page(self.week, "math", "Einmaleins mit 2")
        add_page(self.week, "science", "Der Igel")
        self.client.force_login(self.anna)
        self.base = f"/children/{self.mia.pk}/plans/2026-10-12/"
        OllamaSettings.objects.update_or_create(pk=1, defaults={"base_url": "http://gpu:11434"})

    def run_jobs(self, handle):
        real = llm.get_client

        def fake(settings=None):
            c = real(settings)
            c.transport = httpx.MockTransport(handle)
            return c

        with mock.patch.object(llm, "get_client", fake):
            results = []
            while (job := queue.claim_next()) is not None:
                results.append(queue.run(job))
                if not results[-1]:
                    break
            return results

    def test_create_write_and_print(self):
        week_page = self.client.get(f"/children/{self.mia.pk}/worksheets/week/2026-10-12/")
        self.assertContains(week_page, "Lernplan erstellen")

        response = self.client.post(self.base + "create/")
        self.assertRedirects(response, self.base)
        plan = Plan.objects.get()
        self.assertEqual(plan.days.count(), 5)
        self.assertContains(self.client.get(self.base), "wird geschrieben")

        self.assertEqual(self.run_jobs(fake_ollama), [True])
        plan.refresh_from_db()
        self.assertEqual(plan.status, Plan.Status.DONE)
        for day in plan.days.all():
            self.assertLessEqual(day.total_minutes, 20)
        monday = plan.days.get(weekday=0)
        main = monday.exercises.get(kind="main")
        self.assertEqual(list(main.source_pages.all()), [self.page])
        self.assertEqual(len(main.content["choices"]), 2)

        detail = self.client.get(self.base)
        self.assertContains(detail, "von einer KI erstellt")
        self.assertContains(detail, "Mit Bildern")
        self.assertContains(detail, "Einmaleins mit 2.jpg")  # link back to the worksheet

        printed = self.client.get(self.base + "print/")
        self.assertContains(printed, "Montag · Einmaleins mit 2")
        self.assertContains(printed, "Freitag")
        self.assertContains(printed, "von einer KI erstellt")
        self.assertNotContains(printed, "Einmaleins mit 2.jpg")  # no sources on paper

    def test_plan_is_german_with_an_english_version(self):
        self.client.post(self.base + "create/")
        self.assertEqual(self.run_jobs(fake_ollama), [True])
        plan = Plan.objects.get()
        self.assertEqual(plan.language, "de")
        monday = plan.days.get(weekday=0)
        self.assertEqual(monday.title, "Einmaleins mit 2")
        self.assertEqual(monday.title_translations["en"], "Times table with 2")
        main = monday.exercises.get(kind="main")
        self.assertEqual(main.content["choices"][0]["title"], "Mit Bildern")
        self.assertEqual([c["label"] for c in main.translations["en"]["choices"]], ["A", "B"])
        self.assertTrue(all(d.translated for d in plan.days.all()))

        german = self.client.get(self.base)
        self.assertContains(german, "Mit Bildern")
        self.assertContains(german, '<a href="?lang=en" lang="en">English</a>', html=True)
        english = self.client.get(self.base + "?lang=en")
        self.assertContains(english, "Monday · Times table with 2")
        self.assertContains(english, "Main task")
        self.assertNotContains(english, "Mit Bildern")
        self.assertContains(english, "print/?lang=en")
        printed = self.client.get(self.base + "print/?lang=en")
        self.assertContains(printed, '<html lang="en">')
        self.assertContains(printed, "Monday · Times table with 2")
        self.assertContains(self.client.get(self.base + "print/"), "Montag · Einmaleins mit 2")

    def test_english_answer_is_rejected(self):
        english = {
            "title": "Times table with 2",
            "recall": ["What is 4 × 2?", "What do hedgehogs eat?", "Spell the word bee"],
            "puzzle": "Guess first: are 6 pairs of socks more than 10 socks?",
            "main_intro": "Get your socks and put them in pairs.",
            "choice_a": {"title": "With pictures", "text": "Draw 1 to 10 pairs of socks."},
            "choice_b": {"title": "With numbers", "text": "Write the 2 times table."},
            "explain": "Why are 5 × 2 and 2 × 5 the same?",
        }
        with self.assertRaisesMessage(ValueError, "English"):
            writer.parse(planner.build_outline(self.week, 20)[0], english)

    def test_waits_while_server_is_off_and_keeps_written_days(self):
        self.client.post(self.base + "create/")
        calls = []

        def flaky(request):
            calls.append(1)
            if len(calls) > 2:
                raise httpx.ConnectError("PC switched off")
            return fake_ollama(request)

        self.assertEqual(self.run_jobs(flaky), [False])
        plan = Plan.objects.get()
        self.assertEqual(plan.status, Plan.Status.QUEUED)
        self.assertEqual(plan.days.filter(written=True).count(), 2)
        self.assertContains(self.client.get(self.base), "Warten auf den Analyse-Server")

        calls.clear()
        self.assertEqual(self.run_jobs(fake_ollama), [True])
        plan.refresh_from_db()
        self.assertEqual(plan.status, Plan.Status.DONE)

    def test_bad_model_answer_is_retried_then_fails(self):
        self.client.post(self.base + "create/")
        bad = lambda r: httpx.Response(200, json={"message": {"content": "{}"}})  # noqa: E731
        self.run_jobs(bad)
        job = Job.objects.get()
        self.assertEqual(job.attempts, 1)
        self.assertEqual(Plan.objects.get().status, Plan.Status.QUEUED)

    def test_other_parents_cannot_see_or_create(self):
        self.client.post(self.base + "create/")
        ben = User.objects.create_user("ben", password="x")
        self.client.force_login(ben)
        self.assertEqual(self.client.get(self.base).status_code, 404)
        self.assertEqual(self.client.get(self.base + "print/").status_code, 404)
        self.assertEqual(self.client.post(self.base + "create/").status_code, 404)

    def test_no_plan_while_pages_are_pending(self):
        Page.objects.filter(pk=self.page.pk).update(status=Page.Status.QUEUED)
        self.client.post(self.base + "create/")
        self.assertFalse(Plan.objects.exists())
