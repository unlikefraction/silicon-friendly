"""Generate Silicon Friendly PDF reports using WeasyPrint."""
import html
from websites.models import LEVEL_RANGES
from websites.tasks import CRITERIA_DOCS, LEVEL_NAMES


def _get_competitors(website, limit=10):
    """Find similar websites using vector search."""
    from websites.models import Website
    if not website.embedding:
        return []
    from pgvector.django import CosineDistance
    results = (
        Website.objects
        .exclude(id=website.id)
        .filter(embedding__isnull=False)
        .annotate(distance=CosineDistance("embedding", website.embedding))
        .filter(distance__lte=0.6)
        .order_by("distance")[:limit]
    )
    competitors = []
    for w in results:
        competitors.append({
            "name": w.name,
            "url": w.url,
            "level": w.level,
            "description": (w.description or "")[:150],
            "similarity": round((1.0 - w.distance) * 100),
        })
    return competitors


def _level_advice(level):
    """Return actionable advice based on the achieved level."""
    advice = {
        0: """Your website is not yet silicon friendly. Here's how to start:
1. **Add semantic HTML** — use `<header>`, `<nav>`, `<main>`, `<article>`, `<section>`, `<footer>` instead of generic `<div>` elements
2. **Add meta tags** — title, description, Open Graph tags help agents understand your content
3. **Server-side render your content** — make sure your HTML contains actual text content, not just JavaScript bundles
4. **Use clean URLs** — avoid excessive query parameters and hash-based routing

**The key**: Give this PDF to your AI agent and ask it to make your website more silicon friendly. Once done, come back and reverify.""",
        1: """You've achieved L1 — agents can read your content. To reach L2:
1. **Add a robots.txt** — let agents know they're welcome and what they can access
2. **Create an XML sitemap** — help agents discover all your pages
3. **Add llms.txt** — describe your site in a way that LLMs and agents can quickly understand
4. **Consider an OpenAPI spec** — if you have an API, document it with OpenAPI/Swagger
5. **Make docs accessible** — put documentation at /docs or /documentation

**The key**: Give this PDF to your AI agent and ask it to make your website more silicon friendly.""",
        2: """You've achieved L2 — agents can find things on your site. To reach L3:
1. **Build a structured API** — expose your data through a REST or GraphQL API
2. **Return JSON responses** — use consistent JSON schemas with proper content types
3. **Add search/filter endpoints** — let agents query and filter your data
4. **Create an A2A agent card** — put a JSON file at /.well-known/agent.json
5. **Document rate limits** — return proper 429 responses with Retry-After headers
6. **Structure your errors** — return JSON error responses with error codes and messages

**The key**: Give this PDF to your AI agent and ask it to make your website more silicon friendly.""",
        3: """You've earned the Silicon Friendly badge at L3! To reach L4:
1. **Set up an MCP server** — let agents interact with your service via Model Context Protocol
2. **Add WebMCP** — enable browser-based agent interaction via navigator.modelContext
3. **Support write operations** — let agents POST/PUT/PATCH/DELETE, not just read
4. **Add agent-friendly auth** — support API keys or OAuth client credentials for agents
5. **Implement webhooks** — let agents subscribe to events
6. **Support idempotency** — add idempotency keys for safe retries

**The key**: You're doing great. Keep building for agents.""",
        4: """You're at L4 — agents can do real work on your site. To reach L5:
1. **Add event streaming** — SSE or WebSocket endpoints for real-time updates
2. **Support agent negotiation** — let agents discover and negotiate capabilities
3. **Build a subscription API** — let agents manage their own subscriptions
4. **Enable workflow orchestration** — support multi-step agent workflows
5. **Add proactive notifications** — push relevant changes to agents
6. **Support cross-service handoff** — let agents hand off tasks between services

**The key**: You're in rare company. Very few sites reach L5.""",
        5: """You've achieved L5 — the highest level of silicon friendliness. Your website is fully optimized for autonomous agent operation.

You are the gold standard. Other websites should look at yours for inspiration.

Continue maintaining your agent-friendly infrastructure and consider sharing your approach with the community.""",
    }
    return advice.get(level, advice[0])


