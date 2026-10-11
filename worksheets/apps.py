from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class WorksheetsConfig(AppConfig):
    name = "worksheets"
    verbose_name = _("Worksheets")

    def ready(self):
        from . import jobs, signals  # noqa: F401  (registers job handlers and signals)
