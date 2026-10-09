# CLAUDE.md

> This file is the product spec and working guide for the project. Keep it
> current: record new decisions in the decisions log.

## Project

**Name:** Geyen Grundschule (GGS)

**One-line goal:** A web app that Kai self-hosts in a single, simple Docker
container and exposes through an existing reverse proxy.

**Users:** mainly parents of children at the Grundschule (primary school)
in Geyen, Klasse 1–4.

**Core idea:** each week a parent uploads screenshots/photos of the work their
child was assigned at school. The app analyses them (subject, topic, task type,
difficulty) and generates a study / lesson plan for that week, tailored to the
child.

## Core flow (v1)

1. Parent registers and logs in (simple username/email + password form).
   One parent account can have several children, each with a name and
   class level (Klasse 1–4; this is a primary school).
2. Parent picks a child and uploads that week's screenshots of assigned work.
3. The app analyses the images with a vision-capable model served by Ollama.
4. The app generates a weekly study plan for that child from the analysis.
5. Parent views the plan (and past weeks) and **prints it**.
6. The child works on paper; afterwards the parent asks the child how it went
   and enters the ratings in the app.

**Children never use the app.** Only parents (and the admin) log in. Every
child-facing output is designed to be printed.

## Study plan rules

Plans follow the evidence-based principles in
[docs/learning-principles.md](docs/learning-principles.md) (retrieval
practice, spacing, interleaving, self-explanation, autonomy, curiosity) and
the daily session template defined there. Worked examples:
[Klasse 2](docs/example-weekly-plan.md) and
[Klasse 1, first school week](docs/example-weekly-plan-klasse1.md).

- **Mon–Fri schedule**, one learning session per day.
- **Each day's session is at most 20 minutes** in total by default. The
  generator must budget minutes per exercise and never exceed the cap. The
  cap will become adjustable later; store it as a setting rather than
  hard-coding it.
- **Printable:** the plan and its exercises render as a clean, print-friendly
  page (A4, black and white friendly, large readable font for children),
  e.g. one page per day. No answer key in the printout (primary-school
  level; parents can check without one).
- Each day lists **concrete exercises** (subject, topic, what to do,
  estimated minutes).
- **Spaced repetition:** topics come back at growing intervals (e.g. same
  week, then the following weeks) instead of being drilled once. This means
  the app keeps per-child topic history across weeks and mixes due
  repetitions from earlier weeks into the new plan alongside this week's
  topics.
- The 20-minute cap takes priority: if new topics plus due repetitions don't
  fit, the plan prioritises and defers the rest.

## Exercises, ratings and the exercise library

- The app **writes new exercises** with the LLM. Each one keeps a
  **reference to the assigned worksheet(s)** it was derived from (the
  uploaded screenshot and the detected topic).
- **Disclaimer:** every generated exercise is shown with a clear note that it
  was AI-generated and must be checked for accuracy by the parent before the
  child uses it.
- **Validation:** the parent marks an exercise as checked/correct (or flags it
  as wrong). Only validated exercises are trusted.
- **Ratings:** the parent rates each exercise and also records the child's
  rating (asked verbally after the paper session), e.g. easy / ok / hard.
  Ratings feed the spaced-repetition intervals for that child.
- **Exercise library:** validated exercises are stored in a **shared**
  database, available to all families on the instance, tagged by **class
  level (1–4)**, subject and topic. Later plans for any child reuse matching
  library exercises before generating new ones.
- **Admin approval:** a parent-validated exercise is only *submitted* to the
  library. The admin reviews it and approves (or rejects) it before it
  becomes visible to other families. Until then it is usable only by the
  family that created it.
- Library entries must contain **no personal data**: no child names, no
  original screenshots. The link back to a family's worksheet stays private
  to that family.

## Admin role

The admin (Kai) manages the instance from an admin area:

- **Registrations:** new parent accounts start as *pending* and can only log
  in after the admin approves them.
- **Password resets:** there is no self-service reset and no email. A parent
  who forgot their password asks the admin, who sets a temporary password
  that the parent must change at next login.
- **Exercise library:** review queue for submitted exercises; approve,
  reject, edit or remove entries.
- **Data deletion:** uploaded screenshots are kept by default. The admin can
  delete uploads (and other data) later, e.g. per family or older than a
  given date. No automatic deletion in v1.
- **LLM backend settings** (see below).

## LLM backend

- Source is **Ollama** (self-hosted, reached over its HTTP API). Ollama runs
  outside this container; the app only needs its URL.
- An **admin** configures the backend in an admin settings page: Ollama base
  URL and which model(s) to use (e.g. one vision model for reading the
  screenshots, possibly a separate text model for writing the plan). The page
  should list the models Ollama has installed and offer a connection test.
- An env var (e.g. `OLLAMA_URL`) can seed the default on first start; the
  admin setting overrides it.
- **Hardware:** Ollama runs on a **separate PC with an RTX 4070 (12 GB
  VRAM)**, reached over the LAN. Models must fit in 12 GB, so roughly 7–12B
  parameter models at 4-bit quantisation. Sensible starting points: a
  vision model such as `qwen2.5vl:7b` (good at reading text/handwriting) or
  `gemma3:12b` (vision plus good German). Load one model at a time.
- **The GPU PC is not always on.** The app must treat Ollama as
  intermittently available:
  - uploads are always accepted and stored; analysis/plan jobs wait in the
    queue until Ollama is reachable, then run automatically;
  - the parent sees a clear status ("waiting for the analysis server")
    instead of an error;
  - the admin page shows whether Ollama is currently reachable and how many
    jobs are waiting;
  - jobs retry with backoff and survive app restarts.
