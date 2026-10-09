# CLAUDE.md

> **Status: draft.** This file captures what we know about the project so far and
> the open questions still to answer. Sections marked _TBD_ are filled in as
> decisions are made.

## Project

**Name:** Geyen Grund Schule (GGS)

**One-line goal:** A web app that Kai self-hosts in a single, simple Docker
container and exposes through an existing reverse proxy.

**Purpose / audience:** _TBD_ (assumed: something for the Grundschule Geyen, a
primary school; needs confirming).

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

### What it does
1. Who uses it: parents, teachers, pupils, the school office, or just Kai?
2. What are the 2–3 things a user must be able to do on day one?
3. Is the content public, private, or mixed?

### Users and access
4. Does it need logins? If so: a few known accounts, self-registration, or
   single sign-on via an existing identity provider (e.g. Authentik, Authelia,
   Keycloak behind the proxy)?
5. Are there roles (e.g. admin vs. regular user)?

### Data
6. What data is stored, and is any of it personal data about children or
   parents? (GDPR/DSGVO matters a lot for a school context.)
7. Are file uploads needed (images, PDFs)?
8. Is SQLite in the volume acceptable, or must it use an existing database?

### Interface
9. Language(s): German only, or German and English?
10. Mainly used on phones, desktops, or both?
11. Any notifications needed (email, push)?

### Tech and operations
12. Any preferred language or framework, or a stack you want to avoid?
13. Where will images be built: locally, or by GitHub Actions publishing to a
    registry (e.g. GHCR)?
14. Target architecture: amd64, arm64 (e.g. Raspberry Pi), or both?

## Decisions log

| Date | Decision | Why |
|------|----------|-----|
| 2026-10-09 | Single Docker container behind Kai's existing reverse proxy | Stated project goal |

## Working conventions for Claude

- Keep the app runnable with one `docker compose up`.
- Prefer few dependencies and boring, well-supported tech.
- Update this file when a decision is made: move the question out of
  "Open questions" and record it in the decisions log.
