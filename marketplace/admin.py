from django.contrib import admin
from django.db.models import DecimalField, F, Sum
from django.http import HttpResponse
from django.urls import path, reverse
from django.templatetags.static import static
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from .models import Artisan, Drop, Order, OrderItem, Product


@admin.register(Artisan)
class ArtisanAdmin(admin.ModelAdmin):
    list_display = ["name", "specialty"]
    search_fields = ["name", "specialty"]
    ordering = ["name"]


@admin.register(Drop)
class DropAdmin(admin.ModelAdmin):
    list_display = ["title", "drop_datetime", "is_active", "revenue_report_link"]
    list_filter = ["is_active", "drop_datetime"]
    search_fields = ["title"]
    ordering = ["-drop_datetime"]

    def get_urls(self):
        custom_urls = [
            path(
                "revenue-per-drop/",
                self.admin_site.admin_view(revenue_per_drop_view),
                name="marketplace_drop_revenue",
            )
        ]
        return custom_urls + super().get_urls()

    @admin.display(description=_("Revenue per drop"))
    def revenue_report_link(self, obj):
        url = reverse("admin:marketplace_drop_revenue")
        return format_html('<a href="{}">View report</a>', url)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "artisan", "drop", "price", "stock_quantity"]
    list_filter = ["drop", "artisan"]
    search_fields = ["name", "artisan__name", "drop__title"]
    autocomplete_fields = ["artisan", "drop"]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ["product"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "order_number",
        "user",
        "customer_name",
        "customer_email",
        "city",
        "country",
        "total_amount",
        "created_at",
    ]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "order_number",
                    "user",
                    "customer_name",
                    "customer_email",
                    "total_amount",
                    "created_at",
                ]
            },
        ),
        (
            _("Shipping destination"),
            {"fields": ["shipping_address", "city", "postal_code", "country"]},
        ),
    ]
    readonly_fields = ["order_number", "created_at"]
    list_filter = ["created_at"]
    search_fields = [
        "order_number",
        "customer_name",
        "customer_email",
        "shipping_address",
        "city",
        "postal_code",
        "country",
    ]
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ["order", "product", "quantity", "price_at_purchase"]
    list_filter = ["product__drop"]
    search_fields = ["order__order_number", "product__name"]
    autocomplete_fields = ["order", "product"]


def revenue_per_drop_view(request):
    drops = Drop.objects.annotate(
        revenue=Sum(
            F("products__order_items__quantity")
            * F("products__order_items__price_at_purchase"),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    ).order_by("-drop_datetime")

    rows = format_html_join(
        "",
        "<tr><td>{}</td><td>{}</td><td>{}</td></tr>",
        (
            (
                drop.title,
                drop.drop_datetime.strftime("%Y-%m-%d %H:%M"),
                f"${(drop.revenue or 0):,.2f}",
            )
            for drop in drops
        ),
    )
    content = format_html(
        """
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Revenue per drop</title>
            <link rel="stylesheet" href="{}">
          </head>
          <body>
            <div class="container">
              <h1>Revenue per drop</h1>
              <p><a href="{}">Return to the admin</a></p>
              <table>
                <thead><tr><th>Drop</th><th>Scheduled</th><th>Revenue</th></tr></thead>
                <tbody>{}</tbody>
              </table>
            </div>
          </body>
        </html>
        """,
        static("admin/css/base.css"),
        reverse("admin:index"),
        rows,
    )
    return HttpResponse(content)
