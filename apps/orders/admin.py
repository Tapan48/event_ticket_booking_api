from django.contrib import admin

from .models import Order, Ticket


class TicketInline(admin.TabularInline):
    model = Ticket
    fields = ("code", "ticket_type", "price_paid", "checked_in_at", "checked_in_by")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total_amount", "expires_at", "paid_at", "created_at")
    list_filter = ("status",)
    search_fields = ("user__email", "tickets__code")
    date_hierarchy = "created_at"
    autocomplete_fields = ("user",)
    list_select_related = ("user",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [TicketInline]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("code", "ticket_type", "order", "price_paid", "checked_in_at")
    list_filter = ("ticket_type__event",)
    search_fields = ("code", "order__user__email")
    autocomplete_fields = ("order", "ticket_type", "checked_in_by")
    list_select_related = ("ticket_type__event", "order")
    readonly_fields = ("code", "created_at", "updated_at")
