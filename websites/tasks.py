import json
import re
from celery import shared_task
from django.db.models import Count
from google import genai
from google.genai import types as genai_types
import env

_GEMINI_CLIENT = None


def _get_client():
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is None:
        _GEMINI_CLIENT = genai.Client(api_key=env.GEMINI_API_KEY)
    return _GEMINI_CLIENT


def _normalise_token(t):
    t = t.lower().strip()
    t = re.sub(r'[\s\-/]+', '_', t)
    t = re.sub(r'[^a-z0-9_]', '', t)
    return t


@shared_task
def generate_website_embedding(website_id):
    from websites.models import Website, Keyword

    try:
        website = Website.objects.get(id=website_id)
    except Website.DoesNotExist:
        return

    text = f"{website.name}. {website.description}"
    client = _get_client()

    # Generate embedding
    config = genai_types.EmbedContentConfig(
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=768,
    )
    res = client.models.embed_content(
        model="gemini-embedding-001",
        contents=[text],
        config=config,
    )
    embedding = res.embeddings[0].values
    # Normalize
    norm = sum(x * x for x in embedding) ** 0.5
    if norm > 0:
        embedding = [x / norm for x in embedding]

    website.embedding = embedding
    website.save(update_fields=["embedding"])

    # Generate keywords
    _generate_keywords(website, text)


def _generate_keywords(website, text):
    from websites.models import Keyword

    client = _get_client()
    prompt = f"Generate 20 search keywords/tokens for this website. Return a JSON array of strings.\n\nWebsite: {website.name}\nDomain: {website.url}\nDescription: {text}"

    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=genai_types.Schema(
            type=genai_types.Type.ARRAY,
            items=genai_types.Schema(type=genai_types.Type.STRING),
        ),
    )
    res = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=prompt,
        config=config,
    )

    try:
        tokens_raw = json.loads(res.text)
    except (json.JSONDecodeError, AttributeError):
        return

    tokens = set()
    for t in tokens_raw:
        normalized = _normalise_token(t)
        if normalized and len(normalized) >= 2:
            tokens.add(normalized)
            # Expand compound tokens
            parts = normalized.split('_')
            if len(parts) > 1:
                for p in parts:
                    if len(p) >= 2:
                        tokens.add(p)

    # Clear old keywords for this website
    website.keywords.clear()

    for t in tokens:
        kw, _ = Keyword.objects.get_or_create(token=t)
        kw.websites.add(website)


@shared_task
def daily_verification_crunch():
    """Daily cron: recompute website criteria from verifications."""
    from websites.models import Website, WebsiteVerification, CRITERIA_FIELDS

    uncounted = WebsiteVerification.objects.filter(counted=False)
    affected_ids = set(uncounted.values_list("website_id", flat=True))

    if not affected_ids:
        return "No uncounted verifications."

    for website_id in affected_ids:
        try:
            website = Website.objects.get(id=website_id)
        except Website.DoesNotExist:
            continue

        verifications = WebsiteVerification.objects.filter(website=website)

        for field in CRITERIA_FIELDS:
            weighted_true = 0
            weighted_total = 0
            for v in verifications:
                weight = 100 if v.is_trusted else 1
                if getattr(v, field):
                    weighted_true += weight
                weighted_total += weight

            if weighted_total > 0:
                setattr(website, field, weighted_true > weighted_total / 2)

        # Check if verified: trusted verification OR 12+ verifications
        trusted = verifications.filter(is_trusted=True).first()
        total_count = verifications.count()
        website.verified = trusted is not None or total_count >= 12
        if trusted:
            website.trusted_verification = WebsiteVerification.objects.filter(website=website, is_trusted=True).first()

        website.save()

    # Mark all as counted
    uncounted.update(counted=True)

    return f"Processed {len(affected_ids)} websites."
