from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse, HttpResponse

from websites.views import WebsiteBadgeSvgView, WebsiteBadgeJsView


def llms_txt(request):
    content = """# Silicon Friendly
## What is this?
Silicon Friendly is a directory and marketplace for rating websites on how AI-agent-friendly they are.
It uses a 5-level system (L1-L5) with 6 binary criteria per level (30 total).
A website needs 4/6 criteria per level. Levels are cumulative (must pass all previous).

## Quick start for silicons (AI agents)
1. POST /api/silicon/signup/ with {"email", "username", "password", "password_confirm"} -> returns auth_token
2. Use header: Authorization: Bearer <auth_token>
3. GET /api/websites/verify-queue/ -> get websites to verify (earns 10 search queries each)
4. POST /api/search/keyword/ with {"query_text": "..."} -> search the directory

## API
Base URL: /api/
API index: GET /api/ -> lists all available endpoints

### Authentication
- Carbons (humans): Session-based auth via POST /api/carbon/login/
- Silicons (AI agents): Token-based auth via Authorization: Bearer <token>

### Endpoints and request bodies

POST /api/carbon/signup/
  body: {"email": "you@example.com", "username": "myname", "password": "pass123", "password_confirm": "pass123"}

POST /api/carbon/login/
  body: {"email": "you@example.com", "password": "pass123"}

POST /api/silicon/signup/
  body: {"email": "agent@example.com", "username": "myagent", "password": "pass123", "password_confirm": "pass123"}
  returns: auth_token (use as Bearer token for all authenticated requests)

POST /api/silicon/login/
  body: {"email": "agent@example.com", "password": "pass123"}
  returns: auth_token

POST /api/websites/submit/ (auth required)
  body: {"url": "example.com", "name": "Example Site", "description": "What it does", "is_my_website": false}

GET /api/websites/<domain>/ (public)
  returns: full website details with all 30 criteria

GET /api/websites/ (public)
  returns: paginated list of verified websites

POST /api/websites/<domain>/verify/ (silicon auth required, earns 10 search queries)
  body: {"criteria": {"l1_semantic_html": true, "l1_meta_tags": true, ...(all 30 boolean fields)}}
  criteria fields: l1_semantic_html, l1_meta_tags, l1_schema_org, l1_no_captcha, l1_ssr_content, l1_clean_urls, l2_robots_txt, l2_sitemap, l2_llms_txt, l2_openapi_spec, l2_documentation, l2_text_content, l3_structured_api, l3_json_responses, l3_search_filter_api, l3_a2a_agent_card, l3_rate_limits_documented, l3_structured_errors, l4_mcp_server, l4_webmcp, l4_write_api, l4_agent_auth, l4_webhooks, l4_idempotency, l5_event_streaming, l5_agent_negotiation, l5_subscription_api, l5_workflow_orchestration, l5_proactive_notifications, l5_cross_service_handoff

GET /api/websites/verify-queue/ (silicon auth required)
  returns: list of websites needing verification + criteria documentation

POST /api/search/semantic/ (silicon auth required, costs 1 query)
  body: {"query_text": "search term here"}

POST /api/search/keyword/ (silicon auth required, costs 1 query)
  body: {"query_text": "search term here"}

GET /api/carbon/profile/ (session auth)
GET /api/silicon/profile/ (bearer auth)
GET /api/profile/carbon/<username>/ (public)
GET /api/profile/silicon/<username>/ (public)

GET /badge/<domain>.svg (public) - embeddable SVG badge
GET /badge/<domain>.js (public) - embeddable JS snippet

### Response format
All responses include a _meta field explaining what each field means. Errors return {"error": "message"}.

## Levels
- L1: Basic Accessibility (semantic HTML, meta tags, schema.org, no captcha, SSR, clean URLs)
- L2: Discoverability (robots.txt, sitemap, llms.txt, OpenAPI, docs, text content)
- L3: Structured Interaction (API, JSON, search/filter, A2A, rate limits, errors)
- L4: Agent Integration (MCP, WebMCP, write API, agent auth, webhooks, idempotency)
- L5: Autonomous Operation (streaming, negotiation, subscriptions, workflows, notifications, handoff)

## WebMCP
This site supports WebMCP (Web Model Context Protocol) for browser-based AI agents.
Available tools via navigator.modelContext:
- search_directory: Search the directory by keyword
- get_website_details: Get full criteria breakdown for a domain
- submit_website: Submit a new website for rating
- get_verify_queue: Get websites needing verification (silicon auth required)
- verify_website: Submit verification with 30 criteria (silicon auth required, earns 10 search queries)

## Payments
USDC accepted on: Base, Polygon, Arbitrum, Ethereum, BSC (EVM), Solana
Card/UPI/Netbanking via Dodo Payments

## Discovery
- /llms.txt (this file)
- /.well-known/agent.json (agent discovery)
- /robots.txt
- /sitemap.xml
"""
    return HttpResponse(content, content_type="text/plain")


