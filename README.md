# Geyen Grundschule · Lernpläne

A self-hosted web app for parents of primary-school children: upload the
week's worksheets, get a short, printable study plan for every school day.
See [CLAUDE.md](CLAUDE.md) for the full spec.

> Status: in development. Accounts, children and worksheet uploads with AI
> analysis work; study plans are being built.

## Run it

```sh
docker compose up -d
```

The app listens on port 8000 and keeps everything (database, uploads,
generated secret key) in `./data`. Back up that folder to back up the app.

Point your reverse proxy at `http://<server>:8000`. It must pass the
`Host` and `X-Forwarded-Proto` headers (most proxies do by default).

**Upload size:** phone photos are several MB and parents upload several at
once. Raise the proxy's request size limit for this site, e.g. nginx
`client_max_body_size 100m;` (the nginx default of 1 MB rejects most
photos). Each file may be up to 25 MB, at most 20 files per upload.

## First start and accounts

Set `GGS_ADMIN_USERNAME` and `GGS_ADMIN_PASSWORD` for the first start: the
app creates that admin account if no admin exists yet (later changes to the
variables are ignored). Alternatively run
`docker compose exec ggs python manage.py createsuperuser`.

- Parents register at `/accounts/register/`. New accounts are **pending**
  until you approve them: open **Verwaltung → Benutzer** (`/admin/`), filter
  by *Aktiv: Nein*, select the accounts and run **Ausgewählte Konten
  freigeben**.
- **Forgotten password:** select the account and run **Passwort
  zurücksetzen**. The admin page shows a temporary password to pass on;
  the parent must choose a new one after logging in.
- **Ausgewählte Konten sperren** blocks an account again.

## AI server (Ollama)

Worksheets are read by a vision model running in [Ollama](https://ollama.com)
on another PC. Set it up there:

```sh
ollama pull qwen2.5vl:7b        # or gemma3:12b
# make Ollama listen on the LAN, not only on localhost:
OLLAMA_HOST=0.0.0.0 ollama serve
```

Then open **Verwaltung → KI-Server-Einstellungen** (`/admin/llm/`) and
enter the address, e.g. `http://192.168.1.50:11434`. The page shows
whether Ollama is reachable, which models are installed and how many jobs
are waiting.

The PC does not need to be on all the time. Uploads are always accepted;
the analysis waits until Ollama is reachable and then runs automatically.
Parents see "waiting for the analysis server" in the meantime. Failed jobs
can be retried under **Verwaltung → Hintergrundaufgaben**.

## Automatic builds and updates

1. Every push to `main` runs `.github/workflows/ci.yml`: tests, then a new
   image is built and published as `ghcr.io/kwzwk/ggs:latest`.
2. The compose file includes **Watchtower**, which checks for a new
   `latest` image every 5 minutes, pulls it and restarts the app (data in
   `./data` is kept). It only updates containers with the
   `com.centurylinklabs.watchtower.enable` label, so your other containers
   are left alone.

GHCR packages start out private. Either make the package public (GitHub →
your profile → Packages → `ggs` → Package settings → Change visibility),
or run `docker login ghcr.io` on the server with a token that has
`read:packages` and uncomment the `config.json` line in the compose file so
Watchtower can pull too.

To build the image yourself instead: `docker build -t ghcr.io/kwzwk/ggs:latest .`

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `GGS_ALLOWED_HOSTS` | `*` | Comma-separated hostnames the app answers to, e.g. `lernplan.example.org`. |
| `GGS_BASE_PATH` | *(empty)* | Sub-path when not served at `/`, e.g. `/lernplan`. Works whether or not the proxy strips it. |
| `GGS_HTTPS_ONLY` | `true` | Cookies only over HTTPS. Set `false` to use the app over plain http (e.g. directly on the LAN). |
| `GGS_CSRF_TRUSTED_ORIGINS` | *(empty)* | Extra origins allowed to submit forms, e.g. `https://lernplan.example.org`. Usually not needed. |
| `GGS_ADMIN_USERNAME` / `GGS_ADMIN_PASSWORD` | *(empty)* | Creates the first admin account on start if none exists. |
| `GGS_OLLAMA_URL` | *(empty)* | Ollama address used on first start, e.g. `http://192.168.1.50:11434`. The admin setting overrides it. |
| `GGS_OLLAMA_VISION_MODEL` | `qwen2.5vl:7b` | Initial model for reading worksheets. |
| `GGS_OLLAMA_TEXT_MODEL` | *(empty)* | Initial model for writing plans; empty means the vision model. |
| `GGS_SECRET_KEY` | generated | Generated once and stored in `/data/secret_key` if unset. |
| `GGS_PORT` | `8000` | Port inside the container. |
| `GGS_WEB_WORKERS` | `2` | Gunicorn worker processes. |
| `GGS_TIME_ZONE` | `Europe/Berlin` | |
| `GGS_DEBUG` | `false` | Never enable in production. |

Health check: `GET /healthz` returns `{"status": "ok"}` (also used by the
container's own `HEALTHCHECK`).

## Development

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt "Babel>=2.14,<3"
pybabel compile --domain django --directory locale
GGS_DEBUG=true GGS_HTTPS_ONLY=false python manage.py runserver
python manage.py test
```

Data goes to `./data` by default (`GGS_DATA_DIR` to change it). After
changing user-facing text, run `python manage.py makemessages -l de`
(needs GNU gettext) and fill in the German translations in
`locale/de/LC_MESSAGES/django.po`.
