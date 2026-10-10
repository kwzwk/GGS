import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ggs.settings")


def strip_base_path(app, base_path):
    """Accept requests whether or not the reverse proxy strips GGS_BASE_PATH.

    Django builds URLs with the prefix (FORCE_SCRIPT_NAME); this removes it from
    incoming paths when the proxy forwards it unchanged.
    """
    if not base_path:
        return app

    def wrapped(environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == base_path or path.startswith(base_path + "/"):
            environ["PATH_INFO"] = path[len(base_path):] or "/"
        return app(environ, start_response)

    return wrapped


application = strip_base_path(get_wsgi_application(), settings.BASE_PATH)
