from django.urls import path

from . import views

app_name = "plans"

urlpatterns = [
    path("<str:week>/", views.detail, name="detail"),
    path("<str:week>/create/", views.create, name="create"),
    path("<str:week>/print/", views.print_view, name="print"),
]
