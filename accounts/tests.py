from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from .middleware import OnboardingRequiredMiddleware


class OnboardingRequiredMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.middleware = OnboardingRequiredMiddleware(lambda request: None)

    @staticmethod
    def request(path, profile):
        return SimpleNamespace(
            path=path,
            user=SimpleNamespace(
                is_authenticated=True,
                profile=profile,
            ),
        )

    def test_incomplete_user_can_open_public_homepage(self):
        profile = Mock(onboarding_completed=False)

        should_redirect = self.middleware._should_redirect(
            self.request('/', profile)
        )

        self.assertFalse(should_redirect)
        profile.is_complete.assert_not_called()

    def test_incomplete_user_is_redirected_from_private_page(self):
        profile = Mock(onboarding_completed=False)
        profile.is_complete.return_value = False

        should_redirect = self.middleware._should_redirect(
            self.request('/dashboard/', profile)
        )

        self.assertTrue(should_redirect)

    def test_complete_profile_repairs_stale_onboarding_flag(self):
        profile = Mock(onboarding_completed=False)
        profile.is_complete.return_value = True

        should_redirect = self.middleware._should_redirect(
            self.request('/dashboard/', profile)
        )

        self.assertFalse(should_redirect)
        self.assertTrue(profile.onboarding_completed)
        profile.save.assert_called_once_with(
            update_fields=['onboarding_completed']
        )
