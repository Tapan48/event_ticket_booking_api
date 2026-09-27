from .base import *  # noqa: F403

DEBUG = False

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# collectstatic never runs in tests; don't make whitenoise scan a missing STATIC_ROOT.
WHITENOISE_AUTOREFRESH = True
