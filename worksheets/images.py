"""Turn uploaded photos and PDFs into normalised JPEG pages for the vision model."""

import io

import pypdfium2 as pdfium
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

# Long edge in pixels. Enough to read worksheet text, small enough for a 7–12B
# vision model and a quick upload to the GPU PC.
MAX_EDGE = 1600
MAX_PDF_PAGES = 20
JPEG_QUALITY = 85


class InvalidUpload(ValueError):
    pass


def _to_jpeg(image):
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        background = Image.new("RGB", image.size, "white")
        rgba = image.convert("RGBA")
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    image = image.convert("RGB")
    image.thumbnail((MAX_EDGE, MAX_EDGE))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return ContentFile(out.getvalue(), name="page.jpg")


def is_pdf(data):
    return data[:5] == b"%PDF-"


def pages_from_bytes(data):
    """Return a list of JPEG ContentFiles, one per page."""
    if is_pdf(data):
        try:
            pdf = pdfium.PdfDocument(data)
        except pdfium.PdfiumError as exc:
            raise InvalidUpload("unreadable PDF") from exc
        try:
            if len(pdf) == 0:
                raise InvalidUpload("empty PDF")
            if len(pdf) > MAX_PDF_PAGES:
                raise InvalidUpload("too many pages")
            pages = []
            for page in pdf:
                width, height = page.get_size()
                scale = MAX_EDGE / max(width, height)
                pages.append(_to_jpeg(page.render(scale=scale).to_pil()))
            return pages
        finally:
            pdf.close()
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            return [_to_jpeg(image)]
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidUpload("not an image") from exc
