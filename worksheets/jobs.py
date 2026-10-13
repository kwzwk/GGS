import base64
import logging

from django.utils import timezone

from jobs.queue import handler
from llm import client as llm
from llm.models import OllamaSettings

from .models import Page

logger = logging.getLogger(__name__)

SUBJECTS = ["math", "german", "science", "english", "other"]

SCHEMA = {
    "type": "object",
    "properties": {
        "is_worksheet": {"type": "boolean"},
        "subject": {"type": "string", "enum": SUBJECTS},
        "topics": {"type": "array", "items": {"type": "string"}},
        "task_types": {"type": "array", "items": {"type": "string"}},
        "examples": {"type": "array", "items": {"type": "string"}},
        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
        "summary": {"type": "string"},
    },
    "required": ["is_worksheet", "subject", "topics", "task_types", "examples", "difficulty", "summary"],
}

LANGUAGE_NAMES = {"de": "German (Deutsch)", "en": "English"}

PROMPT = """You are helping a parent support their child at a German primary school (Grundschule), Klasse {class_level}.
The image is a photo or scan of work the child was assigned at school this week.

Read it carefully and describe it:
- is_worksheet: false if the image is not school work at all.
- subject: math (Mathematik), german (Deutsch), science (Sachunterricht), english (Englisch) or other.
- topics: 1-3 short topic names as a teacher would say them, e.g. "Einmaleins mit 5", "Wörter mit ie", "Der Igel".
- task_types: what the child has to do, e.g. "fill in the gaps", "calculate", "read and answer", "draw", "trace letters".
- examples: up to 5 typical tasks copied from the sheet, word for word where readable.
- difficulty: for a child in Klasse {class_level}: easy, medium or hard.
- summary: one or two sentences for the parent about what the child practises.

Only describe what you can see; do not invent tasks. Keep examples in the language of the sheet.
IMPORTANT: write topics, task_types and summary in {language}."""


def _normalise(data):
    result = {key: data.get(key) for key in SCHEMA["properties"]}
    if result["subject"] not in SUBJECTS:
        result["subject"] = "other"
    for key in ("topics", "task_types", "examples"):
        value = result[key]
        result[key] = [str(v).strip() for v in value if str(v).strip()][:5] if isinstance(value, list) else []
    if result["difficulty"] not in ("easy", "medium", "hard"):
        result["difficulty"] = "medium"
    result["summary"] = str(result["summary"] or "").strip()
    result["is_worksheet"] = bool(result["is_worksheet"])
    return result


@handler("worksheets.analyse_page")
def analyse_page(page_id):
    page = Page.objects.select_related("upload__week__child").filter(pk=page_id).first()
    if page is None:
        return  # deleted in the meantime
    settings = OllamaSettings.load()
    Page.objects.filter(pk=page.pk).update(status=Page.Status.ANALYSING)
    with page.image.open("rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    prompt = PROMPT.format(
        class_level=page.upload.week.child.class_level,
        language=LANGUAGE_NAMES.get(page.language, "German"),
    )
    try:
        data = llm.get_client(settings).chat(
            settings.vision_model,
            [{"role": "user", "content": prompt, "images": [image_b64]}],
            schema=SCHEMA,
        )
    except llm.OllamaUnavailable:
        llm.record_status(False)
        Page.objects.filter(pk=page.pk).update(status=Page.Status.QUEUED)
        raise
    except Exception as exc:
        if isinstance(exc, llm.OllamaError):
            llm.record_status(True)  # reachable, but the request itself failed
        Page.objects.filter(pk=page.pk).update(status=Page.Status.QUEUED)
        raise
    llm.record_status(True)
    Page.objects.filter(pk=page.pk).update(
        status=Page.Status.DONE,
        analysis=_normalise(data if isinstance(data, dict) else {}),
        error="",
        analysed_at=timezone.now(),
    )


def _analysis_failed(page_id, error):
    Page.objects.filter(pk=page_id).update(status=Page.Status.FAILED, error=str(error)[:2000])


analyse_page.on_failure = _analysis_failed
