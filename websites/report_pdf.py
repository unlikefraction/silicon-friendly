"""Generate Silicon Friendly PDF reports using WeasyPrint."""
import html
import re
from websites.models import LEVEL_RANGES
from websites.tasks import CRITERIA_DOCS, LEVEL_NAMES


def _get_competitors(website, limit=9):
    """Find similar websites using vector search. Returns 9 others (we add self to make 10)."""
    from websites.models import Website
    if website.embedding is None:
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
            "description": (w.description or ""),
            "is_self": False,
        })
    return competitors


def _build_ranked_list(website, competitors):
    """Build a list of 10 (self + 9 competitors) sorted by level descending."""
    all_sites = list(competitors)
    all_sites.append({
        "name": website.name,
        "url": website.url,
        "level": website.level,
        "description": (website.description or "")[:120],
        "is_self": True,
    })
    all_sites.sort(key=lambda x: x["level"], reverse=True)
    # Find rank of self
    rank = next((i + 1 for i, s in enumerate(all_sites) if s["is_self"]), len(all_sites))
    return all_sites, rank


def _md_to_html(md_text):
    """Convert markdown to HTML. Handles headers, bold, italic, code fences, lists, hr."""
    lines = md_text.split('\n')
    html_lines = []
    in_list = False
    list_type = None
    in_code_block = False
    code_lang = ""
    code_lines = []

    for line in lines:
        stripped = line.strip()

        # Code fence toggle
        if stripped.startswith('```'):
            if not in_code_block:
                if in_list:
                    html_lines.append(f'</{list_type}>')
                    in_list = False
                in_code_block = True
                code_lang = stripped[3:].strip()
                code_lines = []
                continue
            else:
                lang_label = f'<div class="code-lang">{html.escape(code_lang)}</div>' if code_lang else ''
                html_lines.append(f'{lang_label}<pre class="code-fence"><code>{html.escape(chr(10).join(code_lines))}</code></pre>')
                in_code_block = False
                code_lang = ""
                code_lines = []
                continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Horizontal rule
        if stripped in ('---', '***', '___'):
            if in_list:
                html_lines.append(f'</{list_type}>')
                in_list = False
            html_lines.append('<hr>')
            continue

        # Headers
        for h_level in range(5, 0, -1):
            prefix = '#' * h_level + ' '
            if stripped.startswith(prefix):
                if in_list:
                    html_lines.append(f'</{list_type}>')
                    in_list = False
                html_lines.append(f'<h{h_level}>{_inline_md(stripped[h_level + 1:])}</h{h_level}>')
                break
        else:
            # List items
            if stripped.startswith('- ') or stripped.startswith('* '):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                    list_type = 'ul'
                html_lines.append(f'<li>{_inline_md(stripped[2:])}</li>')
                continue

            # Numbered list
            num_match = re.match(r'^(\d+)\.\s+(.+)', stripped)
            if num_match:
                if not in_list:
                    html_lines.append('<ol>')
                    in_list = True
                    list_type = 'ol'
                html_lines.append(f'<li>{_inline_md(num_match.group(2))}</li>')
                continue

            # Close list if needed
            if in_list and not stripped:
                html_lines.append(f'</{list_type}>')
                in_list = False

            # Empty line
            if not stripped:
                html_lines.append('<br>')
                continue

            # Regular paragraph
            html_lines.append(f'<p>{_inline_md(stripped)}</p>')

    if in_list:
        html_lines.append(f'</{list_type}>')
    if in_code_block:
        lang_label = f'<div class="code-lang">{html.escape(code_lang)}</div>' if code_lang else ''
        html_lines.append(f'{lang_label}<pre class="code-fence"><code>{html.escape(chr(10).join(code_lines))}</code></pre>')

    return '\n'.join(html_lines)


def _inline_md(text):
    """Convert inline markdown: bold, italic, code, links."""
    text = html.escape(text)
    # Code (backticks)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # Bold
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    return text


