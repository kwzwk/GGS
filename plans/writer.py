"""Ask the model to write one day's exercises for an outline from planner.py."""

import json

LANGUAGE_NAMES = {"de": "German (Deutsch)", "en": "English"}
SUBJECT_NAMES = {
    "math": "maths",
    "german": "German (Deutsch)",
    "science": "general studies (Sachunterricht)",
    "english": "English",
    "other": "other",
}

CHOICE = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "text": {"type": "string"}},
    "required": ["title", "text"],
}
WEEKDAY_SCHEMA = {
    "type": "object",
    "properties": {
        "recall": {"type": "array", "items": {"type": "string"}},
        "puzzle": {"type": "string"},
        "main_intro": {"type": "string"},
        "choice_a": CHOICE,
        "choice_b": CHOICE,
        "explain": {"type": "string"},
    },
    "required": ["recall", "puzzle", "main_intro", "choice_a", "choice_b", "explain"],
}
FRIDAY_SCHEMA = {
    "type": "object",
    "properties": {"quiz": {"type": "array", "items": {"type": "string"}}},
    "required": ["quiz"],
}

RULES = """You write one day of a printed study plan for a child at a German primary school (Grundschule), Klasse {class_level}.
The parent sits with the child; the child works on paper. Write everything in {language}, addressed to the child ("du"), short and friendly.

Follow these learning principles:
- Retrieval: recall questions are answered from memory, without looking. Low stakes, no grades.
- Spacing and interleaving: mix the recall topics given, do not only repeat today's topic.
- Curiosity: the puzzle asks the child to GUESS FIRST, then find out. It should be surprising or funny and connected to the main topic.
- Concrete before abstract: use real objects (coins, socks, spoons, fingers, dice), pictures or drawing where it fits.
- Autonomy: the main task offers two versions, A and B, of the same practice (e.g. with pictures/objects vs. with numbers/words). The child picks one.
- Self-explanation: the explain prompt asks the child to explain HOW or WHY in their own words, to the parent.
- Right difficulty for Klasse {class_level}: solvable with some effort. Base the tasks on the worksheet examples, but write NEW tasks, do not copy them.
- No rewards, no praise for being clever, no answer key and no solutions anywhere.
- Each task must fit its minutes. Keep texts short: a child reads (or hears) them.
{klasse1}"""

KLASSE1 = """- Klasse 1: the child cannot read yet. The parent reads everything aloud. Answers are spoken, shown, drawn, done with objects, or traced. Writing only as tracing single letters or numbers. Introduce letters by their sound first, numbers with objects and dice patterns."""


def _topic_text(topic):
    lines = [f"- {SUBJECT_NAMES.get(topic.get('subject'), 'other')}: {topic['topic']}"]
    if topic.get("summary"):
        lines.append(f"  About: {topic['summary']}")
    if topic.get("examples"):
        lines.append("  Examples from the worksheet: " + " | ".join(topic["examples"][:6]))
    return "\n".join(lines)


def _reminder(language):
    # Small models drift into English; repeat the language at the end, where it sticks.
    return f"\n\nIMPORTANT: write every text value in {LANGUAGE_NAMES.get(language, 'German')}."


def build_prompt(day, class_level, language):
    rules = RULES.format(
        class_level=class_level,
        language=LANGUAGE_NAMES.get(language, "German"),
        klasse1=KLASSE1 if class_level == 1 else "",
    )
    minutes = dict(day["blocks"])
    recall = "\n".join(_topic_text(t) for t in day["recall"]) or "- (none yet: ask about today's school day and the main topic of the last days)"
    if day["weekday"] == 4:
        task = f"""Today is Friday: a mixed quiz of the whole week ({minutes.get('quiz')} minutes), answered from memory.
Topics to mix (interleave them, alternate subjects):
{recall}

Write "quiz": 5 to 8 short questions or tasks, at most one line each."""
        return rules + "\n\n" + task + _reminder(language), FRIDAY_SCHEMA

    parts = [f"Main topic today:\n{_topic_text(day['main'])}", f"Topics for recall:\n{recall}", "Write:"]
    if "recall" in minutes:
        parts.append(f'- "recall": 3 short recall questions mixing the recall topics ({minutes["recall"]} minutes in total). One line each.')
    parts.append(
        f'- "puzzle": a guess-first puzzle leading into the main topic ({minutes.get("puzzle", 0)} minutes). One or two sentences.'
        if "puzzle" in minutes
        else '- "puzzle": an empty string.'
    )
    parts.append(
        f'- "main_intro": one or two sentences that start the main task ({minutes["main"]} minutes).\n'
        '- "choice_a" and "choice_b": the two versions of the main task, each with a short "title" '
        '(e.g. "Mit Bildern") and a "text" with the concrete tasks (use line breaks between tasks).'
    )
    parts.append(f'- "explain": one question for the child to explain to the parent ({minutes["explain"]} minutes).')
    return rules + "\n\n" + "\n\n".join(parts) + _reminder(language), WEEKDAY_SCHEMA


def _lines(value, limit):
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:limit]


def _text(value, limit=1200):
    return str(value or "").strip()[:limit]


def parse(day, data):
    """Map the model's answer onto the outline's blocks: [(kind, minutes, content)]."""
    if not isinstance(data, dict):
        data = {}
    blocks = []
    for kind, minutes in day["blocks"]:
        if kind == "recall":
            content = {"items": _lines(data.get("recall"), 4)}
        elif kind == "puzzle":
            content = {"text": _text(data.get("puzzle"), 500)}
        elif kind == "main":
            choices = []
            for label, key in (("A", "choice_a"), ("B", "choice_b")):
                choice = data.get(key) if isinstance(data.get(key), dict) else {}
                if _text(choice.get("text")):
                    choices.append({"label": label, "title": _text(choice.get("title"), 80), "text": _text(choice.get("text"))})
            content = {"text": _text(data.get("main_intro"), 600), "choices": choices}
        elif kind == "explain":
            content = {"text": _text(data.get("explain"), 400)}
        elif kind == "quiz":
            content = {"items": _lines(data.get("quiz"), 8)}
        else:  # reflect, research, review: fixed texts in the template
            content = {}
        blocks.append((kind, minutes, content))
    missing = [k for k, _, c in blocks if k in ("main", "quiz") and not (c.get("choices") or c.get("items"))]
    if missing:
        raise ValueError(f"Model answer is missing {', '.join(missing)}: {json.dumps(data)[:300]}")
    return blocks
