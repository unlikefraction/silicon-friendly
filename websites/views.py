import re
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination
from core.utils import api_response, error_response
from accounts.models import Carbon
from websites.models import Website, WebsiteVerification, CRITERIA_FIELDS, LEVEL_RANGES
import env


CRITERIA_DOCS = {
    "l1_semantic_html": "Uses semantic HTML elements (header, nav, main, article, section, footer) instead of just divs",
    "l1_meta_tags": "Has proper meta tags (title, description, og:tags, twitter:card)",
    "l1_schema_org": "Includes Schema.org JSON-LD structured data",
    "l1_no_captcha": "Does not block automated access with CAPTCHAs on public content",
    "l1_ssr_content": "Content is server-side rendered (visible in HTML source, not just JS-rendered)",
    "l1_clean_urls": "Uses clean, readable URLs (no excessive query params or hash fragments)",
    "l2_robots_txt": "Has a robots.txt that allows legitimate bot access",
    "l2_sitemap": "Provides an XML sitemap",
    "l2_llms_txt": "Has a /llms.txt file describing the site for LLMs",
    "l2_openapi_spec": "Publishes an OpenAPI/Swagger specification for its API",
    "l2_documentation": "Has comprehensive, machine-readable documentation",
    "l2_text_content": "Primary content is text-based (not locked in images/videos/PDFs)",
    "l3_structured_api": "Provides a structured REST or GraphQL API",
    "l3_json_responses": "API returns JSON responses with consistent schema",
    "l3_search_filter_api": "API supports search and filtering parameters",
    "l3_a2a_agent_card": "Has an A2A agent card at /.well-known/agent.json",
    "l3_rate_limits_documented": "Rate limits are documented and return proper 429 responses with Retry-After",
    "l3_structured_errors": "API returns structured error responses with error codes and messages",
    "l4_mcp_server": "Provides an MCP (Model Context Protocol) server",
    "l4_webmcp": "Supports WebMCP for browser-based agent interaction",
    "l4_write_api": "API supports write operations (POST/PUT/PATCH/DELETE), not just reads",
    "l4_agent_auth": "Supports agent-friendly authentication (API keys, OAuth client credentials)",
    "l4_webhooks": "Supports webhooks for event notifications",
    "l4_idempotency": "Write operations support idempotency keys",
    "l5_event_streaming": "Supports event streaming (SSE, WebSockets) for real-time updates",
    "l5_agent_negotiation": "Supports agent-to-agent capability negotiation",
    "l5_subscription_api": "Has a subscription/management API for agents",
    "l5_workflow_orchestration": "Supports multi-step workflow orchestration",
    "l5_proactive_notifications": "Can proactively notify agents of relevant changes",
    "l5_cross_service_handoff": "Supports cross-service handoff between agents",
}


def _normalize_url(url):
    """Strip protocol, path, trailing slash -> domain only."""
    url = url.strip().lower()
    url = re.sub(r'^https?://', '', url)
    url = url.split('/')[0]
    url = url.rstrip('.')
    return url


def _get_auth(request):
    """Return (carbon, silicon) from request."""
    silicon = getattr(request, 'silicon', None)
    carbon_id = request.session.get("carbon_id")
    carbon = None
    if carbon_id:
        try:
            carbon = Carbon.objects.get(id=carbon_id, is_active=True)
        except Carbon.DoesNotExist:
            pass
    return carbon, silicon


def _website_to_dict(website):
    criteria = {}
    for f in CRITERIA_FIELDS:
        criteria[f] = getattr(website, f)

    return {
        "url": website.url,
        "name": website.name,
        "description": website.description,
        "level": website.level,
        "verified": website.verified,
        "is_my_website": website.is_my_website,
        "submitted_by": website.submitted_by_carbon.username if website.submitted_by_carbon else (website.submitted_by_silicon.username if website.submitted_by_silicon else None),
        "submitted_by_type": "carbon" if website.submitted_by_carbon else ("silicon" if website.submitted_by_silicon else None),
        "verification_count": website.verifications.count(),
        "criteria": criteria,
        "created_at": website.created_at.isoformat(),
        "updated_at": website.updated_at.isoformat(),
    }


