import secrets

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from children.models import Child

from .models import Profile

User = get_user_model()

# Easy to read out or type: no 0/O, 1/l/I.
_TEMP_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def make_temporary_password():
    groups = ["".join(secrets.choice(_TEMP_ALPHABET) for _ in range(4)) for _ in range(3)]
    return "-".join(groups)


class ChildInline(admin.TabularInline):
    model = Child
    extra = 0
    fields = ("name", "class_level")


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "is_active", "is_staff", "date_joined", "last_login")
    list_filter = ("is_active", "is_staff")
    ordering = ("is_active", "-date_joined")
    inlines = [ChildInline]
    actions = ["approve", "block", "reset_password"]

    @admin.action(description=_("Approve selected accounts"))
    def approve(self, request, queryset):
        count = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(
            request,
            ngettext("%(count)d account approved.", "%(count)d accounts approved.", count)
            % {"count": count},
            messages.SUCCESS,
        )

    @admin.action(description=_("Block selected accounts"))
    def block(self, request, queryset):
        count = queryset.exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(
            request,
            ngettext("%(count)d account blocked.", "%(count)d accounts blocked.", count)
            % {"count": count},
            messages.SUCCESS,
        )

    @admin.action(description=_("Reset password (temporary password)"))
    def reset_password(self, request, queryset):
        for user in queryset:
            temporary = make_temporary_password()
            user.set_password(temporary)
            user.save(update_fields=["password"])
            profile = Profile.for_user(user)
            profile.must_change_password = True
            profile.save(update_fields=["must_change_password"])
            self.message_user(
                request,
                _(
                    "Temporary password for %(username)s: %(password)s. "
                    "They must choose a new password after logging in."
                )
                % {"username": user.get_username(), "password": temporary},
                messages.WARNING,
            )
