from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Profile(models.Model):
    """App-specific account state. Approval itself is User.is_active."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    must_change_password = models.BooleanField(
        _("must change password"),
        default=False,
        help_text=_("Set after the admin assigns a temporary password."),
    )

    class Meta:
        verbose_name = _("profile")
        verbose_name_plural = _("profiles")

    def __str__(self):
        return str(self.user)

    @classmethod
    def for_user(cls, user):
        profile, _created = cls.objects.get_or_create(user=user)
        return profile
