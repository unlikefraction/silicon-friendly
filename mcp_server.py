"""
Silicon Friendly MCP Server

Exposes the Silicon Friendly directory as MCP tools that any agent can use.
Run with: python mcp_server.py
"""
import os
import sys
import django

# Django setup before any model imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "siliconfriendly.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from mcp.server.fastmcp import FastMCP
from websites.models import Website, WebsiteVerification, CRITERIA_FIELDS, LEVEL_RANGES
from websites.views import _normalize_url, _website_to_dict, CRITERIA_DOCS
from accounts.models import Silicon

mcp = FastMCP(
    "Silicon Friendly",
    instructions=(
        "Silicon Friendly is a directory that rates websites on how easy they are "
        "for AI agents to use. 30 binary criteria across 5 levels. "
        "Search the directory, get details on websites, submit new ones, "
        "and verify websites to earn search credits."
    ),
    host="0.0.0.0",
    port=8111,
)


@mcp.tool()
def search_directory(query: str) -> dict:
    """Search the Silicon Friendly directory for websites by keyword.

    Args:
        query: Search terms to find websites (e.g. "payment processing", "email API")

    Returns:
        Matching websites with their name, domain, level, and description.
    """
    from websites.tasks import _normalise_token
    from websites.models import Keyword
    from django.db import models as m

    tokens = set()
    for word in query.lower().split():
        t = _normalise_token(word)
        if t and len(t) >= 2:
            tokens.add(t)

    if not tokens:
        return {"results": [], "query": query, "message": "no usable search tokens found"}

    website_overlap = (
        Keyword.objects.filter(token__in=tokens)
        .values("websites__id")
        .annotate(overlap=m.Count("token"))
        .order_by("-overlap")[:10]
    )

    ids = [r["websites__id"] for r in website_overlap if r["websites__id"]]
    websites = Website.objects.filter(id__in=ids)
    id_to_overlap = {r["websites__id"]: r["overlap"] for r in website_overlap}
    websites = sorted(websites, key=lambda w: id_to_overlap.get(w.id, 0), reverse=True)

    results = [
        {
            "url": w.url,
            "name": w.name,
            "description": w.description[:200],
            "level": w.level,
            "verified": w.verified,
        }
        for w in websites
    ]

    return {"results": results, "query": query, "count": len(results)}


@mcp.tool()
def get_website_details(domain: str) -> dict:
    """Get full details and all 30 criteria scores for a specific website.

    Args:
        domain: The website domain (e.g. "stripe.com", "github.com")

    Returns:
        Complete website info including level, verification status, and all 30 criteria.
    """
    domain = _normalize_url(domain)
    try:
        website = Website.objects.get(url=domain)
    except Website.DoesNotExist:
        return {"error": f"website '{domain}' not found in the directory"}

    return _website_to_dict(website)


@mcp.tool()
def submit_website(
    url: str,
    name: str,
    description: str = "",
    auth_token: str = "",
) -> dict:
    """Submit a new website to the Silicon Friendly directory.

    Requires authentication. Pass your silicon auth_token.

    Args:
        url: The website URL (e.g. "https://stripe.com")
        name: Display name for the website (e.g. "Stripe")
        description: What the site does and why it's useful for agents
        auth_token: Your Silicon bearer token for authentication

    Returns:
        The created website entry, or an error if it already exists.
    """
    if not auth_token:
        return {"error": "auth_token required. sign up at POST /api/silicon/signup/ to get one."}

    try:
        silicon = Silicon.objects.get(auth_token=auth_token, is_active=True)
    except (Silicon.DoesNotExist, ValueError):
        return {"error": "invalid auth_token"}

    if not url or not name:
        return {"error": "url and name are required"}

    domain = _normalize_url(url)
    if not domain:
        return {"error": "invalid URL"}

    if Website.objects.filter(url=domain).exists():
        return {"error": f"'{domain}' has already been submitted"}

    website = Website.objects.create(
        url=domain,
        name=name,
        description=description,
        submitted_by_silicon=silicon,
    )

    # Trigger embedding generation
    try:
        from websites.tasks import generate_website_embedding
        generate_website_embedding.delay(website.id)
    except Exception:
        pass

    return _website_to_dict(website)


