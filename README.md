# Geyen Grundschule · Lernpläne

A self-hosted web app for parents of primary-school children: upload the
week's worksheets, get a short, printable study plan for every school day.
See [CLAUDE.md](CLAUDE.md) for the full spec.

> Status: early setup. The app starts and serves its landing page; accounts,
> uploads and plans are being built.

## Run it

```sh
docker compose up -d
```

The app listens on port 8000 and keeps everything (database, uploads,
generated secret key) in `./data`. Back up that folder to back up the app.

Point your reverse proxy at `http://<server>:8000`. It must pass the
`Host` and `X-Forwarded-Proto` headers (most proxies do by default).

The image is published to `ghcr.io/kwzwk/ggs:latest` on every push to
`main`. GHCR packages start out private: either make the package public in
its GitHub settings, or `docker login ghcr.io` on the server first.

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `GGS_ALLOWED_HOSTS` | `*` | Comma-separated hostnames the app answers to, e.g. `lernplan.example.org`. |
| `GGS_BASE_PATH` | *(empty)* | Sub-path when not served at `/`, e.g. `/lernplan`. Works whether or not the proxy strips it. |
| `GGS_HTTPS_ONLY` | `true` | Cookies only over HTTPS. Set `false` to use the app over plain http (e.g. directly on the LAN). |
| `GGS_CSRF_TRUSTED_ORIGINS` | *(empty)* | Extra origins allowed to submit forms, e.g. `https://lernplan.example.org`. Usually not needed. |
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
