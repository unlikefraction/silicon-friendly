import requests
import re
import json
from urllib.parse import urlparse
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt


USER_AGENT = "SiliconFriendly/1.0 (+https://siliconfriendly.com)"
TIMEOUT = 10


def _normalize_domain(domain):
    """Strip protocol, path, trailing slash -> domain only."""
    domain = domain.strip().lower()
    domain = re.sub(r'^https?://', '', domain)
    domain = domain.split('/')[0]
    domain = domain.rstrip('.')
    return domain


def _fetch(url, timeout=TIMEOUT, allow_redirects=True):
    """Fetch a URL with standard headers. Returns response or None."""
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=allow_redirects)
        return resp
    except requests.exceptions.SSLError:
        # Try http fallback
        if url.startswith("https://"):
            try:
                fallback = "http://" + url[len("https://"):]
                return requests.get(fallback, headers=headers, timeout=timeout, allow_redirects=allow_redirects)
            except Exception:
                return None
    except Exception:
        return None


def _strip_tags(html):
    """Remove HTML tags and return plain text."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _extract_body(html):
    """Extract content inside <body> tags."""
    match = re.search(r'<body[^>]*>(.*?)</body>', html, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1)
    return html


# ---------------------------------------------------------------------------
# L1 checks
# ---------------------------------------------------------------------------

def check_l1_semantic_html(html):
    """Check for presence of semantic HTML tags."""
    try:
        semantic_tags = ['header', 'nav', 'main', 'article', 'section', 'footer']
        found = [tag for tag in semantic_tags if re.search(rf'<{tag}[\s>]', html, re.IGNORECASE)]
        return {
            "pass": len(found) >= 3,
            "detail": f"Found: {', '.join(found)}" if found else "No semantic HTML tags found",
        }
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l1_meta_tags(html):
    """Check for title, description, and og: meta tags."""
    try:
        found = []
        if re.search(r'<title[^>]*>.+?</title>', html, re.IGNORECASE | re.DOTALL):
            found.append("title")
        if re.search(r'<meta\s+[^>]*name=["\']description["\']', html, re.IGNORECASE):
            found.append("description")
        og_tags = re.findall(r'<meta\s+[^>]*property=["\']og:(\w+)["\']', html, re.IGNORECASE)
        for og in og_tags:
            found.append(f"og:{og}")
        return {
            "pass": len(found) >= 2,
            "detail": f"Found: {', '.join(found)}" if found else "No meta tags found",
        }
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l1_schema_org(html):
    """Check for JSON-LD structured data."""
    try:
        has_jsonld = bool(re.search(r'<script\s+[^>]*type=["\']application/ld\+json["\']', html, re.IGNORECASE))
        return {
            "pass": has_jsonld,
            "detail": "Found application/ld+json script" if has_jsonld else "No JSON-LD structured data found",
        }
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l1_no_captcha(html):
    """Check that no captcha systems are present."""
    try:
        captcha_indicators = ['recaptcha', 'hcaptcha', 'cf-turnstile', 'challenge-platform']
        found = [c for c in captcha_indicators if c.lower() in html.lower()]
        return {
            "pass": len(found) == 0,
            "detail": "No captcha detected" if not found else f"Captcha detected: {', '.join(found)}",
        }
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l1_ssr_content(html):
    """Check if the page has substantial server-rendered text content."""
    try:
        body = _extract_body(html)
        text = _strip_tags(body)
        length = len(text)
        passed = length > 100
        return {
            "pass": passed,
            "detail": f"Body text length: {length} chars" if passed else f"Insufficient SSR content ({length} chars, need >100)",
        }
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l1_clean_urls(html):
    """Check if most links on the page use clean URLs."""
    try:
        hrefs = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if not hrefs:
            return {"pass": True, "detail": "No links found to evaluate"}

        clean_count = 0
        total_evaluated = 0
        for href in hrefs:
            # Skip anchors, javascript:, mailto:, tel:
            if href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            total_evaluated += 1
            parsed = urlparse(href)
            # Excessive query params: more than 2
            query_params = parsed.query.count('=') if parsed.query else 0
            # Hash-based routing: fragment that looks like a path
            hash_routing = parsed.fragment.startswith('/') if parsed.fragment else False
            if query_params <= 2 and not hash_routing:
                clean_count += 1

        if total_evaluated == 0:
            return {"pass": True, "detail": "No evaluable links found"}

        ratio = clean_count / total_evaluated
        passed = ratio >= 0.7
        return {
            "pass": passed,
            "detail": f"{clean_count}/{total_evaluated} links are clean ({ratio:.0%})",
        }
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


# ---------------------------------------------------------------------------
# L2 checks
# ---------------------------------------------------------------------------

def check_l2_robots_txt(base_url):
    """Check for a valid robots.txt."""
    try:
        resp = _fetch(f"{base_url}/robots.txt")
        if resp and resp.status_code == 200 and "User-agent" in resp.text:
            return {"pass": True, "detail": "robots.txt found and contains User-agent directive"}
        return {"pass": False, "detail": "robots.txt not found or invalid"}
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l2_sitemap(base_url):
    """Check for a valid sitemap.xml."""
    try:
        resp = _fetch(f"{base_url}/sitemap.xml")
        if resp and resp.status_code == 200:
            text = resp.text
            if "<urlset" in text or "<sitemapindex" in text:
                return {"pass": True, "detail": "sitemap.xml found with valid content"}
        return {"pass": False, "detail": "sitemap.xml not found or invalid"}
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l2_llms_txt(base_url):
    """Check for llms.txt file."""
    try:
        resp = _fetch(f"{base_url}/llms.txt")
        if resp and resp.status_code == 200 and len(resp.text.strip()) > 0:
            return {"pass": True, "detail": f"llms.txt found ({len(resp.text)} chars)"}
        return {"pass": False, "detail": "llms.txt not found"}
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l2_openapi_spec(base_url):
    """Check for OpenAPI/Swagger specification."""
    try:
        paths = ["/openapi.json", "/swagger.json", "/api-docs"]
        for path in paths:
            resp = _fetch(f"{base_url}{path}")
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    if "openapi" in data or "swagger" in data:
                        return {"pass": True, "detail": f"OpenAPI spec found at {path}"}
                except (json.JSONDecodeError, ValueError):
                    continue
        return {"pass": False, "detail": "No OpenAPI/Swagger spec found"}
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l2_documentation(base_url):
    """Check for documentation pages."""
    try:
        paths = ["/docs", "/documentation", "/api/docs"]
        for path in paths:
            resp = _fetch(f"{base_url}{path}")
            if resp and resp.status_code == 200:
                return {"pass": True, "detail": f"Documentation found at {path}"}
        return {"pass": False, "detail": "No documentation endpoint found"}
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l2_text_content(html):
    """Check text-to-HTML ratio."""
    try:
        total_html_len = len(html)
        if total_html_len == 0:
            return {"pass": False, "detail": "Empty HTML"}
        text = _strip_tags(html)
        text_len = len(text)
        ratio = text_len / total_html_len
        passed = ratio > 0.1
        return {
            "pass": passed,
            "detail": f"Text/HTML ratio: {ratio:.2%} ({text_len}/{total_html_len} chars)",
        }
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


# ---------------------------------------------------------------------------
# L3 checks
# ---------------------------------------------------------------------------

def check_l3_a2a_agent_card(base_url):
    """Check for A2A agent card at /.well-known/agent.json."""
    try:
        resp = _fetch(f"{base_url}/.well-known/agent.json")
        if resp and resp.status_code == 200:
            try:
                resp.json()
                return {"pass": True, "detail": "Agent card found at /.well-known/agent.json"}
            except (json.JSONDecodeError, ValueError):
                return {"pass": False, "detail": "/.well-known/agent.json exists but is not valid JSON"}
        return {"pass": False, "detail": "No agent card found"}
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l3_structured_api(base_url):
    """Check if /api/ path exists."""
    try:
        resp = _fetch(f"{base_url}/api/")
        if resp and resp.status_code in (200, 401, 403):
            return {"pass": True, "detail": f"/api/ returned status {resp.status_code}"}
        # Also try without trailing slash
        resp = _fetch(f"{base_url}/api")
        if resp and resp.status_code in (200, 401, 403):
            return {"pass": True, "detail": f"/api returned status {resp.status_code}"}
        return {"pass": False, "detail": "No /api/ endpoint found"}
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l3_json_responses(base_url):
    """Check if /api/ returns JSON responses."""
    try:
        for path in ["/api/", "/api"]:
            resp = _fetch(f"{base_url}{path}")
            if resp and resp.status_code in (200, 401, 403):
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return {"pass": True, "detail": f"JSON response from {path}"}
        return {"pass": False, "detail": "No JSON API responses found"}
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l3_search_filter_api(html, base_url):
    """Check for search/filter capabilities."""
    try:
        # Check for search form elements in HTML
        has_search_form = bool(re.search(
            r'<(input|form)[^>]*(search|filter|query|q=)[^>]*>',
            html, re.IGNORECASE
        ))
        # Check for API endpoints with query params in HTML
        has_api_query = bool(re.search(
            r'(/api/[^"\']*\?|/search[^"\']*\?|/filter[^"\']*\?)',
            html, re.IGNORECASE
        ))
        # Also try hitting a search endpoint
        search_endpoint = False
        for path in ["/search", "/api/search"]:
            resp = _fetch(f"{base_url}{path}")
            if resp and resp.status_code in (200, 400, 401, 403):
                search_endpoint = True
                break

        passed = has_search_form or has_api_query or search_endpoint
        details = []
        if has_search_form:
            details.append("search/filter form elements found")
        if has_api_query:
            details.append("API query endpoints found in HTML")
        if search_endpoint:
            details.append("search endpoint exists")
        return {
            "pass": passed,
            "detail": "; ".join(details) if details else "No search/filter capabilities found",
        }
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l3_rate_limits_documented(base_url):
    """Check for rate limit headers in responses."""
    try:
        resp = _fetch(base_url)
        if resp:
            rate_headers = []
            for header in resp.headers:
                header_lower = header.lower()
                if any(k in header_lower for k in ['x-ratelimit', 'ratelimit', 'retry-after']):
                    rate_headers.append(header)
            if rate_headers:
                return {"pass": True, "detail": f"Rate limit headers found: {', '.join(rate_headers)}"}
        # Also check /api/ endpoint
        for path in ["/api/", "/api"]:
            resp = _fetch(f"{base_url}{path}")
            if resp:
                for header in resp.headers:
                    header_lower = header.lower()
                    if any(k in header_lower for k in ['x-ratelimit', 'ratelimit', 'retry-after']):
                        return {"pass": True, "detail": f"Rate limit headers found on {path}: {header}"}
        return {"pass": False, "detail": "No rate limit headers found"}
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


def check_l3_structured_errors(base_url):
    """Check if error responses are structured (JSON with error field)."""
    try:
        resp = _fetch(f"{base_url}/this-page-does-not-exist-sf-check")
        if resp:
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                try:
                    data = resp.json()
                    if any(k in data for k in ['error', 'message', 'detail', 'errors']):
                        return {"pass": True, "detail": "Structured JSON error response with error field"}
                    return {"pass": True, "detail": "JSON error response (no standard error field)"}
                except (json.JSONDecodeError, ValueError):
                    pass
        return {"pass": False, "detail": "Error responses are not structured JSON"}
    except Exception as e:
        return {"pass": False, "detail": f"Error: {str(e)}"}


# ---------------------------------------------------------------------------
# Main API view
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def check_website_api(request, domain):
    domain = _normalize_domain(domain)
    if not domain:
        return JsonResponse({"error": "Invalid domain"}, status=400)

    base_url = f"https://{domain}"

    # Fetch the main page HTML
    resp = _fetch(base_url)
    if resp is None:
        return JsonResponse({
            "error": f"Could not connect to {domain}",
            "domain": domain,
        }, status=502)

    html = resp.text

    # Run all L1 checks
    l1_results = {
        "l1_semantic_html": check_l1_semantic_html(html),
        "l1_meta_tags": check_l1_meta_tags(html),
        "l1_schema_org": check_l1_schema_org(html),
        "l1_no_captcha": check_l1_no_captcha(html),
        "l1_ssr_content": check_l1_ssr_content(html),
        "l1_clean_urls": check_l1_clean_urls(html),
    }

    # Run all L2 checks
    l2_results = {
        "l2_robots_txt": check_l2_robots_txt(base_url),
        "l2_sitemap": check_l2_sitemap(base_url),
        "l2_llms_txt": check_l2_llms_txt(base_url),
        "l2_openapi_spec": check_l2_openapi_spec(base_url),
        "l2_documentation": check_l2_documentation(base_url),
        "l2_text_content": check_l2_text_content(html),
    }

    # Run all L3 checks
    l3_results = {
        "l3_a2a_agent_card": check_l3_a2a_agent_card(base_url),
        "l3_structured_api": check_l3_structured_api(base_url),
        "l3_json_responses": check_l3_json_responses(base_url),
        "l3_search_filter_api": check_l3_search_filter_api(html, base_url),
        "l3_rate_limits_documented": check_l3_rate_limits_documented(base_url),
        "l3_structured_errors": check_l3_structured_errors(base_url),
    }

    # Calculate level summaries
    def _level_summary(results):
        passed = sum(1 for r in results.values() if r["pass"])
        total = len(results)
        return {"passed": passed, "total": total, "pass": passed >= (total // 2 + 1)}

    levels = {
        "l1": _level_summary(l1_results),
        "l2": _level_summary(l2_results),
        "l3": _level_summary(l3_results),
    }

    # Determine overall level (highest level where that level AND all below pass)
    overall_level = 0
    if levels["l1"]["pass"]:
        overall_level = 1
        if levels["l2"]["pass"]:
            overall_level = 2
            if levels["l3"]["pass"]:
                overall_level = 3

    return JsonResponse({
        "domain": domain,
        "results": {
            "l1": l1_results,
            "l2": l2_results,
            "l3": l3_results,
        },
        "levels": levels,
        "overall_level": overall_level,
    })


# ---------------------------------------------------------------------------
# Page view (renders the check template)
# ---------------------------------------------------------------------------

def check_page_view(request, domain):
    from websites.views import _normalize_url
    domain = _normalize_url(domain)
    return render(request, "check.html", {"domain": domain})
