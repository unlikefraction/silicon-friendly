import time
from django.core.cache import cache
from django.http import JsonResponse


def check_rate_limit(key, max_requests, window_seconds):
    """Sliding window rate limiter using cache.
    Returns (allowed: bool, retry_after: int seconds)"""
    now = time.time()
    cache_key = f"ratelimit:{key}"

    # Get existing timestamps
    timestamps = cache.get(cache_key, [])

    # Remove expired timestamps
    cutoff = now - window_seconds
    timestamps = [t for t in timestamps if t > cutoff]

    if len(timestamps) >= max_requests:
        # Calculate when the oldest relevant request expires
        oldest = min(timestamps)
        retry_after = int(oldest + window_seconds - now) + 1
        return False, max(retry_after, 1)

    # Add current timestamp
    timestamps.append(now)
    cache.set(cache_key, timestamps, window_seconds + 60)

    return True, 0


def rate_limit_response(retry_after):
    """Return a 429 JSON response with Retry-After header."""
    response = JsonResponse(
        {"error": f"Rate limit exceeded. Try again in {retry_after} seconds.", "retry_after": retry_after},
        status=429,
    )
    response["Retry-After"] = str(retry_after)
    return response


def get_client_ip(request):
    """Get the client IP from the request, handling proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")
