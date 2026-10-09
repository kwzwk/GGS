"""Django settings. Everything that differs between installs comes from GGS_* env vars."""

import sys
from pathlib import Path

from .env import env_bool, env_list, env_str, load_or_create_secret_key, normalize_base_path

BASE_DIR = Path(__file__).resolve().parent.parent

# All persistent state (database, uploads, generated secret key) lives here.
DATA_DIR = Path(env_str("GGS_DATA_DIR") or BASE_DIR / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = load_or_create_secret_key(DATA_DIR)
DEBUG = env_bool("GGS_DEBUG")
ALLOWED_HOSTS = env_list("GGS_ALLOWED_HOSTS", "*")
if "*" not in ALLOWED_HOSTS:
    # The container's own health check calls the app on localhost.
    ALLOWED_HOSTS += ["127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = env_list("GGS_CSRF_TRUSTED_ORIGINS")

# Running behind a reverse proxy that terminates TLS.
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Cookies are only sent over HTTPS. Set GGS_HTTPS_ONLY=false to use the app over
# plain http (e.g. http://server:8000 on the LAN without the proxy).
HTTPS_ONLY = env_bool("GGS_HTTPS_ONLY", True)
SESSION_COOKIE_SECURE = HTTPS_ONLY
CSRF_COOKIE_SECURE = HTTPS_ONLY

# Optional sub-path, e.g. GGS_BASE_PATH=/lernplan when served at https://host/lernplan/.
BASE_PATH = normalize_base_path(env_str("GGS_BASE_PATH"))
FORCE_SCRIPT_NAME = BASE_PATH or None
SESSION_COOKIE_PATH = BASE_PATH or "/"
CSRF_COOKIE_PATH = BASE_PATH or "/"
LANGUAGE_COOKIE_PATH = BASE_PATH or "/"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ggs.urls"
WSGI_APPLICATION = "ggs.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {
            # WAL lets the web server and the job worker use the database at the same time.
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "de"
LANGUAGES = [("de", "Deutsch"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = env_str("GGS_TIME_ZONE", "Europe/Berlin")
USE_I18N = True
USE_TZ = True

STATIC_URL = f"{BASE_PATH}/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
if DEBUG or sys.argv[1:2] == ["test"]:
    # No collectstatic in local dev and tests, so serve files without the hashed manifest.
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}

MEDIA_ROOT = DATA_DIR / "uploads"
MEDIA_URL = f"{BASE_PATH}/media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env_str("GGS_LOG_LEVEL", "INFO")},
}
