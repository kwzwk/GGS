from django.urls import path

from . import views

app_name = "worksheets"

urlpatterns = [
    path("", views.week_list, name="weeks"),
    path("upload/", views.upload, name="upload"),
    path("week/<str:week>/", views.week_detail, name="week"),
    path("pages/<int:pk>/image/", views.page_image, name="page_image"),
    path("pages/<int:pk>/delete/", views.page_delete, name="page_delete"),
    path("pages/<int:pk>/retry/", views.page_retry, name="page_retry"),
]
