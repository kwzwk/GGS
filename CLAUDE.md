# CLAUDE.md

> **Status: draft.** This file captures what we know about the project so far and
> the open questions still to answer. Sections marked _TBD_ are filled in as
> decisions are made.

## Project

**Name:** Geyen Grund Schule (GGS)

**One-line goal:** A web app that Kai self-hosts in a single, simple Docker
container and exposes through an existing reverse proxy.

**Users:** mainly parents of primary-school children (assumed: Grundschule
Geyen; to confirm).

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

- **Mon–Fri schedule**, one learning session per day.
- **Each day's session is at most 20 minutes** in total by default. The
  generator must budget minutes per exercise and never exceed the cap. The
  cap will become adjustable later; store it as a setting rather than
  hard-coding it.
- **Printable:** the plan and its exercises render as a clean, print-friendly
  page (A4, black and white friendly, large readable font for children),
  e.g. one page per day.
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
- Library entries must contain **no personal data**: no child names, no
  original screenshots. The link back to a family's worksheet stays private
  to that family.

## LLM backend

- Source is **Ollama** (self-hosted, reached over its HTTP API). Ollama runs
  outside this container; the app only needs its URL.
- An **admin** configures the backend in an admin settings page: Ollama base
  URL and which model(s) to use (e.g. one vision model for reading the
  screenshots, possibly a separate text model for writing the plan). The page
  should list the models Ollama has installed and offer a connection test.
- An env var (e.g. `OLLAMA_URL`) can seed the default on first start; the
  admin setting overrides it.

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

### Analysis and plans
1. Which Ollama models are you running or planning to run (e.g. a vision
   model such as Qwen2.5-VL, Llama 3.2 Vision or Gemma 3), and on what
   hardware (GPU)? Small models may struggle with handwriting.
2. Does a validated exercise go straight into the shared library, or does
   the admin approve it first? Can the admin edit or remove entries?
3. Should the printout include an answer key (on a separate page for the
   parent)?

### Users and access
4. Should two parents be able to share access to the same children?
5. Is registration open to anyone, or invite-only / admin-approved?
6. Besides the LLM settings, what else should the admin manage (approving
   registrations, resetting passwords, deleting accounts)?

### Data
7. Screenshots of children's work are personal data (GDPR/DSGVO). How long
   should uploads be kept: deleted after analysis, after the week, or kept?
8. Is SQLite in the volume acceptable, or must it use an existing database?
9. Should PDFs be accepted as well as images?

### Interface
10. Language(s): German only, or German and English?
11. Mainly used on phones (likely, for taking photos), desktops, or both?
12. Any notifications needed (e.g. "your plan is ready", weekly upload
    reminder)?

### Tech and operations
13. Any preferred language or framework, or a stack you want to avoid?
14. Where will images be built: locally, or by GitHub Actions publishing to a
    registry (e.g. GHCR)?
15. Target architecture: amd64, arm64 (e.g. Raspberry Pi), or both?

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

## Working conventions for Claude

- Keep the app runnable with one `docker compose up`.
- Prefer few dependencies and boring, well-supported tech.
- Update this file when a decision is made: move the question out of
  "Open questions" and record it in the decisions log.
