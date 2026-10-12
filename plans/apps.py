from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PlansConfig(AppConfig):
    name = "plans"
    verbose_name = _("Study plans")

    def ready(self):
        from . import jobs  # noqa: F401  (registers the job handler)