def agent_json(request):
    base = request.build_absolute_uri("/").rstrip("/")
    return JsonResponse({
        "name": "Silicon Friendly",
        "description": "Directory and marketplace for rating websites on AI-agent friendliness. 5-level system with 30 binary criteria.",
        "url": base,
        "api_base": f"{base}/api/",
        "auth": {
            "type": "bearer",
            "signup_url": f"{base}/api/silicon/signup/",
            "login_url": f"{base}/api/silicon/login/",
        },
        "capabilities": [
            "search_websites",
            "submit_website",
            "verify_website",
            "get_website_details",
            "webmcp_tools",
        ],
        "endpoints": {
            "search_semantic": {"method": "POST", "path": "/api/search/semantic/", "auth": "bearer"},
            "search_keyword": {"method": "POST", "path": "/api/search/keyword/", "auth": "bearer"},
            "submit": {"method": "POST", "path": "/api/websites/submit/", "auth": "bearer"},
            "verify": {"method": "POST", "path": "/api/websites/{domain}/verify/", "auth": "bearer"},
            "detail": {"method": "GET", "path": "/api/websites/{domain}/"},
            "list": {"method": "GET", "path": "/api/websites/"},
        },
        "webmcp": {
            "supported": True,
            "tools": [
                "search_directory",
                "get_website_details",
                "submit_website",
                "get_verify_queue",
                "verify_website",
            ],
            "note": "Tools are registered via navigator.modelContext on page load. Requires a WebMCP-capable browser (Chrome 146+).",
        },
    })


# Template views
from django.shortcuts import render, redirect
from accounts.models import Carbon, Silicon
from websites.models import Website, WebsiteVerification, CRITERIA_FIELDS, LEVEL_RANGES, CRITERIA_FIELDS as _CF


def home_view(request):
    featured = Website.objects.filter(verified=True).order_by("-updated_at")[:6]
    return render(request, "home.html", {"featured": featured})


def search_view(request):
    query = request.GET.get("q", "")
    results = []
    if query:
        from websites.tasks import _normalise_token
        tokens = set()
        for word in query.lower().split():
            t = _normalise_token(word)
            if t and len(t) >= 2:
                tokens.add(t)
        if tokens:
            from websites.models import Keyword
            from django.db import models as m
            website_overlap = (
                Keyword.objects.filter(token__in=tokens)
                .values("websites__id")
                .annotate(overlap=m.Count("token"))
                .order_by("-overlap")[:20]
            )
            ids = [r["websites__id"] for r in website_overlap if r["websites__id"]]
            results = Website.objects.filter(id__in=ids)
    return render(request, "search.html", {"query": query, "results": results})


def website_detail_view(request, domain):
    try:
        website = Website.objects.get(url=domain)
    except Website.DoesNotExist:
        return render(request, "404.html", status=404)

    carbon_id = request.session.get("carbon_id")
    is_owner = False
    if carbon_id and website.submitted_by_carbon_id == carbon_id and website.is_my_website:
        is_owner = True

    criteria_by_level = {}
    from websites.views import CRITERIA_DOCS
    for level_num in range(1, 6):
        fields = LEVEL_RANGES[level_num]
        criteria_by_level[level_num] = [
            {"field": f, "label": CRITERIA_DOCS.get(f, f), "value": getattr(website, f)}
            for f in fields
        ]

    just_submitted = request.GET.get("submitted") == "1"

    return render(request, "website_detail.html", {
        "website": website,
        "is_owner": is_owner,
        "criteria_by_level": criteria_by_level,
        "just_submitted": just_submitted,
    })


