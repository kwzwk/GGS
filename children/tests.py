from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Child

User = get_user_model()


class ChildTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user("anna", password="x")
        self.ben = User.objects.create_user("ben", password="x")
        self.client.force_login(self.anna)

    def test_login_required(self):
        self.client.logout()
        self.assertRedirects(self.client.get("/children/"), "/accounts/login/?next=/children/")

    def test_add_edit_and_remove_child(self):
        self.client.post("/children/new/", {"name": "Mia", "class_level": 2})
        mia = Child.objects.get(name="Mia")
        self.assertEqual(mia.parent, self.anna)
        self.assertContains(self.client.get("/children/"), "Klasse 2")

        self.client.post(f"/children/{mia.pk}/edit/", {"name": "Mia", "class_level": 3})
        mia.refresh_from_db()
        self.assertEqual(mia.class_level, 3)

        self.client.post(f"/children/{mia.pk}/delete/")
        self.assertFalse(Child.objects.filter(pk=mia.pk).exists())

    def test_class_level_must_be_1_to_4(self):
        response = self.client.post("/children/new/", {"name": "Mia", "class_level": 5})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Child.objects.exists())

    def test_parents_only_see_their_own_children(self):
        other = Child.objects.create(parent=self.ben, name="Tom", class_level=1)
        self.assertNotContains(self.client.get("/children/"), "Tom")
        self.assertEqual(self.client.get(f"/children/{other.pk}/edit/").status_code, 404)
        self.assertEqual(self.client.post(f"/children/{other.pk}/delete/").status_code, 404)
        self.assertTrue(Child.objects.filter(pk=other.pk).exists())
