import re
from datetime import timedelta
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from common.ratelimit import check_rate_limit, get_client_ip
from accounts.models import Carbon


def _normalize_domain(domain):
    """Strip protocol, path, trailing slash -> domain only."""
    domain = domain.strip().lower()
    domain = re.sub(r'^https?://', '', domain)
    domain = domain.split('/')[0]
    domain = domain.rstrip('.')
    return domain


def check_page_view(request, domain):
    """Render the check page with auth context."""
    from websites.views import _normalize_url
    domain = _normalize_url(domain)

    carbon = None
    carbon_id = request.session.get("carbon_id")
    if carbon_id:
        try:
            carbon = Carbon.objects.get(id=carbon_id, is_active=True)
        except Carbon.DoesNotExist:
            pass

    obfuscated_email = ""
    if carbon and carbon.email:
        email = carbon.email
        local, at_domain = email.split("@") if "@" in email else (email, "")
        if at_domain:
            show_start = local[:4] if len(local) > 4 else local[:2]
            show_end = at_domain[-2:]
            obfuscated_email = show_start + "*****" + show_end

    return render(request, "check.html", {
        "domain": domain,
        "obfuscated_email": obfuscated_email,
    })


@csrf_exempt
@require_http_methods(["GET"])
def check_website_api(request, domain):
    """Legacy endpoint — redirects to new flow."""
    return JsonResponse({"error": "Use POST /api/check/<domain>/start/ instead", "deprecated": True}, status=410)


@csrf_exempt
@require_http_methods(["POST"])
def start_check_api(request, domain):
    """Start a check job. Requires auth. Returns existing website if already checked."""
    from websites.models import Website, CheckJob
    from websites.tasks import run_website_check

    carbon_id = request.session.get("carbon_id")
    if not carbon_id:
        return JsonResponse({"error": "Login required"}, status=401)

    try:
        carbon = Carbon.objects.get(id=carbon_id, is_active=True)
    except Carbon.DoesNotExist:
        return JsonResponse({"error": "Login required"}, status=401)

    domain = _normalize_domain(domain)
    if not domain:
        return JsonResponse({"error": "Invalid domain"}, status=400)

    # Check if website already exists in DB
    try:
        existing = Website.objects.get(url=domain)
        return JsonResponse({"exists": True, "url": f"/w/{domain}/"})
    except Website.DoesNotExist:
        pass

    # Rate limit: 5 checks per hour per carbon
    ip = get_client_ip(request)
    allowed, retry_after = check_rate_limit(f"check:carbon:{carbon.id}", 5, 3600)
    if not allowed:
        return JsonResponse({"error": f"Too many checks. Try again in {retry_after}s."}, status=429)

    # Dedup: reuse recent job for same domain+carbon
    recent = CheckJob.objects.filter(
        domain=domain, carbon=carbon,
        created_at__gte=timezone.now() - timedelta(minutes=30),
    ).exclude(status="error").order_by("-created_at").first()

    if recent:
        return JsonResponse({"job_id": recent.id, "status": recent.status})

    # Create new job
    job = CheckJob.objects.create(domain=domain, carbon=carbon)
    run_website_check.delay(job.id)

    return JsonResponse({"job_id": job.id, "status": "queued"})


@csrf_exempt
@require_http_methods(["GET"])
def check_status_api(request, domain):
    """Poll check job status."""
    from websites.models import CheckJob

    job_id = request.GET.get("job_id")
    if not job_id:
        return JsonResponse({"error": "job_id required"}, status=400)

    try:
        job = CheckJob.objects.get(id=job_id)
    except CheckJob.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)

    response = {
        "job_id": job.id,
        "status": job.status,
        "domain": job.domain,
        "website_name": job.website_name,
        "website_description": job.website_description,
        "overall_level": job.overall_level,
    }

    # Queue position
    if job.status == "queued":
        ahead = CheckJob.objects.filter(
            status="queued", created_at__lt=job.created_at
        ).count()
        response["queue_position"] = ahead + 1

    # Include completed level results
    for level in range(1, 6):
        results = getattr(job, f"level_{level}_results")
        reasoning = getattr(job, f"level_{level}_reasoning")
        if results is not None:
            response[f"level_{level}"] = {
                "results": results,
                "reasoning": reasoning or {},
                "passed": sum(1 for v in results.values() if v),
                "total": len(results),
            }

    if job.status == "done":
        response["report_md"] = job.report_md
        if job.website:
            response["website_url"] = f"/w/{job.domain}/"

    if job.status == "error":
        response["error"] = job.error_message

    return JsonResponse(response)


def report_download_view(request, domain, job_id):
    """Download PDF report for a check job."""
    from websites.models import CheckJob
    from websites.report_pdf import generate_pdf

    try:
        job = CheckJob.objects.get(id=job_id, status="done")
    except CheckJob.DoesNotExist:
        return HttpResponse("Report not found", status=404)

    pdf_bytes = generate_pdf(job)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="siliconfriendly-{domain}-L{job.overall_level}.pdf"'
    return response
