from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from . import queue
from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "status", "attempts", "run_after", "created_at", "finished_at")
    list_filter = ("status", "kind")
    readonly_fields = [f.name for f in Job._meta.fields]
    actions = ["retry_failed"]

    def has_add_permission(self, request):
        return False

    @admin.action(description=_("Retry failed jobs"))
    def retry_failed(self, request, queryset):
        count = queue.retry(queryset)
        self.message_user(
            request,
            ngettext("%(count)d job queued again.", "%(count)d jobs queued again.", count)
            % {"count": count},
            messages.SUCCESS,
        )
