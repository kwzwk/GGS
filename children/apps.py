from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ChildrenConfig(AppConfig):
    name = "children"
    verbose_name = _("Children")
