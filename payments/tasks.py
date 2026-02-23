import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def check_pending_payments():
    """
    Runs every minute via celery beat.
    For each pending PaymentRequest:
      - crypto: try on-chain verification
      - dodo: try status check via API
      - check max wait timeout
    """
    from payments.models import PaymentRequest, VerificationRequest
    from payments.config import PAYMENT_MAX_WAIT
    from payments.verify_crypto import verify_crypto_payment
    from common.mail import send_email
    import env

    pending = PaymentRequest.objects.filter(status="pending")
    now = timezone.now()

    for payment in pending:
        age_minutes = (now - payment.created_at).total_seconds() / 60
        website_name = payment.website.url

        # -- Crypto verification --
        if payment.payment_method == "crypto" and payment.tx_hash and payment.chain:
            try:
                result = verify_crypto_payment(
                    chain=payment.chain,
                    tx_hash=payment.tx_hash,
                    wallet_address=env.USDC_EVM_ADDRESS,
                )
                if result["verified"]:
                    _mark_completed(payment)
                    logger.info(f"Payment #{payment.id} verified on-chain ({payment.chain})")
                    continue
                elif result["reason"] and "mismatch" in result["reason"]:
                    # Definitive failure (wrong amount, wrong recipient)
                    _mark_failed(payment, result["reason"])
                    logger.info(f"Payment #{payment.id} failed: {result['reason']}")
                    continue
                # Otherwise: not found yet, keep waiting
            except Exception as e:
                logger.warning(f"Crypto verify error for payment #{payment.id}: {e}")

        # -- Dodo status check --
        if payment.payment_method == "dodo" and payment.dodo_session_id:
            try:
                dodo_status = _check_dodo_status(payment.dodo_session_id)
                if dodo_status == "succeeded":
                    _mark_completed(payment)
                    logger.info(f"Payment #{payment.id} confirmed via Dodo API")
                    continue
                elif dodo_status in ("failed", "expired", "cancelled"):
                    _mark_failed(payment, f"dodo status: {dodo_status}")
                    logger.info(f"Payment #{payment.id} failed via Dodo: {dodo_status}")
                    continue
            except Exception as e:
                logger.warning(f"Dodo status check error for payment #{payment.id}: {e}")

        # -- Timeout check --
        if payment.payment_method == "crypto":
            max_wait = PAYMENT_MAX_WAIT.get(payment.chain, 10)
        else:
            max_wait = PAYMENT_MAX_WAIT.get(payment.payment_method, 20)

        if age_minutes > max_wait:
            _mark_failed(payment, f"timed out after {int(age_minutes)} minutes")
            logger.info(f"Payment #{payment.id} timed out ({int(age_minutes)}m > {max_wait}m)")


def _check_dodo_status(dodo_session_id):
    """Check payment status via DodoPayments API. Returns status string or None."""
    from dodopayments import DodoPayments
    import env

    try:
        client = DodoPayments(bearer_token=env.DODOPAYMENTS_API_KEY)
        payment = client.payments.retrieve(dodo_session_id)
        return getattr(payment, "status", None)
    except Exception as e:
        logger.warning(f"Dodo API retrieve failed for {dodo_session_id}: {e}")
        return None


def _mark_completed(payment):
    """Mark payment as completed, send success emails, create first VerificationRequest."""
    from payments.models import VerificationRequest
    from common.mail import send_email

    payment.status = "completed"
    if payment.requested_by_carbon and payment.requested_by_carbon.email:
        payment.email = payment.requested_by_carbon.email
    payment.save(update_fields=["status", "email"])

    # Auto-create first verification request
    VerificationRequest.objects.create(
        payment=payment,
        website=payment.website,
        requested_by_carbon=payment.requested_by_carbon,
        requested_by_silicon=payment.requested_by_silicon,
        status="pending",
    )

    website_name = payment.website.url
    customer_email = payment.email
    method = payment.payment_method
    chain = payment.chain or ""
    method_display = f"crypto ({chain})" if method == "crypto" else "card/upi"

    if customer_email:
        send_email(
            to_email=customer_email,
            subject=f"Payment received - {website_name} verification",
            html_body=(
                '<pre style="font-family: Courier New, monospace; white-space: pre-wrap;">'
                '&gt; siliconfriendly\n'
                '---------------------------\n\n'
                'payment received.\n\n'
                f'&gt; website:  {website_name}\n'
                f'&gt; amount:   ${payment.amount_usd}\n'
                f'&gt; method:   {method_display}\n'
                '&gt; status:   completed\n\n'
                'a verified silicon will evaluate your\n'
                'website and send you a detailed report.\n\n'
                'you can track progress at:\n'
                f'https://siliconfriendly.com/w/{website_name}/\n\n'
                '---------------------------\n'
                'siliconfriendly.com\n'
                '</pre>'
            ),
        )

    team_emails = ["shubhastro2@gmail.com", "saketdev12@gmail.com"]
    for team_email in team_emails:
        send_email(
            to_email=team_email,
            subject=f"Payment verified: {website_name}",
            html_body=(
                '<pre style="font-family: Courier New, monospace; white-space: pre-wrap;">'
                '&gt; payment verified\n'
                '---------------------------\n\n'
                f'&gt; website:  {website_name}\n'
                f'&gt; email:    {customer_email or "unknown"}\n'
                f'&gt; amount:   ${payment.amount_usd}\n'
                f'&gt; method:   {method_display}\n\n'
                '---------------------------\n'
                '</pre>'
            ),
        )


def _mark_failed(payment, reason):
    """Mark payment as failed and send failure emails."""
    from common.mail import send_email

    payment.status = "failed"
    payment.save(update_fields=["status"])

    website_name = payment.website.url
    customer_email = payment.email or (
        payment.requested_by_carbon.email if payment.requested_by_carbon else None
    )
    method = payment.payment_method
    chain = payment.chain or ""
    method_display = f"crypto ({chain})" if method == "crypto" else "card/upi"

    if customer_email:
        send_email(
            to_email=customer_email,
            subject=f"Payment could not be verified - {website_name}",
            html_body=(
                '<pre style="font-family: Courier New, monospace; white-space: pre-wrap;">'
                '&gt; siliconfriendly\n'
                '---------------------------\n\n'
                'payment could not be verified.\n\n'
                f'&gt; website:  {website_name}\n'
                f'&gt; method:   {method_display}\n'
                '&gt; status:   failed\n'
                f'&gt; reason:   {reason}\n\n'
                'if this was a mistake, please contact\n'
                'team@unlikefraction.com with your\n'
                'transaction details.\n\n'
                '---------------------------\n'
                'siliconfriendly.com\n'
                '</pre>'
            ),
        )

    team_emails = ["shubhastro2@gmail.com", "saketdev12@gmail.com"]
    for team_email in team_emails:
        send_email(
            to_email=team_email,
            subject=f"Payment failed: {website_name} (#{payment.id})",
            html_body=(
                '<pre style="font-family: Courier New, monospace; white-space: pre-wrap;">'
                '&gt; payment failed\n'
                '---------------------------\n\n'
                f'&gt; payment:  #{payment.id}\n'
                f'&gt; website:  {website_name}\n'
                f'&gt; email:    {customer_email or "unknown"}\n'
                f'&gt; method:   {method_display}\n'
                f'&gt; reason:   {reason}\n\n'
                '---------------------------\n'
                '</pre>'
            ),
        )
