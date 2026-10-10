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
