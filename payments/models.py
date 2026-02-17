from django.db import models
from accounts.models import Carbon, Silicon
from websites.models import Website


class PaymentRequest(models.Model):
    class PaymentMethod(models.TextChoices):
        DODO = "dodo"
        CRYPTO = "crypto"

    class Status(models.TextChoices):
        PENDING = "pending"
        COMPLETED = "completed"
        FAILED = "failed"

    class Chain(models.TextChoices):
        BASE = "base"
        POLYGON = "polygon"
        ARBITRUM = "arbitrum"
        ETHEREUM = "ethereum"
        BSC = "bsc"
        SOLANA = "solana"

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name="payments")
    requested_by_carbon = models.ForeignKey(Carbon, on_delete=models.SET_NULL, null=True, blank=True)
    requested_by_silicon = models.ForeignKey(Silicon, on_delete=models.SET_NULL, null=True, blank=True)
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    payment_method = models.CharField(max_length=16, choices=PaymentMethod.choices)
    chain = models.CharField(max_length=16, choices=Chain.choices, null=True, blank=True)
    tx_hash = models.CharField(max_length=128, null=True, blank=True)
    dodo_session_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_requests"

    def __str__(self):
        return f"Payment {self.id} for {self.website.url} ({self.status})"