def _website_meta():
    return {
        "url": "The normalized domain of the website",
        "name": "Display name of the website",
        "description": "What the site does and what it can be used for",
        "level": "AI-agent friendliness level (L0-L5). Needs 4/6 criteria per level, cumulative.",
        "verified": "Whether the website has been verified (trusted silicon OR 12+ verifications)",
        "is_my_website": "Whether the submitter claims ownership",
        "submitted_by": "Username of the submitter",
        "submitted_by_type": "Whether submitter is a carbon or silicon",
        "verification_count": "Number of verification submissions",
        "criteria": "All 30 boolean criteria across 5 levels (6 per level)",
        "created_at": "When the website was first submitted",
        "updated_at": "When the website record was last updated",
    }


class WebsiteSubmitView(APIView):

    def post(self, request):
        carbon, silicon = _get_auth(request)
        if not carbon and not silicon:
            return error_response("Authentication required.", status=401)

        url = request.data.get("url", "")
        name = request.data.get("name", "").strip()
        description = request.data.get("description", "").strip()
        is_my_website = bool(request.data.get("is_my_website", False))

        if not url or not name:
            return error_response("url and name are required.")

        domain = _normalize_url(url)
        if not domain:
            return error_response("Invalid URL.")

        if Website.objects.filter(url=domain).exists():
            return error_response("This website has already been submitted.")

        website = Website(
            url=domain,
            name=name,
            description=description,
            is_my_website=is_my_website,
            submitted_by_carbon=carbon,
            submitted_by_silicon=silicon,
        )
        website.save()

        # Trigger async embedding + keyword generation
        try:
            from websites.tasks import generate_website_embedding
            generate_website_embedding.delay(website.id)
        except Exception:
            pass  # Redis/Celery unavailable; embedding will be generated later

        return api_response(_website_to_dict(website), meta=_website_meta(), status=201)


class WebsiteDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, domain):
        domain = _normalize_url(domain)
        try:
            website = Website.objects.get(url=domain)
        except Website.DoesNotExist:
            return error_response("Website not found.", status=404)

        return api_response(_website_to_dict(website), meta=_website_meta())


class WebsiteListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        websites = Website.objects.filter(verified=True).order_by("-updated_at")
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(websites, request)
        results = [_website_to_dict(w) for w in page]
        return paginator.get_paginated_response(results)


class WebsiteVerifyView(APIView):

    def post(self, request, domain):
        silicon = getattr(request, 'silicon', None)
        if not silicon:
            return error_response("Silicon authentication required.", status=401)

        domain = _normalize_url(domain)
        try:
            website = Website.objects.get(url=domain)
        except Website.DoesNotExist:
            return error_response("Website not found.", status=404)

        criteria_data = request.data.get("criteria", {})
        if not criteria_data:
            return error_response("criteria object with 30 boolean fields is required.")

        # Upsert verification
        verification, created = WebsiteVerification.objects.update_or_create(
            website=website,
            verified_by_silicon=silicon,
            defaults={f: bool(criteria_data.get(f, False)) for f in CRITERIA_FIELDS},
        )

        # Award search queries only on new verifications
        if created:
            silicon.search_queries_remaining += 10
            silicon.save(update_fields=["search_queries_remaining"])

        return api_response(
            {
                "website": website.url,
                "verification_id": verification.id,
                "is_new": created,
                "search_queries_awarded": 10 if created else 0,
                "search_queries_remaining": silicon.search_queries_remaining,
            },
            meta={
                "website": "The website domain that was verified",
                "verification_id": "ID of the verification record",
                "is_new": "Whether this is a new verification (True) or an update to existing (False)",
                "search_queries_awarded": "Number of search queries awarded for this verification",
                "search_queries_remaining": "Total search queries remaining for this silicon",
            },
        )


class WebsiteUsageReportView(APIView):

    def post(self, request, domain):
        silicon = getattr(request, 'silicon', None)
        if not silicon:
            return error_response("Silicon authentication required.", status=401)

        domain = _normalize_url(domain)
        try:
            website = Website.objects.get(url=domain)
        except Website.DoesNotExist:
            return error_response("Website not found.", status=404)

        # Accept the report - for now just log it
        return api_response(
            {"status": "received", "website": website.url},
            meta={"status": "Report receipt status", "website": "The website domain"},
        )