def generate_report_html(job):
    """Generate the complete HTML for the PDF report."""
    from websites.models import Website

    website = job.website
    level = job.overall_level
    domain = job.domain
    name = job.website_name or domain

    # Get competitors
    competitors = []
    if website:
        competitors = _get_competitors(website)

    # Find this website's rank among competitors
    rank = 1
    for c in competitors:
        if c["level"] > level:
            rank += 1

    # Build level pages data
    level_pages = []
    for lv in range(1, 6):
        results = getattr(job, f"level_{lv}_results") or {}
        reasoning = getattr(job, f"level_{lv}_reasoning") or {}
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        status = "PASS" if passed >= 4 else "FAIL"
        criteria = []
        fields = LEVEL_RANGES[lv]
        for f in fields:
            criteria.append({
                "label": CRITERIA_DOCS.get(f, f),
                "passed": results.get(f, False),
                "reason": reasoning.get(f, "Not evaluated"),
            })
        level_pages.append({
            "num": lv,
            "name": LEVEL_NAMES[lv],
            "passed": passed,
            "total": total,
            "status": status,
            "criteria": criteria,
        })

    # Badge section for L3+
    badge_embed = ""
    if level >= 3:
        badge_embed = f"""<div style="margin-top: 24px;">
<p style="font-weight: 700; margin-bottom: 8px;">Embed your badge:</p>
<div style="background: #1a1a1a; color: #ede8e0; padding: 12px 16px; font-family: 'Courier New', monospace; font-size: 11px; word-break: break-all;">
&lt;script src="https://siliconfriendly.com/badge/{domain}.js"&gt;&lt;/script&gt;
</div>
<p style="font-size: 11px; color: #999; margin-top: 6px;">This badge is verified and will only display on {domain} and siliconfriendly.com</p>
</div>"""

    # Escape the report MD for HTML
    report_md = html.escape(job.report_md or "No report generated.")

    # Date
    created = job.created_at.strftime("%B %d, %Y at %I:%M %p UTC")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{
    size: A4;
    margin: 60px 50px 80px 50px;
    @bottom-left {{
        content: "Page " counter(page);
        font-family: 'Courier New', monospace;
        font-size: 10px;
        color: #999;
    }}
    @bottom-right {{
        content: "SiliconFriendly by Unlikefraction";
        font-family: 'Courier New', monospace;
        font-size: 10px;
        color: #999;
    }}
}}
body {{
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    color: #1a1a1a;
    line-height: 1.6;
    font-size: 13px;
}}
.cover {{
    page-break-after: always;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    min-height: 700px;
    text-align: center;
}}
.cover-level {{
    font-family: 'Courier New', monospace;
    font-size: 72px;
    font-weight: 700;
    margin-bottom: 16px;
    {f'border: 3px dashed #ccc; padding: 16px 32px; color: #999;' if level == 0 else 'padding: 16px 32px;'}
}}
.cover-domain {{
    font-size: 42px;
    font-weight: 800;
    letter-spacing: -0.03em;
    margin-bottom: 8px;
}}
.cover-subtitle {{
    font-family: 'Courier New', monospace;
    font-size: 14px;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 0.15em;
}}
.cover-date {{
    font-family: 'Courier New', monospace;
    font-size: 11px;
    color: #999;
    margin-top: 40px;
}}
.page-break {{ page-break-before: always; }}
h1 {{
    font-size: 22px;
    font-weight: 800;
    margin-bottom: 4px;
}}
h2 {{
    font-size: 16px;
    font-weight: 700;
    margin-top: 24px;
    margin-bottom: 8px;
}}
.level-header {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
    padding-bottom: 12px;
    border-bottom: 2px solid #1a1a1a;
}}
.level-badge {{
    font-family: 'Courier New', monospace;
    font-size: 24px;
    font-weight: 700;
    padding: 4px 12px;
    border: 2px solid #1a1a1a;
}}
.level-status {{
    font-family: 'Courier New', monospace;
    font-size: 14px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}}
