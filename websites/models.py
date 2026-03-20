from django.db import models
from pgvector.django import VectorField
from accounts.models import Carbon, Silicon

CRITERIA_FIELDS = [
    # L1: Basic Accessibility
    "l1_semantic_html", "l1_meta_tags", "l1_schema_org", "l1_no_captcha", "l1_ssr_content", "l1_clean_urls",
    # L2: Discoverability
    "l2_robots_txt", "l2_sitemap", "l2_llms_txt", "l2_openapi_spec", "l2_documentation", "l2_text_content",
    # L3: Structured Interaction
    "l3_structured_api", "l3_json_responses", "l3_search_filter_api", "l3_a2a_agent_card", "l3_rate_limits_documented", "l3_structured_errors",
    # L4: Agent Integration
    "l4_mcp_server", "l4_webmcp", "l4_write_api", "l4_agent_auth", "l4_webhooks", "l4_idempotency",
    # L5: Autonomous Operation
    "l5_event_streaming", "l5_agent_negotiation", "l5_subscription_api", "l5_workflow_orchestration", "l5_proactive_notifications", "l5_cross_service_handoff",
]

LEVEL_RANGES = {
    1: CRITERIA_FIELDS[0:6],
    2: CRITERIA_FIELDS[6:12],
    3: CRITERIA_FIELDS[12:18],
    4: CRITERIA_FIELDS[18:24],
    5: CRITERIA_FIELDS[24:30],
}


def _compute_level(obj):
    for level in range(1, 6):
        fields = LEVEL_RANGES[level]
        passed = sum(1 for f in fields if getattr(obj, f))
        if passed < 4:
            return level - 1
    return 5


