from django.contrib import admin

from .models import Category, Event, TicketType, Venue


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "capacity", "created_by")
    list_filter = ("city",)
    search_fields = ("name", "city", "address")
    autocomplete_fields = ("created_by",)
    list_select_related = ("created_by",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    fields = ("name", "price", "quantity_total", "quantity_available")
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "organizer", "venue", "starts_at", "status")
    list_filter = ("status", "categories", "venue__city")
    search_fields = ("title", "description")
    date_hierarchy = "starts_at"
    autocomplete_fields = ("organizer", "venue")
    filter_horizontal = ("categories",)
    list_select_related = ("organizer", "venue")
    inlines = [TicketTypeInline]


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "price", "quantity_available", "quantity_total")
    search_fields = ("name", "event__title")
    autocomplete_fields = ("event",)
    list_select_related = ("event",)