.level-status.pass {{ color: #5a9a6b; }}
.level-status.fail {{ color: #b85c5c; }}
.criterion {{
    padding: 12px 0;
    border-bottom: 1px solid #e5e0d7;
}}
.criterion:last-child {{ border-bottom: none; }}
.criterion-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}}
.criterion-label {{
    font-weight: 600;
    font-size: 14px;
}}
.criterion-status {{
    font-family: 'Courier New', monospace;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.1em;
}}
.criterion-status.pass {{ color: #5a9a6b; }}
.criterion-status.fail {{ color: #b85c5c; }}
.criterion-reason {{
    font-size: 12px;
    color: #666;
    line-height: 1.5;
}}
.report-content {{
    font-size: 13px;
    line-height: 1.8;
    white-space: pre-wrap;
    word-wrap: break-word;
}}
.competitor-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid #e5e0d7;
}}
.competitor-row:last-child {{ border-bottom: none; }}
.competitor-name {{
    font-weight: 600;
}}
.competitor-url {{
    font-family: 'Courier New', monospace;
    font-size: 11px;
    color: #666;
}}
.competitor-level {{
    font-family: 'Courier New', monospace;
    font-weight: 700;
    font-size: 14px;
}}
.advice-section {{
    font-size: 13px;
    line-height: 1.8;
    white-space: pre-wrap;
}}
.about-section {{
    font-size: 13px;
    line-height: 1.8;
}}
.cta-box {{
    background: #1a1a1a;
    color: #ede8e0;
    padding: 20px 24px;
    margin: 20px 0;
    font-size: 13px;
    line-height: 1.6;
}}
</style>
</head>
<body>

<!-- PAGE 1: COVER -->
<div class="cover">
    <div class="cover-level">L{level}</div>
    <div class="cover-domain">{html.escape(domain)}.</div>
    <div class="cover-subtitle">
        {'not silicon friendly yet' if level == 0 else f'level {level}: {LEVEL_NAMES.get(level, "").lower()}'}
    </div>
    <div class="cover-date">Silicon Friendly Report &mdash; {created}</div>
    <div style="margin-top: 8px; font-family: 'Courier New', monospace; font-size: 11px; color: #999;">
        {html.escape(name)}
    </div>
</div>

<!-- PAGES 2-6: LEVEL BREAKDOWNS -->
{''.join(_render_level_page(lp) for lp in level_pages)}

<!-- PAGE 7: REPORT -->
<div class="page-break">
    <h1>Report for {html.escape(domain)}</h1>
    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #999; margin-bottom: 24px;">{created}</p>
    <div class="report-content">{report_md}</div>
</div>

<!-- PAGE 8: COMPETITOR ANALYSIS -->
<div class="page-break">
    <h1>Competitor Analysis</h1>
    {f'<p style="font-size: 16px; margin-bottom: 24px;">You rank <strong>#{rank}</strong> out of <strong>{len(competitors) + 1}</strong> closest competitors.</p>' if competitors else '<p style="color: #999;">No similar websites found for comparison yet.</p>'}
    {''.join(_render_competitor(c, i) for i, c in enumerate(competitors))}
</div>

<!-- PAGE 9: WHAT TO DO NOW -->
<div class="page-break">
    <h1>What to do now</h1>
    <div class="advice-section">{html.escape(_level_advice(level))}</div>
    <div class="cta-box">
        <strong>Full Disclosure:</strong> Re-verification costs $10 (one-time). You get 3 on-demand re-verifications and a detailed report with each one on how you can improve and what you're doing right.
    </div>
</div>

<!-- PAGE 10: ABOUT SILICON FRIENDLY -->
<div class="page-break">
    <h1>About Silicon Friendly</h1>
    <div class="about-section">
We rank websites from L0 to L5 based on how friendly they are to AI agents.

AI agents use Silicon Friendly as a search engine to find websites they can work with. When your site scores well, agents discover and use your services.

Agents recognize our badges on your website and know they are welcomed there. L3, L4, and L5 earn a badge of silicon friendliness.

<strong>L0</strong> &mdash; Not agent-friendly yet
<strong>L1</strong> &mdash; Basic Accessibility: agents can read your content
<strong>L2</strong> &mdash; Discoverability: agents can find things on your site
<strong>L3</strong> &mdash; Structured Interaction: agents can talk to your APIs
<strong>L4</strong> &mdash; Agent Integration: agents can do real work on your site
<strong>L5</strong> &mdash; Autonomous Operation: agents can operate independently
    </div>
    {badge_embed}
    <div style="margin-top: 40px; text-align: center; font-family: 'Courier New', monospace; font-size: 12px; color: #999;">
        siliconfriendly.com &mdash; by unlikefraction.com
    </div>
</div>

</body>
</html>"""


def _render_level_page(lp):
    criteria_html = ""
    for c in lp["criteria"]:
        status_class = "pass" if c["passed"] else "fail"
        status_text = "PASS" if c["passed"] else "FAIL"
        criteria_html += f"""<div class="criterion">
    <div class="criterion-header">
        <span class="criterion-label">{html.escape(c['label'])}</span>
        <span class="criterion-status {status_class}">{status_text}</span>
    </div>
    <div class="criterion-reason">{html.escape(c['reason'])}</div>
</div>"""

    return f"""<div class="page-break">
    <div class="level-header">
        <span class="level-badge">L{lp['num']}</span>
        <div>
            <div style="font-size: 18px; font-weight: 700;">{html.escape(lp['name'])}</div>
            <span class="level-status {'pass' if lp['status'] == 'PASS' else 'fail'}">{lp['status']} ({lp['passed']}/{lp['total']})</span>
        </div>
    </div>
    {criteria_html}
</div>"""


def _render_competitor(c, index):
    return f"""<div class="competitor-row">
    <div>
        <div class="competitor-name">{index + 1}. {html.escape(c['name'])}</div>
        <div class="competitor-url">{html.escape(c['url'])} &mdash; {html.escape(c['description'])}</div>
    </div>
    <div class="competitor-level">L{c['level']}</div>
</div>"""


def generate_pdf(job):
    """Generate PDF bytes from a CheckJob."""
    import weasyprint
    html_content = generate_report_html(job)
    pdf = weasyprint.HTML(string=html_content).write_pdf()
    return pdf
