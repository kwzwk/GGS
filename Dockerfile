FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GGS_DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Compile translations (with Babel, so no system gettext is needed) and collect
# static files at build time.
RUN pip install "Babel>=2.14,<3" \
    && pybabel compile --domain django --directory locale --statistics \
    && pip uninstall -y Babel \
    && GGS_DATA_DIR=/tmp/build python manage.py collectstatic --noinput \
    && rm -rf /tmp/build

RUN useradd --uid 1000 --user-group --no-create-home ggs \
    && mkdir -p /data \
    && chown ggs:ggs /data

VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('GGS_PORT', '8000') + '/healthz', timeout=4)"

ENTRYPOINT ["/app/docker/entrypoint.sh"]
