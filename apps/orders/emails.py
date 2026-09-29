from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_tickets_email(order):
    """Email a paid order's tickets (HTML + plain text) to the buyer."""
    tickets = list(order.tickets.all())
    event = tickets[0].ticket_type.event
    context = {"order": order, "event": event, "tickets": tickets}
    message = EmailMultiAlternatives(
        subject=f"Your tickets for {event.title}",
        body=render_to_string("orders/emails/tickets.txt", context),
        to=[order.user.email],
    )
    message.attach_alternative(render_to_string("orders/emails/tickets.html", context), "text/html")
    message.send()