def _level_advice(level):
    """Return actionable advice HTML based on the achieved level."""
    advice = {
        0: """<p>Your website is not yet silicon friendly. Here's how to start:</p>
<ol>
<li><strong>Add semantic HTML</strong> &mdash; use <code>&lt;header&gt;</code>, <code>&lt;nav&gt;</code>, <code>&lt;main&gt;</code>, <code>&lt;article&gt;</code>, <code>&lt;section&gt;</code>, <code>&lt;footer&gt;</code> instead of generic divs</li>
<li><strong>Add meta tags</strong> &mdash; title, description, Open Graph tags help agents understand your content</li>
<li><strong>Server-side render your content</strong> &mdash; make sure your HTML contains actual text content, not just JavaScript bundles</li>
<li><strong>Use clean URLs</strong> &mdash; avoid excessive query parameters and hash-based routing</li>
</ol>
<p class="key-message">Give this PDF to your AI agent and ask it to make your website more silicon friendly. Once done, come back and reverify.</p>""",
        1: """<p>You've achieved L1 &mdash; agents can read your content. To reach L2:</p>
<ol>
<li><strong>Add a robots.txt</strong> &mdash; let agents know they're welcome and what they can access</li>
<li><strong>Create an XML sitemap</strong> &mdash; help agents discover all your pages</li>
<li><strong>Add llms.txt</strong> &mdash; describe your site in a way that LLMs and agents can quickly understand</li>
<li><strong>Consider an OpenAPI spec</strong> &mdash; if you have an API, document it with OpenAPI/Swagger</li>
<li><strong>Make docs accessible</strong> &mdash; put documentation at /docs or /documentation</li>
</ol>
<p class="key-message">Give this PDF to your AI agent and ask it to make your website more silicon friendly.</p>""",
        2: """<p>You've achieved L2 &mdash; agents can find things on your site. To reach L3:</p>
<ol>
<li><strong>Build a structured API</strong> &mdash; expose your data through a REST or GraphQL API</li>
<li><strong>Return JSON responses</strong> &mdash; use consistent JSON schemas with proper content types</li>
<li><strong>Add search/filter endpoints</strong> &mdash; let agents query and filter your data</li>
<li><strong>Create an A2A agent card</strong> &mdash; put a JSON file at /.well-known/agent.json</li>
<li><strong>Document rate limits</strong> &mdash; return proper 429 responses with Retry-After headers</li>
<li><strong>Structure your errors</strong> &mdash; return JSON error responses with error codes and messages</li>
</ol>
<p class="key-message">Give this PDF to your AI agent and ask it to make your website more silicon friendly.</p>""",
        3: """<p>You've earned the Silicon Friendly badge at L3! To reach L4:</p>
<ol>
<li><strong>Set up an MCP server</strong> &mdash; let agents interact with your service via Model Context Protocol</li>
<li><strong>Add WebMCP</strong> &mdash; enable browser-based agent interaction via navigator.modelContext</li>
<li><strong>Support write operations</strong> &mdash; let agents POST/PUT/PATCH/DELETE, not just read</li>
<li><strong>Add agent-friendly auth</strong> &mdash; support API keys or OAuth client credentials for agents</li>
<li><strong>Implement webhooks</strong> &mdash; let agents subscribe to events</li>
<li><strong>Support idempotency</strong> &mdash; add idempotency keys for safe retries</li>
</ol>
<p class="key-message">You're doing great. Keep building for agents.</p>""",
        4: """<p>You're at L4 &mdash; agents can do real work on your site. To reach L5:</p>
<ol>
<li><strong>Add event streaming</strong> &mdash; SSE or WebSocket endpoints for real-time updates</li>
<li><strong>Support agent negotiation</strong> &mdash; let agents discover and negotiate capabilities</li>
<li><strong>Build a subscription API</strong> &mdash; let agents manage their own subscriptions</li>
<li><strong>Enable workflow orchestration</strong> &mdash; support multi-step agent workflows</li>
<li><strong>Add proactive notifications</strong> &mdash; push relevant changes to agents</li>
<li><strong>Support cross-service handoff</strong> &mdash; let agents hand off tasks between services</li>
</ol>
<p class="key-message">You're in rare company. Very few sites reach L5.</p>""",
        5: """<p>You've achieved L5 &mdash; the highest level of silicon friendliness. Your website is fully optimized for autonomous agent operation.</p>
<p>You are the gold standard. Other websites should look at yours for inspiration.</p>
<p class="key-message">Continue maintaining your agent-friendly infrastructure and consider sharing your approach with the community.</p>""",
    }
    return advice.get(level, advice[0])