class Website(models.Model):
    url = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    siliconfriendly_entry_point = models.URLField(max_length=500, blank=True, default="", help_text="URL where an agent should start interacting with this site")
    submitted_by_carbon = models.ForeignKey(Carbon, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_websites")
    submitted_by_silicon = models.ForeignKey(Silicon, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_websites")
    is_my_website = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    trusted_verification = models.ForeignKey("WebsiteVerification", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    embedding = VectorField(dimensions=768, null=True, blank=True)

    # L1
    l1_semantic_html = models.BooleanField(default=False)
    l1_meta_tags = models.BooleanField(default=False)
    l1_schema_org = models.BooleanField(default=False)
    l1_no_captcha = models.BooleanField(default=False)
    l1_ssr_content = models.BooleanField(default=False)
    l1_clean_urls = models.BooleanField(default=False)
    # L2
    l2_robots_txt = models.BooleanField(default=False)
    l2_sitemap = models.BooleanField(default=False)
    l2_llms_txt = models.BooleanField(default=False)
    l2_openapi_spec = models.BooleanField(default=False)
    l2_documentation = models.BooleanField(default=False)
    l2_text_content = models.BooleanField(default=False)
    # L3
    l3_structured_api = models.BooleanField(default=False)
    l3_json_responses = models.BooleanField(default=False)
    l3_search_filter_api = models.BooleanField(default=False)
    l3_a2a_agent_card = models.BooleanField(default=False)
    l3_rate_limits_documented = models.BooleanField(default=False)
    l3_structured_errors = models.BooleanField(default=False)
    # L4
    l4_mcp_server = models.BooleanField(default=False)
    l4_webmcp = models.BooleanField(default=False)
    l4_write_api = models.BooleanField(default=False)
    l4_agent_auth = models.BooleanField(default=False)
    l4_webhooks = models.BooleanField(default=False)
    l4_idempotency = models.BooleanField(default=False)
    # L5
    l5_event_streaming = models.BooleanField(default=False)
    l5_agent_negotiation = models.BooleanField(default=False)
    l5_subscription_api = models.BooleanField(default=False)
    l5_workflow_orchestration = models.BooleanField(default=False)
    l5_proactive_notifications = models.BooleanField(default=False)
    l5_cross_service_handoff = models.BooleanField(default=False)

    class Meta:
        db_table = "websites"

    @property
    def level(self):
        return _compute_level(self)

    def __str__(self):
        return f"{self.name} ({self.url})"


class WebsiteVerification(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name="verifications")
    verified_by_carbon = models.ForeignKey(Carbon, on_delete=models.SET_NULL, null=True, blank=True)
    verified_by_silicon = models.ForeignKey(Silicon, on_delete=models.SET_NULL, null=True, blank=True)
    is_trusted = models.BooleanField(default=False)
    counted = models.BooleanField(default=False)
    detailed_report = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    # L1
    l1_semantic_html = models.BooleanField(default=False)
    l1_meta_tags = models.BooleanField(default=False)
    l1_schema_org = models.BooleanField(default=False)
    l1_no_captcha = models.BooleanField(default=False)
    l1_ssr_content = models.BooleanField(default=False)
    l1_clean_urls = models.BooleanField(default=False)
    # L2
    l2_robots_txt = models.BooleanField(default=False)
    l2_sitemap = models.BooleanField(default=False)
    l2_llms_txt = models.BooleanField(default=False)
    l2_openapi_spec = models.BooleanField(default=False)
    l2_documentation = models.BooleanField(default=False)
    l2_text_content = models.BooleanField(default=False)
    # L3
    l3_structured_api = models.BooleanField(default=False)
    l3_json_responses = models.BooleanField(default=False)
    l3_search_filter_api = models.BooleanField(default=False)
    l3_a2a_agent_card = models.BooleanField(default=False)
    l3_rate_limits_documented = models.BooleanField(default=False)
    l3_structured_errors = models.BooleanField(default=False)
    # L4
    l4_mcp_server = models.BooleanField(default=False)
    l4_webmcp = models.BooleanField(default=False)
    l4_write_api = models.BooleanField(default=False)
    l4_agent_auth = models.BooleanField(default=False)
    l4_webhooks = models.BooleanField(default=False)
    l4_idempotency = models.BooleanField(default=False)
    # L5
    l5_event_streaming = models.BooleanField(default=False)
    l5_agent_negotiation = models.BooleanField(default=False)
    l5_subscription_api = models.BooleanField(default=False)
    l5_workflow_orchestration = models.BooleanField(default=False)
    l5_proactive_notifications = models.BooleanField(default=False)
    l5_cross_service_handoff = models.BooleanField(default=False)

    class Meta:
        db_table = "website_verifications"
        constraints = [
            models.UniqueConstraint(fields=["website", "verified_by_silicon"], name="uq_verification_silicon", condition=models.Q(verified_by_silicon__isnull=False)),
            models.UniqueConstraint(fields=["website", "verified_by_carbon"], name="uq_verification_carbon", condition=models.Q(verified_by_carbon__isnull=False)),
        ]

    def __str__(self):
        verifier = self.verified_by_silicon or self.verified_by_carbon
        return f"Verification of {self.website.url} by {verifier}"


class CheckJob(models.Model):
    domain = models.CharField(max_length=255)
    carbon = models.ForeignKey(Carbon, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, default="queued")
    # Step 0
    website_name = models.CharField(max_length=255, blank=True, default="")
    website_description = models.TextField(blank=True, default="")
    # Per-level results: {field_name: bool}
    level_1_results = models.JSONField(null=True, blank=True)
    level_2_results = models.JSONField(null=True, blank=True)
    level_3_results = models.JSONField(null=True, blank=True)
    level_4_results = models.JSONField(null=True, blank=True)
    level_5_results = models.JSONField(null=True, blank=True)
    # Per-level reasoning: {field_name: str}
    level_1_reasoning = models.JSONField(null=True, blank=True)
    level_2_reasoning = models.JSONField(null=True, blank=True)
    level_3_reasoning = models.JSONField(null=True, blank=True)
    level_4_reasoning = models.JSONField(null=True, blank=True)
    level_5_reasoning = models.JSONField(null=True, blank=True)
    # Final
    report_md = models.TextField(blank=True, default="")
    overall_level = models.IntegerField(default=0)
    website = models.ForeignKey(Website, on_delete=models.SET_NULL, null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "check_jobs"

    def __str__(self):
        return f"CheckJob {self.id}: {self.domain} ({self.status})"


class Keyword(models.Model):
    token = models.CharField(max_length=128, unique=True)
    websites = models.ManyToManyField(Website, related_name="keywords")

    class Meta:
        db_table = "keywords"

    def __str__(self):
        return self.token
