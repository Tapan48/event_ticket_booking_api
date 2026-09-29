import logging

from celery import shared_task

from . import services
from .emails import send_tickets_email
from .models import Order

logger = logging.getLogger(__name__)


# OSError covers SMTPException and refused/reset connections. Backoff: ~1s, 2s, 4s... up to 10 min.
@shared_task(
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def send_ticket_email(order_id):
    order = (
        Order.objects.select_related("user")
        .prefetch_related("tickets__ticket_type__event__venue")
        .filter(pk=order_id, status=Order.Status.PAID)
        .first()
    )
    if order is not None:
        send_tickets_email(order)


@shared_task
def expire_stale_orders():
    """Scheduled by CELERY_BEAT_SCHEDULE; returns unpaid tickets to sale."""
    expired = services.expire_stale_orders()
    if expired:
        logger.info("Expired %d unpaid order(s)", expired)
    return expired