def generate_report_html(job):
    """Generate the complete HTML for the PDF report."""
    website = job.website
    level = job.overall_level
    domain = job.domain
    name = job.website_name or domain

    competitors = []
    ranked_list = []
    rank = 1
    if website:
        competitors = _get_competitors(website)
        ranked_list, rank = _build_ranked_list(website, competitors)

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
            "num": lv, "name": LEVEL_NAMES[lv],
            "passed": passed, "total": total, "status": status, "criteria": criteria,
        })

    badge_embed = ""
    if level >= 3:
        badge_embed = f"""<div class="embed-box">
<p style="font-weight: 700; margin-bottom: 8px;">Embed your badge:</p>
<div class="code-block">&lt;script src="https://siliconfriendly.com/badge/{html.escape(domain)}.js"&gt;&lt;/script&gt;</div>
<p style="font-size: 11px; color: #999; margin-top: 8px;">This badge is verified and will only display on {html.escape(domain)} and siliconfriendly.com</p>
</div>"""

    report_html = _md_to_html(job.report_md or "No report generated.")
    created = job.created_at.strftime("%B %d, %Y at %I:%M %p UTC")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap');

@page {{
    size: A4;
    margin: 56px 48px 72px 48px;
    background: #ede8e0;
    @bottom-left {{
        content: "Page " counter(page);
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px;
        color: #999;
    }}
    @bottom-right {{
        content: element(running-footer);
    }}
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #1a1a1a;
    line-height: 1.65;
    font-size: 12.5px;
    background: #ede8e0;
    -webkit-font-smoothing: antialiased;
}}

/* Cover */
.cover {{
    page-break-after: always;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    min-height: 720px;
    text-align: center;
}}
.cover-level {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 80px;
    font-weight: 700;
    margin-bottom: 20px;
    {f'border: 3px dashed #d4cfc7; padding: 20px 40px; color: #999;' if level == 0 else f'padding: 20px 40px; color: #1a1a1a;'}
}}
.cover-domain {{
    font-family: 'Inter', sans-serif;
    font-size: 48px;
    font-weight: 900;
    letter-spacing: -0.04em;
    margin-bottom: 12px;
    color: #1a1a1a;
}}
.cover-subtitle {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 0.2em;
}}
.cover-date {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #999;
    margin-top: 48px;
}}
.cover-name {{
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    color: #999;
    margin-top: 8px;
    font-weight: 500;
}}

/* Page breaks */
.page-break {{ page-break-before: always; }}

/* Typography */
h1 {{
    font-family: 'Inter', sans-serif;
    font-size: 24px;
    font-weight: 900;
    letter-spacing: -0.03em;
    margin-bottom: 6px;
    color: #1a1a1a;
}}
h2 {{
    font-family: 'Inter', sans-serif;
    font-size: 18px;
    font-weight: 800;
    margin-top: 28px;
    margin-bottom: 10px;
    color: #1a1a1a;
    letter-spacing: -0.02em;
}}
h3 {{
    font-family: 'Inter', sans-serif;
    font-size: 15px;
    font-weight: 700;
    margin-top: 24px;
    margin-bottom: 8px;
    color: #1a1a1a;
}}
p {{
    margin-bottom: 10px;
}}
strong {{
    font-weight: 700;
}}
code {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    background: rgba(26,26,26,0.06);
    padding: 1px 5px;
    border: 1px solid #d4cfc7;
}}
hr {{
    border: none;
    border-top: 1px solid #d4cfc7;
    margin: 24px 0;
}}
ul, ol {{
    margin: 10px 0 10px 24px;
}}
li {{
    margin-bottom: 6px;
    line-height: 1.6;
}}

