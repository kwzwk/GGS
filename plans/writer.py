"""Ask the model to write one day's exercises for an outline from planner.py.

Plans are written in German first, with the instructions in German too: small
models answer in the language they are prompted in, and drift into English
otherwise. An English version is then made by translating the finished day.
"""

import re

SUBJECT_NAMES = {
    "math": "Mathematik",
    "german": "Deutsch",
    "science": "Sachunterricht",
    "english": "Englisch",
    "other": "Sonstiges",
}

CHOICE = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "text": {"type": "string"}},
    "required": ["title", "text"],
}
WEEKDAY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "recall": {"type": "array", "items": {"type": "string"}},
        "puzzle": {"type": "string"},
        "main_intro": {"type": "string"},
        "choice_a": CHOICE,
        "choice_b": CHOICE,
        "explain": {"type": "string"},
    },
    "required": ["title", "recall", "puzzle", "main_intro", "choice_a", "choice_b", "explain"],
}
FRIDAY_SCHEMA = {
    "type": "object",
    "properties": {"quiz": {"type": "array", "items": {"type": "string"}}},
    "required": ["quiz"],
}
TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {"texts": {"type": "array", "items": {"type": "string"}}},
    "required": ["texts"],
}

RULES = """Du schreibst einen Tag eines ausgedruckten Lernplans für ein Kind an einer Grundschule in Deutschland, Klasse {class_level}.
Ein Elternteil sitzt dabei, das Kind arbeitet auf Papier. Schreibe ALLES auf Deutsch, kindgerecht, an das Kind gerichtet („du“), kurz und freundlich.

Halte dich an diese Lernprinzipien:
- Abrufen: Die Fragen bei „Weißt du noch?“ werden aus dem Gedächtnis beantwortet, ohne nachzuschauen. Keine Noten.
- Verteilen und Mischen: Mische die angegebenen Wiederholungsthemen, nicht nur das heutige Thema.
- Neugier: Das Rätsel fordert das Kind auf, ZUERST ZU RATEN und es dann herauszufinden. Es soll überraschend oder lustig sein und zum Hauptthema passen.
- Erst konkret, dann abstrakt: Nutze echte Gegenstände (Münzen, Socken, Löffel, Finger, Würfel), Bilder oder Malen, wo es passt.
- Selbstbestimmung: Die Hauptaufgabe hat zwei Varianten, A und B, für dieselbe Übung (z. B. mit Bildern oder Gegenständen bzw. mit Zahlen oder Wörtern). Das Kind wählt.
- Selbsterklärung: Bei „Erklär es mir“ erklärt das Kind mit eigenen Worten, WIE oder WARUM.
- Passende Schwierigkeit für Klasse {class_level}: mit etwas Anstrengung lösbar. Orientiere dich an den Beispielen vom Arbeitsblatt, aber schreibe NEUE Aufgaben und kopiere sie nicht.
- Keine Belohnungen, kein Lob fürs Schlau-Sein, keine Lösungen und keine Antworten.
- Jede Aufgabe muss in ihre Minuten passen. Kurze Texte: Ein Kind liest oder hört sie.
{klasse1}"""

KLASSE1 = """- Klasse 1: Das Kind kann noch nicht lesen. Die Eltern lesen alles vor. Antworten werden gesprochen, gezeigt, gemalt, mit Gegenständen gemacht oder nachgespurt. Schreiben nur als Nachspuren einzelner Buchstaben oder Zahlen. Buchstaben zuerst über ihren Laut einführen, Zahlen mit Gegenständen und Würfelbildern."""

REMINDER = "\n\nWICHTIG: Schreibe alle Texte auf Deutsch, nicht auf Englisch."

TRANSLATE = """Translate these texts from a German primary-school study plan (Klasse {class_level}) into simple, child-friendly English.
Keep the meaning, the order, line breaks and blanks like ___. Keep numbers and maths as they are. Do not add answers.
German words that are themselves being practised (spelling, letter sounds, reading words) stay in German.
Return "texts": exactly {count} translated texts in the same order.

{texts}"""


def _topic_text(topic):
    lines = [f"- {SUBJECT_NAMES.get(topic.get('subject'), 'Sonstiges')}: {topic['topic']}"]
    if topic.get("summary"):
        lines.append(f"  Worum es geht: {topic['summary']}")
    if topic.get("examples"):
        lines.append("  Beispiele vom Arbeitsblatt: " + " | ".join(topic["examples"][:6]))
    return "\n".join(lines)


