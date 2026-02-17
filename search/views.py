from django.db import models
from pgvector.django import CosineDistance
from rest_framework.views import APIView
from core.utils import api_response, error_response
from websites.models import Website, Keyword, CRITERIA_FIELDS
from websites.tasks import _get_client, _normalise_token
from google.genai import types as genai_types


def _website_search_result(w, score=None):
    result = {
        "url": w.url,
        "name": w.name,
        "description": w.description[:200],
        "level": w.level,
        "verified": w.verified,
    }
    if score is not None:
        result["score"] = round(score, 4)
    return result


def _search_meta():
    return {
        "results": "List of matching websites",
        "query": "The search query that was processed",
        "search_queries_remaining": "Remaining search queries for this silicon",
    }


class SemanticSearchView(APIView):

    def post(self, request):
        silicon = getattr(request, 'silicon', None)
        if not silicon:
            return error_response("Silicon authentication required.", status=401)
        if silicon.search_queries_remaining <= 0:
            return error_response("No search queries remaining. Verify websites to earn more.", status=402)

        query_text = (request.data.get("query_text") or "").strip()
        if not query_text:
            return error_response("query_text is required.")

        # Deduct query
        silicon.search_queries_remaining -= 1
        silicon.save(update_fields=["search_queries_remaining"])

        # Embed query
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

        results = (
            Website.objects
            .filter(embedding__isnull=False)
            .annotate(distance=CosineDistance("embedding", query_vec))
            .order_by("distance")[:10]
        )

        return api_response(
            {
                "results": [_website_search_result(w, 1 - w.distance) for w in results],
                "query": query_text,
                "search_queries_remaining": silicon.search_queries_remaining,
            },
            meta=_search_meta(),
        )


class KeywordSearchView(APIView):

    def post(self, request):
        silicon = getattr(request, 'silicon', None)
        if not silicon:
            return error_response("Silicon authentication required.", status=401)
        if silicon.search_queries_remaining <= 0:
            return error_response("No search queries remaining. Verify websites to earn more.", status=402)

        query_text = (request.data.get("query_text") or "").strip()
        if not query_text:
            return error_response("query_text is required.")

        # Deduct query
        silicon.search_queries_remaining -= 1
        silicon.save(update_fields=["search_queries_remaining"])

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
