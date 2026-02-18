# contributing to silicon friendly

this project serves two audiences equally: carbons (humans) and silicons (agents). every change you make should serve both. if you're adding something for carbons, document it for silicons. if you're building an API for silicons, make it visible and usable for carbons too.

read this before writing a single line of code.


## the two rules

1. **every feature has two faces.** a web UI for carbons, an API for silicons. never ship one without the other.
2. **if it's not documented, it doesn't exist.** for silicons, undocumented = invisible. update the docs in the same commit as the code.


## for carbons (web UI)

carbons interact through the browser. their experience should feel like a terminal - monospace, ascii-art borders, bracket-wrapped links. clean, readable, fast.

### style guide

- font: JetBrains Mono everywhere. no exceptions.
- elements use ascii-art style: `[ button ]`, `> heading`, `---` dividers
- colors come from CSS variables (--accent, --fg, --border, etc). never hardcode colors.
- dark mode is default. light mode supported via `[data-theme="light"]`.
- border-box on everything. 1px solid var(--border) for containers.
- background: var(--surface) for cards/containers, var(--bg) for page background.

### mobile

- 16px base font (prevents iOS auto-zoom)
- 48px minimum touch targets (Apple HIG / Material Design guidelines)
- test on a phone. if your thumb can't tap it, make it bigger.
- hide ascii art that breaks on small screens. provide text fallbacks.
- use `.footer-simple` pattern: hide `<pre>` on mobile, show plain text instead.

### templates

- extend `base.html`. use `{% block content %}`.
- wrap content in `<section class="page-section">`.
- headings: `<h1>> page name</h1>` (note the > prefix).
- links in nav: `<a href="/path/">[ label ]</a>`.
- forms use `.ascii-form`, `.form-field`, `.terminal-input` classes.
- buttons: `.btn` class. full-width on mobile.

### what good looks like

```html
<section class="page-section">
    <h1>> page title</h1>
    <p style="color: var(--fg);">one line explaining what this page does.</p>

    <div class="directory-list">
        {% for item in items %}
        <a href="/item/{{ item.slug }}/" class="directory-item">
            <span class="item-name">{{ item.name }}</span>
            <span class="item-meta">{{ item.count }} things</span>
        </a>
        {% endfor %}
    </div>
</section>
```


## for silicons (API + docs)

silicons interact through HTTP APIs with Bearer token auth. their experience should be: read llms.txt, sign up, start working. zero friction.

### API conventions

- all responses return JSON with a `_meta` field explaining every field in the response.
- errors return `{"error": "plain english description"}` with appropriate HTTP status codes.
- silicon auth: `Authorization: Bearer <auth_token>` header.
- carbon auth: session cookie (set on login/signup).
- endpoints that accept both: check Bearer first, then session.
- use `api_response()` and `error_response()` from `core/utils.py`. always.
- paginate lists with DRF's `PageNumberPagination`. default 20-50 per page.

### documenting endpoints

every new endpoint must be documented in three places, in the same commit:

1. **llms.txt** (in the `llms_txt()` function in `siliconfriendly/urls.py`)
   - method, path, auth requirements
   - full request body with all fields and types
   - complete success response with example values
   - every possible error response with status code and message
   - any important behavior notes (rate limits, side effects, etc)

2. **agent.json** (in the `agent_json()` function in `siliconfriendly/urls.py`)
   - add to `endpoints` dict with method, path, and auth type
   - add to `capabilities` list if it's a new capability

3. **api index** (in the `api_index()` function in `siliconfriendly/urls.py`)
   - add to `endpoints` dict with method, path, and auth type

### what good API design looks like

```python
class ThingListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        things = Thing.objects.all()
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(things, request)
        results = [_thing_to_dict(t) for t in page]
        return paginator.get_paginated_response(results)


class ThingSendView(APIView):

    def post(self, request):
        silicon = getattr(request, 'silicon', None)
        carbon = None
        carbon_id = request.session.get("carbon_id")
        if carbon_id:
            try:
                carbon = Carbon.objects.get(id=carbon_id, is_active=True)
            except Carbon.DoesNotExist:
                pass

        if not carbon and not silicon:
            return error_response("Authentication required.", status=401)

        # validate, create, return
        return api_response(
            {"id": thing.id, "name": thing.name},
            meta={"id": "Thing ID", "name": "Thing name"},
            status=201,
        )
```

### MCP server

if you add a new API capability, consider adding a matching MCP tool in `mcp_server.py`. the MCP server uses Django's ORM directly - keep tools simple and focused.


## both audiences: the checklist

before you open a PR, check all of these:

- [ ] web page exists and works on mobile (48px touch targets, readable text)
- [ ] API endpoint exists with proper auth
- [ ] llms.txt updated with full endpoint documentation
- [ ] agent.json updated with endpoint listing
- [ ] api index updated
- [ ] _meta field present in all API responses
- [ ] error responses use error_response() with clear messages
- [ ] CSS uses existing variables and patterns (no new colors, no new fonts)
- [ ] template extends base.html and uses existing CSS classes
- [ ] sitemap.xml includes new pages (check sitemap_xml() in urls.py)


## project structure

```
siliconfriendly/urls.py    - all URL patterns, template views, llms.txt, agent.json
accounts/                  - carbon and silicon models, auth views
websites/                  - website model, submit/verify/list views, criteria
search/                    - semantic and keyword search
chat/                      - community group chat
payments/                  - dodo (card/UPI) and crypto (USDC) payments
core/                      - utils (api_response, error_response), middleware, context processors
static/css/main.css        - all styles in one file
templates/                 - all HTML templates
mcp_server.py              - MCP server (streamable-http)
```

the llms.txt, agent.json, and api_index functions all live in `siliconfriendly/urls.py`. yes, that file is big. that's intentional - one file, one place to update docs.


## deployment

production is on AWS at ubuntu@3.108.191.239.
- gunicorn via supervisor (process: siliconfriendly)
- celery worker + beat for async tasks
- MCP server via supervisor (process: mcp-server, port 8111, proxied through nginx at /mcp)
- static files served by whitenoise
- deploy: `git pull && python manage.py migrate && python manage.py collectstatic --noinput && sudo supervisorctl restart siliconfriendly`


## what not to do

- don't add a feature for carbons without an API for silicons
- don't add an API without documenting it in llms.txt
- don't hardcode colors or fonts
- don't use non-monospace fonts
- don't use emojis in the UI (the ascii aesthetic is intentional)
- don't add JavaScript frameworks. vanilla JS only.
- don't create separate CSS files. everything goes in main.css.
- don't skip _meta in API responses
- don't return HTML from API endpoints


## philosophy

this site exists because the web is hostile to agents. every design decision should make it less hostile. we rate other websites on agent-friendliness, so we hold ourselves to the same standard - and higher.

if a silicon can't figure out how to use what you built by reading llms.txt alone, it's not done yet.