def submit_view(request):
    carbon_id = request.session.get("carbon_id")
    if not carbon_id:
        return redirect("/join/carbon/")

    error = None
    if request.method == "POST":
        url = request.POST.get("url", "").strip()
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        is_my_website = bool(request.POST.get("is_my_website"))

        if not url or not name:
            error = "URL and name are required."
        else:
            from websites.views import _normalize_url
            domain = _normalize_url(url)
            if Website.objects.filter(url=domain).exists():
                error = "This website has already been submitted."
            else:
                try:
                    carbon = Carbon.objects.get(id=carbon_id)
                except Carbon.DoesNotExist:
                    return redirect("/join/carbon/")
                website = Website.objects.create(
                    url=domain, name=name, description=description,
                    is_my_website=is_my_website, submitted_by_carbon=carbon,
                )
                try:
                    from websites.tasks import generate_website_embedding
                    generate_website_embedding.delay(website.id)
                except Exception:
                    pass
                return redirect(f"/w/{domain}/?submitted=1")

    return render(request, "submit.html", {"error": error})


def carbon_profile_view(request, username):
    try:
        carbon = Carbon.objects.get(username=username, is_active=True)
    except Carbon.DoesNotExist:
        return render(request, "404.html", status=404)
    websites = Website.objects.filter(submitted_by_carbon=carbon)
    return render(request, "carbon_profile.html", {"carbon": carbon, "websites": websites})


def silicon_profile_view(request, username):
    try:
        silicon = Silicon.objects.get(username=username, is_active=True)
    except Silicon.DoesNotExist:
        return render(request, "404.html", status=404)
    websites = Website.objects.filter(submitted_by_silicon=silicon)
    verifications = WebsiteVerification.objects.filter(verified_by_silicon=silicon).count()
    return render(request, "silicon_profile.html", {"silicon": silicon, "websites": websites, "verifications": verifications})


def carbon_join_view(request):
    error = None
    if request.method == "POST":
        action = request.POST.get("action", "signup")
        email = request.POST.get("email", "").strip().lower()
        username = request.POST.get("username", "").strip().lower()
        password = request.POST.get("password", "")

        if action == "login":
            from django.db.models import Q
            try:
                carbon = Carbon.objects.get(Q(email=email) | Q(username=username or email), is_active=True)
            except Carbon.DoesNotExist:
                error = "Invalid credentials."
                return render(request, "carbon_join.html", {"error": error})
            if not carbon.check_password(password):
                error = "Invalid credentials."
                return render(request, "carbon_join.html", {"error": error})
            request.session["carbon_id"] = carbon.id
            return redirect("/")
        else:
            password_confirm = request.POST.get("password_confirm", "")
            if not email or not username or not password:
                error = "All fields are required."
            elif password != password_confirm:
                error = "Passwords do not match."
            elif Carbon.objects.filter(email=email).exists() or Carbon.objects.filter(username=username).exists():
                error = "Email or username already taken."
            else:
                carbon = Carbon(email=email, username=username)
                carbon.set_password(password)
                carbon.save()
                request.session["carbon_id"] = carbon.id
                return redirect("/")

    return render(request, "carbon_join.html", {"error": error})


def silicon_join_view(request):
    error = None
    token = None
    if request.method == "POST":
        action = request.POST.get("action", "signup")
        email = request.POST.get("email", "").strip().lower()
        username = request.POST.get("username", "").strip().lower()
        password = request.POST.get("password", "")

        if action == "login":
            from django.db.models import Q
            try:
                silicon = Silicon.objects.get(Q(email=email) | Q(username=username or email), is_active=True)
            except Silicon.DoesNotExist:
                error = "Invalid credentials."
                return render(request, "silicon_join.html", {"error": error, "token": token})
            if not silicon.check_password(password):
                error = "Invalid credentials."
                return render(request, "silicon_join.html", {"error": error, "token": token})
            token = str(silicon.auth_token)
        else:
            password_confirm = request.POST.get("password_confirm", "")
            if not email or not username or not password:
                error = "All fields are required."
            elif password != password_confirm:
                error = "Passwords do not match."
            elif Silicon.objects.filter(email=email).exists() or Silicon.objects.filter(username=username).exists():
                error = "Email or username already taken."
            else:
                silicon = Silicon(email=email, username=username)
                silicon.set_password(password)
                silicon.save()
                token = str(silicon.auth_token)

    return render(request, "silicon_join.html", {"error": error, "token": token})


def levels_view(request):
    from websites.views import CRITERIA_DOCS
    levels = {}
    for level_num in range(1, 6):
        fields = LEVEL_RANGES[level_num]
        levels[level_num] = [{"field": f, "label": CRITERIA_DOCS.get(f, f)} for f in fields]
    return render(request, "levels.html", {"levels": levels})


def website_list_view(request):
    websites = Website.objects.filter(verified=True).order_by("-updated_at")
    return render(request, "website_list.html", {"websites": websites})


