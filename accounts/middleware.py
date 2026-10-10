from django.shortcuts import redirect
from django.urls import Resolver404, resolve

from .models import Profile

# Pages a user with a temporary password may still open.
ALLOWED_URL_NAMES = {"password_change", "password_change_done", "logout", "set_language", "healthz"}


class ForcePasswordChangeMiddleware:
    """Send users with an admin-assigned temporary password to the change form."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not self._allowed(request):
            if Profile.objects.filter(user=user, must_change_password=True).exists():
                return redirect("password_change")
        return self.get_response(request)

    @staticmethod
    def _allowed(request):
        try:
            return resolve(request.path_info).url_name in ALLOWED_URL_NAMES
        except Resolver404:
            return False
