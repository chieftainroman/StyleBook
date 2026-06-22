from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch


# Paths where the user is allowed to be even while not onboarded.
# Everything else redirects to /onboarding/.
ALLOWED_PATH_PREFIXES = (
    '/onboarding/',
    '/accounts/',       # django-allauth (Google login callback, logout)
    '/auth/',           # your custom auth routes
    '/admin/',          # superuser access
    '/static/',
    '/media/',
    '/favicon',
)


class OnboardingRequiredMiddleware:
    """
    Force logged-in users with an incomplete MasterProfile to /onboarding/.
    Skips static files, auth routes, and the onboarding pages themselves.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_redirect(request):
            try:
                return redirect(reverse('onboarding_start'))
            except NoReverseMatch:
                # Onboarding URLs not wired up yet — fail open (don't break the app)
                pass
        return self.get_response(request)

    def _should_redirect(self, request):
        # 1. Anonymous users — never redirect
        if not request.user.is_authenticated:
            return False

        # 2. Allowed paths — let through
        path = request.path
        for prefix in ALLOWED_PATH_PREFIXES:
            if path.startswith(prefix):
                return False

        # 3. User without a MasterProfile (shouldn't happen, but safe) — let through
        if not hasattr(request.user, 'profile'):
            return False

        # 4. Already onboarded — let through
        if request.user.profile.onboarding_completed:
            return False

        # 5. Everything else — redirect
        return True