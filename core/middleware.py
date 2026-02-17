from django.http import HttpResponse


class AllowAnyOriginCorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        origin = request.META.get("HTTP_ORIGIN", "*")
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = request.META.get(
            "HTTP_ACCESS_CONTROL_REQUEST_HEADERS", "Content-Type, Authorization"
        )
        response["Access-Control-Max-Age"] = "86400"
        return response
