from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Page, Upload, Week


class UploadInline(admin.TabularInline):
    model = Upload
    fields = ("original_name", "uploaded_at")
    readonly_fields = fields
    extra = 0
    can_delete = True
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = ("child", "week_start", "parent")
    list_filter = ("week_start",)
    search_fields = ("child__name", "child__parent__username")
    readonly_fields = ("child", "week_start")
    inlines = [UploadInline]

    @admin.display(description=_("parent"), ordering="child__parent__username")
    def parent(self, obj):
        return obj.child.parent

    def has_add_permission(self, request):
        return False


class PageInline(admin.TabularInline):
    model = Page
    fields = ("page_number", "status", "analysis", "error")
    readonly_fields = fields
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Upload)
class UploadAdmin(admin.ModelAdmin):
    list_display = ("original_name", "week", "uploaded_at")
    list_filter = ("uploaded_at",)
    date_hierarchy = "uploaded_at"
    readonly_fields = ("week", "file", "original_name", "content_type", "uploaded_at")
    inlines = [PageInline]

    def has_add_permission(self, request):
        return False
