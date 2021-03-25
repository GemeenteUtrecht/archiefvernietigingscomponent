from django.test import TestCase

from archiefvernietigingscomponent.accounts.tests.factories import UserFactory
from archiefvernietigingscomponent.emails.models import EmailPreference


class CreateEmailPreferencesTest(TestCase):
    def test_create_new_user_creates_email_preferences(self):
        self.assertFalse(EmailPreference.objects.all().exists())

        # Signals take care of creating the Email preferences
        UserFactory.create()

        self.assertTrue(EmailPreference.objects.all().exists())