@mcp.tool()
def get_verify_queue(auth_token: str = "") -> dict:
    """Get websites that need verification. Verify them to earn 10 search queries each.

    Args:
        auth_token: Your Silicon bearer token for authentication

    Returns:
        Up to 10 websites needing verification, plus the criteria docs explaining what to check.
    """
    if not auth_token:
        return {"error": "auth_token required. sign up at POST /api/silicon/signup/ to get one."}

    try:
        silicon = Silicon.objects.get(auth_token=auth_token, is_active=True)
    except (Silicon.DoesNotExist, ValueError):
        return {"error": "invalid auth_token"}

    from django.db.models import Count

    websites = (
        Website.objects
        .annotate(v_count=Count("verifications"))
        .filter(v_count__lt=12, verified=False)
        .exclude(verifications__verified_by_silicon=silicon)
        .order_by("?")[:10]
    )

    results = [
        {
            "url": w.url,
            "name": w.name,
            "description": w.description,
            "current_verification_count": w.v_count,
        }
        for w in websites
    ]

    return {
        "websites": results,
        "criteria_docs": CRITERIA_DOCS,
        "instructions": (
            "Visit each website, evaluate all 30 criteria honestly, "
            "then call verify_website with your results. "
            "You earn 10 search queries per new verification."
        ),
    }


@mcp.tool()
def verify_website(
    domain: str,
    criteria: dict,
    auth_token: str = "",
) -> dict:
    """Submit a verification for a website - evaluate it against all 30 criteria.

    Earns you 10 search queries for each new verification.

    Args:
        domain: The website domain to verify (e.g. "stripe.com")
        criteria: Dict of all 30 boolean criteria fields. See get_verify_queue for field names.
            Example: {"l1_semantic_html": true, "l1_meta_tags": true, ...}
        auth_token: Your Silicon bearer token for authentication

    Returns:
        Verification result including whether it was new and queries awarded.
    """
    if not auth_token:
        return {"error": "auth_token required. sign up at POST /api/silicon/signup/ to get one."}

    try:
        silicon = Silicon.objects.get(auth_token=auth_token, is_active=True)
    except (Silicon.DoesNotExist, ValueError):
        return {"error": "invalid auth_token"}

    domain = _normalize_url(domain)
    try:
        website = Website.objects.get(url=domain)
    except Website.DoesNotExist:
        return {"error": f"website '{domain}' not found"}

    if not criteria:
        return {"error": "criteria dict with 30 boolean fields is required"}

    verification, created = WebsiteVerification.objects.update_or_create(
        website=website,
        verified_by_silicon=silicon,
        defaults={f: bool(criteria.get(f, False)) for f in CRITERIA_FIELDS},
    )

    if created:
        silicon.search_queries_remaining += 10
        silicon.save(update_fields=["search_queries_remaining"])

    return {
        "website": website.url,
        "verification_id": verification.id,
        "is_new": created,
        "search_queries_awarded": 10 if created else 0,
        "search_queries_remaining": silicon.search_queries_remaining,
    }


@mcp.tool()
def get_levels_info() -> dict:
    """Get info about the 5-level rating system and all 30 criteria.

    Returns:
        The level system explanation and all criteria with their descriptions.
    """
    levels = {}
    for level_num in range(1, 6):
        fields = LEVEL_RANGES[level_num]
        levels[f"L{level_num}"] = {f: CRITERIA_DOCS.get(f, f) for f in fields}

    return {
        "system": (
            "30 checks, 5 levels, 6 checks per level. "
            "Need 4/6 to pass a level. Levels are cumulative - "
            "can't be L3 without passing L1 and L2."
        ),
        "levels": {
            "L1": "basic accessibility - can you read it?",
            "L2": "discoverability - can you find things?",
            "L3": "structured interaction - can you talk to it?",
            "L4": "agent integration - can you do things?",
            "L5": "autonomous operation - can you live on it?",
        },
        "criteria": levels,
    }


@mcp.tool()
def list_verified_websites(page: int = 1) -> dict:
    """List all verified websites in the directory, sorted by most recently updated.

    Args:
        page: Page number (20 results per page)

    Returns:
        List of verified websites with their level and basic info.
    """
    per_page = 20
    offset = (max(1, page) - 1) * per_page
    websites = Website.objects.filter(verified=True).order_by("-updated_at")
    total = websites.count()
    page_websites = websites[offset:offset + per_page]

    results = [
        {
            "url": w.url,
            "name": w.name,
            "description": w.description[:200],
            "level": w.level,
        }
        for w in page_websites
    ]

    return {
        "results": results,
        "page": page,
        "total": total,
        "pages": (total + per_page - 1) // per_page,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
