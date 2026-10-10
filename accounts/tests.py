import os
from io import StringIO
from unittest import mock

from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase

from .admin import UserAdmin, make_temporary_password
from .models import Profile

User = get_user_model()


class RegistrationTests(TestCase):
    def test_new_account_waits_for_approval(self):
        response = self.client.post(
            "/accounts/register/",
            {"username": "anna", "email": "", "password1": "Schulweg-2026!", "password2": "Schulweg-2026!"},
        )
        self.assertContains(response, "Freigabe")
        user = User.objects.get(username="anna")
        self.assertFalse(user.is_active)

    def test_pending_parent_is_told_why_login_fails(self):
        User.objects.create_user("anna", password="Schulweg-2026!", is_active=False)
        response = self.client.post("/accounts/login/", {"username": "anna", "password": "Schulweg-2026!"})
        self.assertContains(response, "wartet auf die Freigabe")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_wrong_password_for_pending_parent_gives_generic_error(self):
        User.objects.create_user("anna", password="Schulweg-2026!", is_active=False)
        response = self.client.post("/accounts/login/", {"username": "anna", "password": "falsch"})
        self.assertNotContains(response, "wartet auf die Freigabe")

    def test_approved_parent_can_log_in(self):
        User.objects.create_user("anna", password="Schulweg-2026!")
        response = self.client.post("/accounts/login/", {"username": "anna", "password": "Schulweg-2026!"})
        self.assertRedirects(response, "/children/")


class AdminActionTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser("kai", password="Admin-Pass-2026!")
        self.request = RequestFactory().post("/admin/auth/user/")
        self.request.user = self.admin_user
        self.model_admin = UserAdmin(User, site)
        self.model_admin.message_user = mock.Mock()

    def test_approve(self):
        User.objects.create_user("anna", password="x", is_active=False)
        self.model_admin.approve(self.request, User.objects.filter(username="anna"))
        self.assertTrue(User.objects.get(username="anna").is_active)

    def test_block_never_blocks_yourself(self):
        User.objects.create_user("anna", password="x")
        self.model_admin.block(self.request, User.objects.all())
        self.assertFalse(User.objects.get(username="anna").is_active)
        self.assertTrue(User.objects.get(username="kai").is_active)

    def test_reset_password_forces_change(self):
        anna = User.objects.create_user("anna", password="Old-Pass-2026!")
        with mock.patch("accounts.admin.make_temporary_password", return_value="abcd-efgh-jkmn"):
            self.model_admin.reset_password(self.request, User.objects.filter(pk=anna.pk))
        self.assertIn("abcd-efgh-jkmn", str(self.model_admin.message_user.call_args))

        self.client.post("/accounts/login/", {"username": "anna", "password": "abcd-efgh-jkmn"})
        self.assertRedirects(self.client.get("/children/"), "/accounts/password/")

        response = self.client.post(
            "/accounts/password/",
            {
                "old_password": "abcd-efgh-jkmn",
                "new_password1": "Neues-Passwort-2026!",
                "new_password2": "Neues-Passwort-2026!",
            },
        )
        self.assertRedirects(response, "/accounts/password/done/")
        self.assertFalse(Profile.for_user(anna).must_change_password)
        self.assertEqual(self.client.get("/children/").status_code, 200)

    def test_temporary_password_format(self):
        password = make_temporary_password()
        self.assertRegex(password, r"^[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}$")


class EnsureAdminTests(TestCase):
    def test_creates_admin_from_env_once(self):
        env = {"GGS_ADMIN_USERNAME": "kai", "GGS_ADMIN_PASSWORD": "Admin-Pass-2026!"}
        with mock.patch.dict(os.environ, env):
            call_command("ensure_admin", stdout=StringIO())
            call_command("ensure_admin", stdout=StringIO())
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)
        self.assertTrue(User.objects.get(username="kai").check_password("Admin-Pass-2026!"))

    def test_without_env_does_nothing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            call_command("ensure_admin", stdout=StringIO())
        self.assertFalse(User.objects.exists())
