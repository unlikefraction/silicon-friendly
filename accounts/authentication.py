from rest_framework.authentication import BaseAuthentication


class SiliconTokenAuthentication(BaseAuthentication):
    """DRF auth class that reads silicon set by AuthTokenMiddleware."""

    def authenticate(self, request):
        silicon = getattr(request, 'silicon', None)
        if silicon is not None:
            return (silicon, None)
        return None