def build_prompt(day, class_level):
    rules = RULES.format(class_level=class_level, klasse1=KLASSE1 if class_level == 1 else "")
    minutes = dict(day["blocks"])
    recall = "\n".join(_topic_text(t) for t in day["recall"]) or (
        "- (noch keine: frage nach dem heutigen Schultag und den Themen der letzten Tage)"
    )
    if day["weekday"] == 4:
        task = f"""Heute ist Freitag: ein gemischtes Quiz der ganzen Woche ({minutes.get('quiz')} Minuten), aus dem Gedächtnis.
Themen zum Mischen (abwechseln, Fächer wechseln):
{recall}

Schreibe "quiz": 5 bis 8 kurze Fragen oder Aufgaben, höchstens eine Zeile pro Frage."""
        return rules + "\n\n" + task + REMINDER, FRIDAY_SCHEMA

    parts = [
        f"Hauptthema heute:\n{_topic_text(day['main'])}",
        f"Themen zum Wiederholen:\n{recall}",
        "Schreibe:",
        '- "title": den Namen des Hauptthemas auf Deutsch, kurz (z. B. „Einmaleins mit 2“).',
    ]
    if "recall" in minutes:
        parts.append(
            f'- "recall": 3 kurze Wiederholungsfragen, die die Wiederholungsthemen mischen '
            f'({minutes["recall"]} Minuten zusammen). Je eine Zeile.'
        )
    parts.append(
        f'- "puzzle": ein Rätsel zum Vorab-Raten, das zum Hauptthema hinführt ({minutes["puzzle"]} Minuten). '
        "Ein oder zwei Sätze."
        if "puzzle" in minutes
        else '- "puzzle": ein leerer Text.'
    )
    parts.append(
        f'- "main_intro": ein oder zwei Sätze, mit denen die Hauptaufgabe beginnt ({minutes["main"]} Minuten).\n'
        '- "choice_a" und "choice_b": die zwei Varianten der Hauptaufgabe, je mit kurzem "title" '
        '(z. B. „Mit Bildern“) und einem "text" mit den konkreten Aufgaben (Zeilenumbrüche zwischen den Aufgaben).'
    )
    parts.append(f'- "explain": eine Frage, bei der das Kind den Eltern etwas erklärt ({minutes["explain"]} Minuten).')
    return rules + "\n\n" + "\n".join(parts) + REMINDER, WEEKDAY_SCHEMA


EN_WORDS = {"the", "and", "you", "your", "with", "what", "how", "is", "are", "of", "to", "can", "this", "it"}
DE_WORDS = {"der", "die", "das", "und", "du", "ist", "mit", "wie", "was", "ein", "eine", "zu", "nicht", "dein", "deine"}


def looks_english(texts):
    words = [w.lower() for t in texts for w in re.findall(r"[A-Za-zÄÖÜäöüß]+", t)]
    english = sum(w in EN_WORDS for w in words)
    german = sum(w in DE_WORDS for w in words)
    return english >= 3 and english > german


def _lines(value, limit):
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:limit]


def _text(value, limit=1200):
    return str(value or "").strip()[:limit]


def parse(day, data):
    """Map the model's answer onto the outline's blocks: (title, [(kind, minutes, content)])."""
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
        raise ValueError(f"Model answer is missing {', '.join(missing)}")
    title = _text(data.get("title"), 120)
    if looks_english([title] + [s for _, _, c in blocks for s in flatten(c)]):
        raise ValueError("Model answered in English instead of German")
    return title, blocks


def flatten(content):
    """All texts of one exercise's content, in a fixed order."""
    texts = []
    if content.get("text"):
        texts.append(content["text"])
    texts += content.get("items", [])
    for choice in content.get("choices", []):
        texts += [choice.get("title", ""), choice.get("text", "")]
    return texts


def unflatten(content, texts):
    """Rebuild a content dict like `content` from translated texts (consumes `texts`)."""
    result = {}
    if content.get("text"):
        result["text"] = texts.pop(0)
    if "items" in content:
        result["items"] = [texts.pop(0) for _ in content["items"]]
    if "choices" in content:
        result["choices"] = [
            {"label": c["label"], "title": texts.pop(0), "text": texts.pop(0)} for c in content["choices"]
        ]
    return result


def build_translation_prompt(texts, class_level):
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    return TRANSLATE.format(class_level=class_level, count=len(texts), texts=numbered), TRANSLATION_SCHEMA


def parse_translation(texts, data):
    translated = data.get("texts") if isinstance(data, dict) else None
    if not isinstance(translated, list) or len(translated) != len(texts):
        raise ValueError("Translation has a different number of texts")
    return [_text(t, 1200) for t in translated]