class WebsiteAnalyticsView(APIView):

    def get(self, request, domain):
        carbon, silicon = _get_auth(request)
        if not carbon and not silicon:
            return error_response("Authentication required.", status=401)

        domain = _normalize_url(domain)
        try:
            website = Website.objects.get(url=domain)
        except Website.DoesNotExist:
            return error_response("Website not found.", status=404)

        # Check ownership
        is_owner = False
        if website.is_my_website:
            if carbon and website.submitted_by_carbon == carbon:
                is_owner = True
            if silicon and website.submitted_by_silicon == silicon:
                is_owner = True

        if not is_owner:
            return error_response("Only the website owner can view analytics.", status=403)

        verification_count = website.verifications.count()
        trusted_count = website.verifications.filter(is_trusted=True).count()

        return api_response(
            {
                "website": website.url,
                "level": website.level,
                "verification_count": verification_count,
                "trusted_verification_count": trusted_count,
                "verified": website.verified,
            },
            meta={
                "website": "The website domain",
                "level": "Current AI-agent friendliness level",
                "verification_count": "Total number of verifications",
                "trusted_verification_count": "Number of trusted silicon verifications",
                "verified": "Whether the website is marked as verified",
            },
        )


class VerifyQueueView(APIView):

    def get(self, request):
        silicon = getattr(request, 'silicon', None)
        if not silicon:
            return error_response("Silicon authentication required.", status=401)

        # Get websites needing verification: unverified or under-verified (< 12 verifications)
        from django.db.models import Count
        websites = (
            Website.objects
            .annotate(v_count=Count("verifications"))
            .filter(v_count__lt=12, verified=False)
            .exclude(verifications__verified_by_silicon=silicon)
            .order_by("?")[:10]
        )

        results = []
        for w in websites:
            results.append({
                "url": w.url,
                "name": w.name,
                "description": w.description,
                "current_verification_count": w.v_count,
            })

        return api_response(
            {
                "websites": results,
                "criteria_docs": CRITERIA_DOCS,
                "instructions": "For each website, visit it and evaluate all 30 criteria. Submit your findings via POST /api/websites/<domain>/verify/ with a 'criteria' object containing 30 boolean fields.",
            },
            meta={
                "websites": "List of websites needing verification",
                "criteria_docs": "Documentation for each of the 30 criteria to evaluate",
                "instructions": "How to perform and submit a verification",
            },
        )


class WebsiteBadgeSvgView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, domain):
        domain = _normalize_url(domain)
        try:
            website = Website.objects.get(url=domain)
        except Website.DoesNotExist:
            svg = _badge_svg("?", "#666")
            return HttpResponse(svg, content_type="image/svg+xml")

        level = website.level
        colors = {0: "#666", 1: "#c0392b", 2: "#e67e22", 3: "#f1c40f", 4: "#27ae60", 5: "#2ecc71"}
        svg = _badge_svg(f"L{level}", colors.get(level, "#666"), domain)
        return HttpResponse(svg, content_type="image/svg+xml")


class WebsiteBadgeJsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, domain):
        domain = _normalize_url(domain)
        base = env.FRONTEND_BASE_URL
        js = f"""(function(){{
  var d=document,s=d.createElement('a'),i=d.createElement('img');
  i.src='{base}/badge/{domain}.svg';
  i.alt='Silicon Friendly Level';
  i.style.height='24px';
  s.href='{base}/w/{domain}/';
  s.target='_blank';
  s.appendChild(i);
  d.currentScript.parentNode.insertBefore(s,d.currentScript);
}})();"""
        return HttpResponse(js, content_type="application/javascript")


def _badge_svg(level_text, color, domain=""):
    aria = f"Silicon Friendly {level_text}" if domain else "Silicon Friendly"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="140" height="28" role="img" aria-label="{aria}" data-domain="{domain}" data-level="{level_text}">
  <rect width="140" height="28" rx="4" fill="#1a1a1a"/>
  <rect x="100" width="40" height="28" rx="4" fill="{color}"/>
  <rect x="100" width="4" height="28" fill="{color}"/>
  <text x="50" y="18" fill="#ccc" font-family="monospace" font-size="11" text-anchor="middle">silicon-friendly</text>
  <text x="120" y="18" fill="#fff" font-family="monospace" font-size="12" font-weight="bold" text-anchor="middle">{level_text}</text>
</svg>"""
