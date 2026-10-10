from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Child(models.Model):
    class ClassLevel(models.IntegerChoices):
        KLASSE_1 = 1, _("Class 1")
        KLASSE_2 = 2, _("Class 2")
        KLASSE_3 = 3, _("Class 3")
        KLASSE_4 = 4, _("Class 4")

    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="children",
        verbose_name=_("parent"),
    )
    name = models.CharField(
        _("first name"),
        max_length=60,
        help_text=_("Shown on the printed plan. A first name or nickname is enough."),
    )
    class_level = models.PositiveSmallIntegerField(_("class"), choices=ClassLevel.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("child")
        verbose_name_plural = _("children")

    def __str__(self):
        return self.name
