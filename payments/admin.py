from django.contrib import admin
from payments.models import PaymentRequest


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "website", "payment_method", "chain", "status", "amount_usd", "created_at")
    list_filter = ("status", "payment_method", "chain")
    search_fields = ("tx_hash", "dodo_session_id")
    list_editable = ("status",)
