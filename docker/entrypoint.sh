#!/bin/sh
set -e

DATA_DIR="${GGS_DATA_DIR:-/data}"

# Started as root so a freshly mounted volume can be handed to the app user,
# then everything runs unprivileged.
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"
    chown -R ggs:ggs "$DATA_DIR"
    exec setpriv --reuid=ggs --regid=ggs --init-groups "$0" "$@"
fi

python manage.py migrate --noinput
python manage.py ensure_admin

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec gunicorn ggs.wsgi \
    --bind "0.0.0.0:${GGS_PORT:-8000}" \
    --workers "${GGS_WEB_WORKERS:-2}" \
    --forwarded-allow-ips "*" \
    --access-logfile - \
    --access-logformat '%({x-forwarded-for}i)s %(h)s "%(r)s" %(s)s %(b)s %(M)sms'