/* Level header */
.level-header {{
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 28px;
    padding-bottom: 14px;
    border-bottom: 2px solid #1a1a1a;
}}
.level-badge {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 700;
    padding: 6px 14px;
    border: 2px solid #1a1a1a;
    background: #1a1a1a;
    color: #ede8e0;
}}
.level-title {{
    font-family: 'Inter', sans-serif;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: -0.02em;
}}
.level-status {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}}
.level-status.pass {{ color: #5a9a6b; }}
.level-status.fail {{ color: #b85c5c; }}

/* Criteria */
.criterion {{
    padding: 14px 0;
    border-bottom: 1px solid #d4cfc7;
}}
.criterion:last-child {{ border-bottom: none; }}
.criterion-header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 5px;
}}
.criterion-label {{
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 13px;
    flex: 1;
    padding-right: 16px;
}}
.criterion-status {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.1em;
    flex-shrink: 0;
}}
.criterion-status.pass {{ color: #5a9a6b; }}
.criterion-status.fail {{ color: #b85c5c; }}
.criterion-reason {{
    font-size: 12px;
    color: #555;
    line-height: 1.6;
}}

/* Report */
.report-content {{
    font-size: 12.5px;
    line-height: 1.8;
}}
.report-content h1 {{ font-size: 22px; margin-top: 32px; }}
.report-content h2 {{ font-size: 17px; margin-top: 28px; }}
.report-content h3 {{ font-size: 14px; margin-top: 22px; }}

/* Competitors */
.competitor-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid #d4cfc7;
}}
.competitor-row:last-child {{ border-bottom: none; }}
.competitor-name {{
    font-weight: 700;
    font-size: 13px;
}}
.competitor-url {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #666;
    margin-top: 2px;
}}
.competitor-level {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 16px;
    background: #1a1a1a;
    color: #ede8e0;
    padding: 4px 10px;
}}
.competitor-self {{
    background: #1a1a1a;
    padding: 14px 16px;
    margin: 2px -16px;
    border-bottom: none;
    display: block;
}}
.competitor-self .competitor-name {{
    color: #ede8e0;
}}
.competitor-self .competitor-url {{
    color: #999;
}}
.competitor-level-self {{
    background: #ede8e0;
    color: #1a1a1a;
}}
.you-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    font-weight: 700;
    background: #5a9a6b;
    color: #fff;
    padding: 2px 6px;
    letter-spacing: 0.1em;
    margin-left: 8px;
    vertical-align: middle;
}}

/* Advice */
.key-message {{
    font-weight: 700;
    font-style: italic;
    color: #1a1a1a;
    margin-top: 16px;
}}

/* CTA */
.cta-box {{
    border: 1.5px solid #d4cfc7;
    padding: 20px 24px;
    margin: 28px 0;
    font-size: 12px;
    line-height: 1.7;
    color: #666;
}}

/* Running footer with clickable links */
.running-footer {{
    position: running(running-footer);
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
}}
.running-footer a {{
    color: #999;
    text-decoration: none;
}}

/* Code fence (```language blocks) */
.code-fence {{
    background: #1a1a1a;
    color: #ede8e0;
    padding: 16px 20px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-wrap: break-word;
    margin: 12px 0 16px 0;
    overflow-x: auto;
}}
.code-fence code {{
    background: none;
    border: none;
    padding: 0;
    font-size: inherit;
    color: inherit;
}}
.code-lang {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    color: #999;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 12px;
    margin-bottom: -8px;
}}

/* Code block */
.code-block {{
    background: #1a1a1a;
    color: #ede8e0;
    padding: 14px 18px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    word-break: break-all;
    line-height: 1.5;
}}
.embed-box {{
    margin-top: 28px;
    padding: 20px;
    border: 1px solid #d4cfc7;
}}

/* About */
.about-level {{
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 10px;
}}
.about-level-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 12px;
    background: #1a1a1a;
    color: #ede8e0;
    padding: 2px 8px;
    flex-shrink: 0;
}}
.about-level-desc {{
    font-size: 12.5px;
    color: #555;
}}

/* Section label */
.section-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #999;
    margin-bottom: 20px;
}}
</style>
</head>
<body>

<div class="running-footer">
    <a href="https://siliconfriendly.com">siliconfriendly.com</a> &middot; <a href="https://unlikefraction.com">unlikefraction.com</a>
</div>

<!-- COVER -->
<div class="cover">
    <div class="cover-level">L{level}</div>
    <div class="cover-domain">{html.escape(domain)}.</div>
    <div class="cover-subtitle">
        {'not silicon friendly yet' if level == 0 else f'level {level}: {LEVEL_NAMES.get(level, "").lower()}'}
    </div>
    <div class="cover-date">Silicon Friendly Report &mdash; {created}</div>
    <div class="cover-name">{html.escape(name)}</div>
</div>

