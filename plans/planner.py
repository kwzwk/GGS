"""Turn a week's analysed worksheets into a Mon–Fri outline.

The outline is decided in code, not by the model: which topic is the main task
on which day, which topics come back for recall (spacing, interleaving) and how
many minutes each block gets (never more than the child's cap). The model only
writes the content of each block. See docs/learning-principles.md.
"""

import datetime

# Session template from docs/learning-principles.md: (kind, minutes).
WEEKDAY_TEMPLATE = [("recall", 3), ("puzzle", 2), ("main", 10), ("explain", 3), ("reflect", 2)]
FRIDAY_TEMPLATE = [("quiz", 8), ("research", 8), ("review", 4)]
# Klasse 1: shorter blocks around a 5–7 minute main task, 15 minutes a day.
WEEKDAY_TEMPLATE_K1 = [("recall", 2), ("puzzle", 2), ("main", 7), ("explain", 2), ("reflect", 2)]
FRIDAY_TEMPLATE_K1 = [("quiz", 6), ("research", 6), ("review", 3)]

# Earlier weeks whose topics are due again (spacing: next week, 2 weeks, 4 weeks).
# Ratings will adjust this per topic once they exist.
REVIEW_WEEKS_AGO = (1, 2, 4)
MAIN_KIND = {"main", "quiz"}


def budget(template, cap):
    """Scale a template to the cap. The main block takes what is left; never exceeds cap."""
    full = sum(m for _, m in template)
    total = min(cap, full)
    if total == full:
        return list(template)
    main_kind = next(k for k, _ in template if k in MAIN_KIND)
    blocks = [(k, max(1, round(m * total / full))) for k, m in template]
    others = sum(m for k, m in blocks if k != main_kind)
    main = total - others
    if main < 3:
        # Too little time: drop the puzzle / research first, then shrink the rest to 1 minute.
        blocks = [(k, m) for k, m in blocks if k not in ("puzzle", "research")]
        blocks = [(k, 1 if k != main_kind else m) for k, m in blocks]
        others = sum(m for k, m in blocks if k != main_kind)
        main = max(1, total - others)
    return [(k, main if k == main_kind else m) for k, m in blocks]


def topics_of_week(week):
    """Distinct topics from the week's analysed worksheets, in upload order."""
    topics = {}
    for page in week.pages():
        data = page.analysis or {}
        if page.status != "done" or not data.get("is_worksheet") or not data.get("topics"):
            continue
        name = data["topics"][0].strip()
        key = (data.get("subject", "other"), name.lower())
        entry = topics.setdefault(
            key,
            {
                "subject": data.get("subject", "other"),
                "topic": name,
                "summary": data.get("summary", ""),
                "examples": [],
                "task_types": [],
                "difficulty": data.get("difficulty", "medium"),
                "page_ids": [],
            },
        )
        entry["page_ids"].append(page.pk)
        for field in ("examples", "task_types"):
            for value in data.get(field, []):
                if value not in entry[field]:
                    entry[field].append(value)
        entry["examples"] = entry["examples"][:8]
    return list(topics.values())


def due_topics(week):
    """Topics from earlier weeks that are due for repetition this week."""
    due = []
    child = week.child
    for weeks_ago in REVIEW_WEEKS_AGO:
        start = week.week_start - datetime.timedelta(weeks=weeks_ago)
        earlier = child.weeks.filter(week_start=start).first()
        if earlier:
            for topic in topics_of_week(earlier):
                topic["weeks_ago"] = weeks_ago
                due.append(topic)
    return due


def _short(topic):
    return {k: topic[k] for k in ("subject", "topic", "summary", "examples", "page_ids") if k in topic}


def build_outline(week, cap):
    """Return five day outlines: {"weekday", "main", "recall", "blocks"}."""
    klasse1 = week.child.class_level == 1
    weekday_blocks = budget(WEEKDAY_TEMPLATE_K1 if klasse1 else WEEKDAY_TEMPLATE, cap)
    friday_blocks = budget(FRIDAY_TEMPLATE_K1 if klasse1 else FRIDAY_TEMPLATE, cap)

    new = topics_of_week(week)
    due = due_topics(week)
    # With no new worksheets, the due repetitions become the main topics.
    mains = new or due
    if not mains:
        return []

    days = []
    practised = []
    for weekday in range(4):
        main = mains[weekday % len(mains)]
        # Recall: the previous days of this week first (next-day spacing), then
        # due topics from earlier weeks, mixing subjects (interleaving).
        recall = [t for t in reversed(practised) if t["topic"] != main["topic"]][:2]
        recall += [t for t in due if t not in recall and t["topic"] != main["topic"]][: 3 - len(recall)]
        days.append(
            {
                "weekday": weekday,
                "main": _short(main),
                "recall": [_short(t) for t in recall],
                "blocks": weekday_blocks,
            }
        )
        if main not in practised:
            practised.append(main)

    # New topics that didn't get a main slot (more than four) still come back in
    # Friday's quiz, together with the week's topics and the due repetitions.
    quiz_topics = practised + [t for t in new if t not in practised] + [t for t in due if t not in practised]
    days.append(
        {
            "weekday": 4,
            "main": None,
            "recall": [_short(t) for t in quiz_topics[:6]],
            "blocks": friday_blocks,
        }
    )
    return days