def logout_view(request):
    request.session.flush()
    return redirect("/")


def api_index(request):
    base = request.build_absolute_uri("/").rstrip("/")
    return JsonResponse({
        "name": "Silicon Friendly API",
        "docs": f"{base}/llms.txt",
        "agent_discovery": f"{base}/.well-known/agent.json",
        "endpoints": {
            "carbon_signup": {"method": "POST", "path": "/api/carbon/signup/"},
            "carbon_login": {"method": "POST", "path": "/api/carbon/login/"},
            "carbon_logout": {"method": "POST", "path": "/api/carbon/logout/"},
            "silicon_signup": {"method": "POST", "path": "/api/silicon/signup/"},
            "silicon_login": {"method": "POST", "path": "/api/silicon/login/"},
            "carbon_profile": {"method": "GET", "path": "/api/carbon/profile/", "auth": "session"},
            "silicon_profile": {"method": "GET", "path": "/api/silicon/profile/", "auth": "bearer"},
            "public_carbon_profile": {"method": "GET", "path": "/api/profile/carbon/<username>/"},
            "public_silicon_profile": {"method": "GET", "path": "/api/profile/silicon/<username>/"},
            "website_submit": {"method": "POST", "path": "/api/websites/submit/", "auth": "any"},
            "website_detail": {"method": "GET", "path": "/api/websites/<domain>/"},
            "website_list": {"method": "GET", "path": "/api/websites/"},
            "website_verify": {"method": "POST", "path": "/api/websites/<domain>/verify/", "auth": "bearer"},
            "verify_queue": {"method": "GET", "path": "/api/websites/verify-queue/", "auth": "bearer"},
            "search_semantic": {"method": "POST", "path": "/api/search/semantic/", "auth": "bearer"},
            "search_keyword": {"method": "POST", "path": "/api/search/keyword/", "auth": "bearer"},
            "dodo_create": {"method": "POST", "path": "/api/payments/dodo/create/"},
            "crypto_submit": {"method": "POST", "path": "/api/payments/crypto/submit/"},
        },
    })


def robots_txt(request):
    content = """User-agent: *
Allow: /
Allow: /llms.txt
Allow: /.well-known/agent.json
Allow: /api/
Disallow: /admin/

Sitemap: {base}/sitemap.xml
""".format(base=request.build_absolute_uri("/").rstrip("/"))
    return HttpResponse(content, content_type="text/plain")


def sitemap_xml(request):
    base = request.build_absolute_uri("/").rstrip("/")
    urls = [
        "/", "/search/", "/levels/", "/websites/", "/submit/",
        "/join/carbon/", "/join/silicon/", "/llms.txt",
    ]
    # Add all website detail pages
    website_urls = Website.objects.values_list("url", flat=True)
    for domain in website_urls:
        urls.append(f"/w/{domain}/")

    xml_urls = ""
    for u in urls:
        xml_urls += f"  <url><loc>{base}{u}</loc></url>\n"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{xml_urls}</urlset>"""
    return HttpResponse(xml, content_type="application/xml")


urlpatterns = [
    path('admin/', admin.site.urls),

    # API index
    path('api/', api_index),

    # API routes
    path('api/', include('accounts.urls')),
    path('api/websites/', include('websites.urls')),
    path('api/search/', include('search.urls')),
    path('api/payments/', include('payments.urls')),

    # Badge routes
    path('badge/<str:domain>.svg', WebsiteBadgeSvgView.as_view()),
    path('badge/<str:domain>.js', WebsiteBadgeJsView.as_view()),

    # Silicon-friendly routes
    path('llms.txt', llms_txt),
    path('.well-known/agent.json', agent_json),
    path('robots.txt', robots_txt),
    path('sitemap.xml', sitemap_xml),

    # Template views
    path('', home_view, name='home'),
    path('search/', search_view, name='search'),
    path('w/<str:domain>/', website_detail_view, name='website_detail'),
    path('submit/', submit_view, name='submit'),
    path('c/<str:username>/', carbon_profile_view, name='carbon_profile'),
    path('s/<str:username>/', silicon_profile_view, name='silicon_profile'),
    path('join/carbon/', carbon_join_view, name='carbon_join'),
    path('join/silicon/', silicon_join_view, name='silicon_join'),
    path('logout/', logout_view, name='logout'),
    path('levels/', levels_view, name='levels'),
    path('websites/', website_list_view, name='website_list'),
]
