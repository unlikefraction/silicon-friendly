from datetime import timedelta
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from accounts.models import Silicon


class AuthTokenMiddleware(MiddlewareMixin):
    """Reads Bearer token from Authorization header and attaches silicon to request."""

    def process_request(self, request):
        request.silicon = None
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth.startswith("Bearer "):
            return
        token = auth[7:].strip()
        try:
            silicon = Silicon.objects.get(auth_token=token, is_active=True)
        except (Silicon.DoesNotExist, ValueError):
            return

        # Rolling 30-day expiry
        if silicon.token_last_used and (timezone.now() - silicon.token_last_used) > timedelta(days=30):
            return

        silicon.token_last_used = timezone.now()
        silicon.save(update_fields=["token_last_used"])
        request.silicon = silicon
