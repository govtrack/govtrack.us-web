from django.conf import settings
settings.AUTHENTICATION_BACKENDS = list(settings.AUTHENTICATION_BACKENDS) + ['registration.views.DirectLoginBackend', 'registration.views.EmailPasswordLoginBackend']

