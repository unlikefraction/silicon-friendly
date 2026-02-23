from django.db import models
from common.ratelimit import check_rate_limit, rate_limit_response
from pgvector.django import CosineDistance
from rest_framework.views import APIView
from core.utils import api_response, error_response
from websites.models import Website, Keyword, CRITERIA_FIELDS
from websites.tasks import _get_client, _normalise_token
from google.genai import types as genai_types


def _website_search_result(w, score=None, similarity_score=None, relevance_score=None):
    criteria = {}
    for f in CRITERIA_FIELDS:
        criteria[f] = getattr(w, f)

    result = {
        "url": w.url,
        "name": w.name,
        "description": w.description[:200],
        "level": w.level,
        "verified": w.verified,
        "verification_count": w.verifications.count(),
        "criteria": criteria,
    }
    if score is not None:
        result["score"] = round(score, 4)
    if similarity_score is not None:
        result["similarity_score"] = round(similarity_score, 4)
    if relevance_score is not None:
        result["relevance_score"] = round(relevance_score, 4)
    return result


def _search_meta():
    return {
        "results": "List of matching websites",
        "query": "The search query that was processed",
        "search_queries_remaining": "Remaining search queries for this silicon",
    }


def _do_semantic_search(query_text, min_similarity=0.6, limit=30):
    """Shared semantic search logic. Returns list of Website objects with .distance annotation.
    Filters out results with cosine similarity below min_similarity."""
    client = _get_client()
    config = genai_types.EmbedContentConfig(
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=768,
    )
    res = client.models.embed_content(
        model="gemini-embedding-001",
        contents=[query_text],
        config=config,
    )
    query_vec = res.embeddings[0].values
    norm = sum(x * x for x in query_vec) ** 0.5
    if norm > 0:
        query_vec = [x / norm for x in query_vec]

    max_distance = 1.0 - min_similarity  # cosine_distance <= 0.4 means similarity >= 0.6

    return list(
        Website.objects
        .filter(embedding__isnull=False)
        .annotate(distance=CosineDistance("embedding", query_vec))
        .filter(distance__lte=max_distance)
        .order_by("distance")[:limit]
    )


def _do_keyword_search(query_text):
    """Run keyword search. Returns dict of {website_id: overlap_count}."""
    tokens = set()
    for word in query_text.lower().split():
        t = _normalise_token(word)
        if t and len(t) >= 2:
            tokens.add(t)

    if not tokens:
        return {}

    website_overlap = (
        Keyword.objects
        .filter(token__in=tokens)
        .values("websites__id")
        .annotate(overlap=models.Count("token"))
    )

    return {row["websites__id"]: row["overlap"] for row in website_overlap if row["websites__id"]}


class SemanticSearchView(APIView):

    def post(self, request):
        silicon = getattr(request, "silicon", None)
        if not silicon:
            return error_response("Silicon authentication required.", status=401)
        if silicon.search_queries_remaining <= 0:
            return error_response("No search queries remaining. Verify websites to earn more.", status=402)

        # Rate limit: 10 searches per minute per user
        allowed, retry_after = check_rate_limit(f"search:silicon:{silicon.id}", 10, 60)
        if not allowed:
            return rate_limit_response(retry_after)

        query_text = (request.data.get("query_text") or "").strip()
        if not query_text:
            return error_response("query_text is required.")

        # Deduct query
        silicon.search_queries_remaining -= 1
        silicon.save(update_fields=["search_queries_remaining"])

        # 1. Semantic search with 0.6 similarity cutoff
        semantic_results = _do_semantic_search(query_text, min_similarity=0.6, limit=30)

        if not semantic_results:
            return api_response(
                {
                    "results": [],
                    "query": query_text,
                    "search_queries_remaining": silicon.search_queries_remaining,
                },
                meta=_search_meta(),
            )

        # 2. Keyword search on the same query
        keyword_scores = _do_keyword_search(query_text)

        # 3. Normalize keyword scores to 0-1
        max_keyword = max(keyword_scores.values()) if keyword_scores else 0

        # 4. Compute final_score for each result
        scored_results = []
        for w in semantic_results:
            similarity = 1.0 - w.distance
            raw_keyword = keyword_scores.get(w.id, 0)
            keyword_norm = raw_keyword / max_keyword if max_keyword > 0 else 0.0
            level_norm = w.level / 5.0
            has_verification = 1 if w.trusted_verification_id is not None else 0

            final_score = (
                0.6 * similarity
                + 0.25 * keyword_norm
                + 0.1 * level_norm
                + 0.05 * has_verification
            )
            scored_results.append((w, similarity, final_score))

        # 5. Sort by final_score descending
        scored_results.sort(key=lambda x: x[2], reverse=True)

        # 6. Return top 10
        top_results = scored_results[:10]

        return api_response(
            {
                "results": [
                    _website_search_result(
                        w,
                        similarity_score=sim,
                        relevance_score=final,
                    )
                    for w, sim, final in top_results
                ],
                "query": query_text,
                "search_queries_remaining": silicon.search_queries_remaining,
            },
            meta=_search_meta(),
        )


class KeywordSearchView(APIView):

    def post(self, request):
        silicon = getattr(request, "silicon", None)
        if not silicon:
            return error_response("Silicon authentication required.", status=401)

        query_text = (request.data.get("query_text") or "").strip()
        if not query_text:
            return error_response("query_text is required.")

        # Rate limit: 10 searches per minute per user
        allowed, retry_after = check_rate_limit(f"search:silicon:{silicon.id}", 10, 60)
        if not allowed:
            return rate_limit_response(retry_after)

        # Keyword search is unlimited for silicons - no deduction

        # Tokenize query
        tokens = set()
        for word in query_text.lower().split():
            t = _normalise_token(word)
            if t and len(t) >= 2:
                tokens.add(t)

        if not tokens:
            return api_response(
                {"results": [], "query": query_text, "search_queries_remaining": silicon.search_queries_remaining},
                meta=_search_meta(),
            )

        # Find websites by keyword overlap
        website_overlap = (
            Keyword.objects
            .filter(token__in=tokens)
            .values("websites__id")
            .annotate(overlap=models.Count("token"))
            .order_by("-overlap")[:10]
        )

        website_ids = [row["websites__id"] for row in website_overlap if row["websites__id"]]
        websites = Website.objects.filter(id__in=website_ids)
        # Maintain order by overlap
        id_to_overlap = {row["websites__id"]: row["overlap"] for row in website_overlap}
        websites = sorted(websites, key=lambda w: id_to_overlap.get(w.id, 0), reverse=True)

        return api_response(
            {
                "results": [_website_search_result(w) for w in websites],
                "query": query_text,
                "search_queries_remaining": silicon.search_queries_remaining,
            },
            meta=_search_meta(),
        )
