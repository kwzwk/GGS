from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("accounts/", include("accounts.urls")),
    path("children/", include("children.urls")),
    path("children/<int:child_pk>/worksheets/", include("worksheets.urls")),
    path("", include("core.urls")),
]
