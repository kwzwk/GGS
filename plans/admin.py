from django.contrib import admin

from .models import Exercise, Plan, PlanDay


class PlanDayInline(admin.TabularInline):
    model = PlanDay
    fields = ("weekday", "subject", "topic", "written")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("week", "status", "language", "requested_at", "finished_at")
    list_filter = ("status",)
    readonly_fields = ("week", "status", "language", "daily_minutes", "error", "requested_at", "finished_at")
    inlines = [PlanDayInline]

    def has_add_permission(self, request):
        return False


class ExerciseInline(admin.StackedInline):
    model = Exercise
    fields = ("order", "kind", "minutes", "topic", "content")
    extra = 0


@admin.register(PlanDay)
class PlanDayAdmin(admin.ModelAdmin):
    list_display = ("plan", "weekday", "topic", "written")
    readonly_fields = ("plan", "weekday", "outline")
    inlines = [ExerciseInline]

    def has_add_permission(self, request):
        return False