- **No Wake-on-LAN.** Kai switches the GPU PC on manually; the app only
  waits for it.

## Tech stack

Chosen by Claude (Kai asked for "what makes sense"); change here if needed.

- **Python + Django**, server-rendered templates with **HTMX** for small
  interactive bits. Django gives login/registration, an admin site (useful
  for account approval and the library review queue), translations and
  database migrations out of the box.
- **SQLite** stored in the `/data` volume. No separate database container.
- **Background jobs:** screenshot analysis and plan generation can take
  minutes on Ollama, so they run as jobs in a simple database-backed queue
  processed by a worker inside the same container. The page shows progress
  and the parent can come back later.
- **Ollama** called over its HTTP API with plain `httpx`/`requests`; no
  heavy LLM frameworks.
- **Printing** via print-optimised HTML/CSS (the browser's print/save as
  PDF). Server-side PDF generation only if that proves insufficient.
- **Languages:** German is the default and primary language; English is
  available as a second language (Django i18n). All user-facing text goes
  through translations from the start. Generated plans and exercises are
  written in the parent's chosen language (German by default).
- **Container:** one image, run with `gunicorn` (web) plus the job worker,
  started from a single entrypoint. Uploads and the database live in
  `/data`.
- **Uploads:** images (JPEG, PNG, HEIC from phones) and PDFs. PDF pages are
  converted to images before analysis.
- **Layout:** phone-first responsive design (parents photograph worksheets
  on their phones), works on desktop too.
- **Notifications:** none in v1. Parents check the app for their plan.
- **Accounts:** one parent per account in v1; no shared access to children
  between two parent accounts.
- **Builds:** GitHub Actions builds the image and publishes it to GHCR
  (`ghcr.io/kwzwk/ggs`).
- **Target platform:** `linux/amd64` (Kai's server is a normal x86 machine).
  No ARM build needed.

## Known constraints

- **Self-hosted.** Runs on Kai's own infrastructure, not a managed cloud.
- **One simple Docker container.** `docker run` or a minimal `docker compose`
  file should be enough. Avoid requiring extra services (separate DB server,
  Redis, queues) unless a requirement forces it.
- **Behind a reverse proxy.** The app serves plain HTTP on one configurable
  port; TLS, the public hostname and certificates are handled by the proxy.
  The app must therefore:
  - respect `X-Forwarded-*` headers (scheme, host, client IP),
  - work under a configurable base path if it is not mounted at `/`,
  - expose a health endpoint the proxy or Docker can probe.
- **Configuration via environment variables**, with sensible defaults.
- **Persistent data in one mounted volume** (e.g. `/data`) so backups are a
  single directory copy.

## Open questions

None right now. Add new ones here as they come up.

## Decisions log

| Date | Decision | Why |
|------|----------|-----|
| 2026-10-09 | Single Docker container behind Kai's existing reverse proxy | Stated project goal |
| 2026-10-09 | Primary users are parents | Kai |
| 2026-10-09 | Core feature: weekly upload of assigned-work screenshots, AI analysis, generated weekly study plan per child | Kai |
| 2026-10-09 | Built-in simple login/register form (no external SSO) | Kai |
| 2026-10-09 | AI runs on Ollama; an admin role configures the LLM backend in the app | Kai |
| 2026-10-09 | Plan = Mon–Fri schedule with concrete exercises, max 20 min per day, spaced repetition across weeks | Kai |
| 2026-10-09 | One parent account can have multiple children | Kai |
| 2026-10-09 | App generates new exercises linked to the source worksheets, shown with an accuracy disclaimer | Kai |
| 2026-10-09 | Parent and child both rate exercises; parent-validated exercises are stored in a reusable exercise library | Kai |
| 2026-10-09 | Exercise library is shared across all families, tagged by class level 1–4 | Kai |
| 2026-10-09 | Children never use the app; parents print plans and enter the child's rating | Kai |
| 2026-10-09 | 20 min/day is the default cap; make it adjustable later | Kai |
| 2026-10-09 | Admin approves exercises before they enter the shared library | Kai |
| 2026-10-09 | Registration requires admin approval | Kai |
| 2026-10-09 | Uploads are kept; the admin decides what to delete (no auto-deletion in v1) | Kai |
| 2026-10-09 | UI in German (default) and English | Kai |
| 2026-10-09 | No answer key on printouts | Kai |
| 2026-10-09 | Stack: Django + HTMX + SQLite, background job worker in the same container | Claude, at Kai's request |
| 2026-10-09 | Forgotten passwords are reset by the admin (no email reset) | Kai |
| 2026-10-09 | Server is x86; build images for linux/amd64 only | Kai |
| 2026-10-09 | SQLite in /data; PDFs accepted; phone-first layout; no notifications in v1; one parent per account; GitHub Actions publishes to GHCR | Defaults proposed by Claude, accepted by Kai |
| 2026-10-09 | Plans follow docs/learning-principles.md: retrieval, spacing, interleaving, self-explanation, autonomy and curiosity | Kai asked for science-backed plans |
| 2026-10-09 | No Wake-on-LAN; Kai switches the GPU PC on manually | Kai |
| 2026-10-09 | Ollama runs on a separate PC with an RTX 4070 that is not always on; jobs queue until it is reachable | Kai |

## Working conventions for Claude

- Keep the app runnable with one `docker compose up`.
- Prefer few dependencies and boring, well-supported tech.
- Update this file when a decision is made: move the question out of
  "Open questions" and record it in the decisions log.