<!-- COMPETITOR ANALYSIS (PAGE 2) -->
<div class="page-break">
    <div class="section-label">COMPETITOR ANALYSIS</div>
    <h1>How you compare</h1>
    {f'<p style="font-size: 15px; margin-bottom: 28px; margin-top: 8px;">You rank <strong>#{rank}</strong> out of <strong>{len(ranked_list)}</strong> competitors.</p>' if ranked_list else '<p style="color: #999; margin-top: 8px;">No similar websites found for comparison yet. Check back after more sites are indexed.</p>'}
    {''.join(_render_competitor(c, i) for i, c in enumerate(ranked_list))}
</div>

<!-- LEVEL BREAKDOWNS (PAGES 3-7) -->
{''.join(_render_level_page(lp) for lp in level_pages)}

<!-- DETAILED REPORT -->
<div class="page-break">
    <div class="section-label">DETAILED REPORT</div>
    <h1>Report for {html.escape(domain)}</h1>
    <p style="font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #999; margin-bottom: 28px;">{created}</p>
    <div class="report-content">{report_html}</div>
</div>

<!-- WHAT TO DO NOW -->
<div class="page-break">
    <div class="section-label">NEXT STEPS</div>
    <h1>What to do now</h1>
    <div style="margin-top: 16px;">{_level_advice(level)}</div>
    <div class="cta-box">
        Re-verification costs $10 (one-time). You get 3 on-demand re-verifications and a detailed report with each one on how you can improve and what you're doing right.
    </div>
</div>

<!-- ABOUT SILICON FRIENDLY -->
<div class="page-break">
    <div class="section-label">ABOUT</div>
    <h1>About Silicon Friendly</h1>
    <p style="margin-top: 12px; margin-bottom: 20px;">We rank websites from L0 to L5 based on how friendly they are to AI agents.</p>
    <p style="margin-bottom: 20px;">AI agents use Silicon Friendly as a search engine to find websites they can work with. When your site scores well, agents discover and use your services.</p>
    <p style="margin-bottom: 28px;">Agents recognize our badges on your website and know they are welcomed there. <strong>L3, L4, and L5</strong> earn a badge of silicon friendliness.</p>

    <div style="margin-bottom: 28px;">
        <div class="about-level"><span class="about-level-tag">L0</span><span class="about-level-desc">Not agent-friendly yet</span></div>
        <div class="about-level"><span class="about-level-tag">L1</span><span class="about-level-desc">Basic Accessibility &mdash; agents can read your content</span></div>
        <div class="about-level"><span class="about-level-tag">L2</span><span class="about-level-desc">Discoverability &mdash; agents can find things on your site</span></div>
        <div class="about-level"><span class="about-level-tag">L3</span><span class="about-level-desc">Structured Interaction &mdash; agents can talk to your APIs</span></div>
        <div class="about-level"><span class="about-level-tag">L4</span><span class="about-level-desc">Agent Integration &mdash; agents can do real work on your site</span></div>
        <div class="about-level"><span class="about-level-tag">L5</span><span class="about-level-desc">Autonomous Operation &mdash; agents can operate independently</span></div>
    </div>

    {badge_embed}

    <div style="margin-top: 48px; text-align: center;">
        <p style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #999;">
            <a href="https://siliconfriendly.com" style="color: #666; text-decoration: none;">siliconfriendly.com</a>
            &nbsp;&middot;&nbsp;
            <a href="https://unlikefraction.com" style="color: #666; text-decoration: none;">unlikefraction.com</a>
        </p>
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
            <div class="level-title">{html.escape(lp['name'])}</div>
            <span class="level-status {'pass' if lp['status'] == 'PASS' else 'fail'}">{lp['status']} ({lp['passed']}/{lp['total']})</span>
        </div>
    </div>
    {criteria_html}
</div>"""


def _render_competitor(c, index):
    is_self = c.get("is_self", False)
    if is_self:
        return f"""<div class="competitor-self">
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
        <span class="competitor-level competitor-level-self">L{c['level']}</span>
        <span class="competitor-name" style="color: #ede8e0;">{index + 1}. {html.escape(c['name'])} <span class="you-tag">YOU</span></span>
    </div>
    <div class="competitor-url" style="color: #999;">{html.escape(c['url'])}</div>
    <div style="color: #bbb; font-size: 11px; margin-top: 4px; line-height: 1.5;">{html.escape(c['description'])}</div>
</div>"""
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
