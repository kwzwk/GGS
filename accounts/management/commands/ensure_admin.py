import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Create the admin account from GGS_ADMIN_USERNAME and GGS_ADMIN_PASSWORD "
        "if no superuser exists yet."
    )

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get("GGS_ADMIN_USERNAME", "").strip()
        password = os.environ.get("GGS_ADMIN_PASSWORD", "")
        if User.objects.filter(is_superuser=True).exists():
            return
        if not username or not password:
            self.stdout.write(
                "No admin account yet. Set GGS_ADMIN_USERNAME and GGS_ADMIN_PASSWORD, "
                "or run: python manage.py createsuperuser"
            )
            return
        User.objects.create_superuser(username=username, email="", password=password)
        self.stdout.write(f"Created admin account '{username}'.")
