from rest_framework.views import APIView
from rest_framework import permissions
from dodopayments import DodoPayments
from core.utils import api_response, error_response
from accounts.models import Carbon
from websites.models import Website
from payments.models import PaymentRequest
import env


class DodoCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        carbon_id = request.session.get("carbon_id")
        if not carbon_id:
            return error_response("Carbon authentication required.", status=401)
        try:
            carbon = Carbon.objects.get(id=carbon_id, is_active=True)
        except Carbon.DoesNotExist:
            return error_response("Carbon not found.", status=401)

        website_url = request.data.get("website_url", "").strip()
        if not website_url:
            return error_response("website_url is required.")

        try:
            website = Website.objects.get(url=website_url)
        except Website.DoesNotExist:
            return error_response("Website not found.", status=404)

        client = DodoPayments(bearer_token=env.DODOPAYMENTS_API_KEY)
        amount_cents = 1000  # $10

        payment = PaymentRequest.objects.create(
            website=website,
            requested_by_carbon=carbon,
            amount_usd=10.00,
            payment_method="dodo",
        )

        session = client.checkout_sessions.create(
            product_cart=[{
                "product_id": "pdt_0NYiXePm40uSt6H6x3aGn",
                "quantity": 1,
                "amount": amount_cents,
            }],
            return_url=f"{env.FRONTEND_BASE_URL}/w/{website.url}/",
            customer={"email": carbon.email, "name": carbon.username},
            metadata={
                "payment_id": str(payment.id),
                "website_id": str(website.id),
            },
        )

        payment.dodo_session_id = session.session_id
        payment.save(update_fields=["dodo_session_id"])

        return api_response(
            {
                "checkout_url": session.url,
                "session_id": session.session_id,
                "payment_id": payment.id,
            },
            meta={
                "checkout_url": "Redirect the user to this URL to complete payment",
                "session_id": "Dodo checkout session ID for tracking",
                "payment_id": "Internal payment request ID",
            },
        )


class DodoWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    OUR_PRODUCT_ID = "pdt_0NYiXePm40uSt6H6x3aGn"

    def post(self, request):
        payload = request.data
        event_type = payload.get("event_type", "")
        data = payload.get("data", {})
        metadata = data.get("metadata", {})

        # Filter: only process successful payments for our product
        product_cart = data.get("product_cart", [])
        is_ours = any(item.get("product_id") == self.OUR_PRODUCT_ID for item in product_cart)
        if not is_ours:
            # Not our product - ignore silently
            return api_response({"status": "ignored", "reason": "not our product"}, meta={"status": "Webhook processing status"})

        if event_type != "payment.succeeded" and data.get("status") != "succeeded":
            return api_response({"status": "ignored", "reason": "not a success event"}, meta={"status": "Webhook processing status"})

        payment_id = metadata.get("payment_id")
        if not payment_id:
            return api_response({"status": "no_payment_id"}, meta={"status": "Webhook processing status"})

        try:
            payment = PaymentRequest.objects.get(id=payment_id)
        except PaymentRequest.DoesNotExist:
            return error_response("Payment not found.", status=404)

        payment.status = "completed"
        payment.save(update_fields=["status"])

        return api_response({"status": "processed"}, meta={"status": "Webhook processing status"})


class CryptoSubmitView(APIView):

    def post(self, request):
        carbon_id = request.session.get("carbon_id")
        silicon = getattr(request, 'silicon', None)
        carbon = None
        if carbon_id:
            try:
                carbon = Carbon.objects.get(id=carbon_id, is_active=True)
            except Carbon.DoesNotExist:
                pass

        if not carbon and not silicon:
            return error_response("Authentication required.", status=401)

        chain = request.data.get("chain", "").lower()
        tx_hash = request.data.get("tx_hash", "").strip()
        website_url = request.data.get("website_url", "").strip()

        if chain not in ("base", "polygon", "arbitrum", "ethereum", "bsc"):
            return error_response("chain must be one of: base, polygon, arbitrum, ethereum, bsc")
        if not tx_hash:
            return error_response("tx_hash is required.")
        if not website_url:
            return error_response("website_url is required.")

        try:
            website = Website.objects.get(url=website_url)
        except Website.DoesNotExist:
            return error_response("Website not found.", status=404)

        wallet = env.USDC_EVM_ADDRESS

        payment = PaymentRequest.objects.create(
            website=website,
            requested_by_carbon=carbon,
            requested_by_silicon=silicon,
            amount_usd=10.00,
            payment_method="crypto",
            chain=chain,
            tx_hash=tx_hash,
        )

        return api_response(
            {
                "payment_id": payment.id,
                "wallet_address": wallet,
                "chain": chain,
                "tx_hash": tx_hash,
                "status": payment.status,
            },
            meta={
                "payment_id": "Internal payment request ID",
                "wallet_address": "The wallet address to send USDC to",
                "chain": "The blockchain network",
                "tx_hash": "The transaction hash submitted",
                "status": "Current payment verification status (pending until admin verifies)",
            },
        )


class CryptoVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, tx_hash):
        try:
            payment = PaymentRequest.objects.get(tx_hash=tx_hash)
        except PaymentRequest.DoesNotExist:
            return error_response("Payment not found.", status=404)

        return api_response(
            {
                "tx_hash": payment.tx_hash,
                "chain": payment.chain,
                "status": payment.status,
                "website": payment.website.url,
            },
            meta={
                "tx_hash": "The transaction hash",
                "chain": "The blockchain network",
                "status": "Current payment verification status",
                "website": "The website this payment is for",
            },
        )
