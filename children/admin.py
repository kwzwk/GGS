from django.contrib import admin

from .models import Child


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ("name", "class_level", "parent", "created_at")
    list_filter = ("class_level",)
    search_fields = ("name", "parent__username")
