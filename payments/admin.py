from django.contrib import admin
from payments.models import PaymentRequest, VerificationRequest


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "website", "payment_method", "chain", "status", "amount_usd", "max_verification_requests", "created_at")
    list_filter = ("status", "payment_method", "chain")
    search_fields = ("tx_hash", "dodo_session_id")
    list_editable = ("status",)


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "website", "payment", "status", "verified_by_silicon", "level_at_verification", "created_at", "served_at")
    list_filter = ("status",)
    search_fields = ("website__url", "detailed_report")
    raw_id_fields = ("payment", "website", "requested_by_carbon", "requested_by_silicon", "verified_by_silicon")
