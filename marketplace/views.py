import csv
import io
import json
from datetime import datetime
from decimal import Decimal
from xml.sax.saxutils import escape

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, Http404, HttpResponse
from django.urls import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from .forms import ArtisanForm, DropForm, OrderForm, OrderItemForm, ProductForm
from .models import Artisan, Drop, Order, OrderItem, Product


ENTITY_CONFIGS = {
    "artisans": {
        "title": "Artisans",
        "singular_title": "Artisan",
        "model": Artisan,
        "form": ArtisanForm,
        "queryset": lambda: Artisan.objects.annotate(
            product_count=Count("products")
        ).order_by("name"),
        "columns": (
            ("Name", lambda artisan: artisan.name),
            ("Specialty", lambda artisan: artisan.specialty),
            ("Products", lambda artisan: artisan.product_count),
        ),
    },
    "drops": {
        "title": "Drops",
        "singular_title": "Drop",
        "model": Drop,
        "form": DropForm,
        "queryset": lambda: Drop.objects.annotate(
            product_count=Count("products")
        ).order_by("drop_datetime"),
        "columns": (
            ("Title", lambda drop: drop.title),
            ("Launch date", lambda drop: drop.drop_datetime),
            ("Products", lambda drop: drop.product_count),
            ("Status", lambda drop: drop.is_active),
        ),
    },
    "order-items": {
        "title": "Order items",
        "singular_title": "Order item",
        "model": OrderItem,
        "form": OrderItemForm,
        "queryset": lambda: OrderItem.objects.select_related(
            "order", "product"
        ).order_by("id"),
        "columns": (
            ("Order", lambda item: item.order.order_number),
            ("Product", lambda item: item.product.name),
            ("Quantity", lambda item: item.quantity),
            ("Unit price", lambda item: item.price_at_purchase),
        ),
    },
    "orders": {
        "title": "Orders",
        "singular_title": "Order",
        "model": Order,
        "form": OrderForm,
        "queryset": lambda: Order.objects.annotate(
            item_count=Count("items")
        ).order_by("-created_at"),
        "columns": (
            ("Order ID", lambda order: order.order_number),
            ("Customer", lambda order: order.customer_name),
            ("Date", lambda order: order.created_at),
            ("Items", lambda order: order.item_count),
            ("Total", lambda order: order.total_amount),
        ),
        "delete_warning": "Deleting an order also deletes its order items.",
    },
    "products": {
        "title": "Products",
        "singular_title": "Product",
        "model": Product,
        "form": ProductForm,
        "queryset": lambda: Product.objects.select_related(
            "artisan", "drop"
        ).order_by("name"),
        "columns": (
            ("Name", lambda product: product.name),
            ("Artisan", lambda product: product.artisan.name),
            ("Drop", lambda product: product.drop.title),
            ("Price", lambda product: product.price),
            ("Stock", lambda product: product.stock_quantity),
        ),
    },
}


def _format_admin_value(value):
    if isinstance(value, bool):
        return "Active" if value else "Inactive"
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime("%b %d, %Y %H:%M")
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    if value is None:
        return "—"
    return str(value)


class StaffRequiredMixin:
    @method_decorator(staff_member_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class AdminEntityMixin(StaffRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        self.entity_key = kwargs.get("entity")
        self.entity_config = ENTITY_CONFIGS.get(self.entity_key)
        if self.entity_config is None:
            raise Http404("Admin section not found.")
        return super().dispatch(request, *args, **kwargs)

    @property
    def list_url(self):
        return reverse("admin_entity_list", kwargs={"entity": self.entity_key})

    @property
    def create_url(self):
        return reverse("admin_entity_create", kwargs={"entity": self.entity_key})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "entity_key": self.entity_key,
                "entity_title": self.entity_config["title"],
                "singular_title": self.entity_config["singular_title"],
                "active_section": self.entity_key,
                "create_url": self.create_url,
                "list_url": self.list_url,
            }
        )
        return context


class AdminEntityListView(AdminEntityMixin, ListView):
    template_name = "marketplace/admin_entity_list.html"
    context_object_name = "objects"
    paginate_by = 50

    def get_queryset(self):
        return self.entity_config["queryset"]()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        columns = self.entity_config["columns"]
        context["columns"] = [column[0] for column in columns]
        context["records"] = [
            {
                "pk": item.pk,
                "label": str(item),
                "cells": [
                    _format_admin_value(value_getter(item))
                    for _, value_getter in columns
                ],
                "edit_url": reverse(
                    "admin_entity_edit",
                    kwargs={"entity": self.entity_key, "pk": item.pk},
                ),
                "delete_url": reverse(
                    "admin_entity_delete",
                    kwargs={"entity": self.entity_key, "pk": item.pk},
                ),
            }
            for item in context["objects"]
        ]
        return context


class AdminEntityFormMixin(AdminEntityMixin):
    template_name = "marketplace/admin_entity_form.html"

    def get_form_class(self):
        return self.entity_config["form"]

    def get_success_url(self):
        return self.list_url

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"{self.entity_config['singular_title']} saved successfully.",
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_heading"] = (
            f"Edit {self.entity_config['singular_title']}"
            if getattr(self, "object", None)
            else f"Add {self.entity_config['singular_title']}"
        )
        return context


class AdminEntityCreateView(AdminEntityFormMixin, CreateView):
    pass


class AdminEntityUpdateView(AdminEntityFormMixin, UpdateView):
    def get_queryset(self):
        return self.entity_config["model"].objects.all()


class AdminEntityDeleteView(AdminEntityMixin, DeleteView):
    template_name = "marketplace/admin_entity_confirm_delete.html"

    def get_queryset(self):
        return self.entity_config["model"].objects.all()

    def get_success_url(self):
        return self.list_url

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["delete_warning"] = self.entity_config.get(
            "delete_warning",
            "Records in use by other data cannot be deleted.",
        )
        return context

    def form_valid(self, form):
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                "This record is still in use and cannot be deleted.",
            )
        else:
            messages.success(
                self.request,
                f"{self.entity_config['singular_title']} deleted successfully.",
            )
        return redirect(self.get_success_url())


def _report_csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    writer.writerows(rows)
    return response


def _report_pdf_response(title, headers, rows, filename, page_size=A4):
    buffer = io.BytesIO()
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="HYSMyeongJo-Medium",
        textColor=colors.HexColor("#1A1A1A"),
        alignment=0,
        spaceAfter=16,
    )
    cell_style = ParagraphStyle(
        "ReportCell",
        parent=styles["BodyText"],
        fontName="HYSMyeongJo-Medium",
        fontSize=8,
        leading=11,
    )
    header_style = ParagraphStyle(
        "ReportHeader",
        parent=cell_style,
        textColor=colors.white,
    )
    table_data = [
        [Paragraph(escape(str(value)), header_style) for value in headers],
        *[
            [Paragraph(escape(str(value)), cell_style) for value in row]
            for row in rows
        ],
    ]
    document = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=30,
        leftMargin=30,
        topMargin=36,
        bottomMargin=36,
        title=title,
    )
    table = Table(table_data, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A1A1A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#F3F1ED"),
                ]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D6D3D1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    document.build([Paragraph(escape(title), title_style), table])
    buffer.seek(0)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )


@staff_member_required
def admin_dashboard(request):
    total_revenue = Order.objects.aggregate(total=Sum("total_amount"))["total"]
    total_items = Product.objects.aggregate(total=Sum("stock_quantity"))["total"]
    stock_counts = Product.objects.aggregate(
        stock_in_stock=Count("pk", filter=Q(stock_quantity__gt=10)),
        stock_low=Count(
            "pk", filter=Q(stock_quantity__gt=0, stock_quantity__lte=10)
        ),
        stock_sold_out=Count("pk", filter=Q(stock_quantity=0)),
    )
    drop_revenue_expression = ExpressionWrapper(
        F("products__order_items__quantity")
        * F("products__order_items__price_at_purchase"),
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )
    drops = Drop.objects.annotate(
        revenue=Sum(drop_revenue_expression)
    ).order_by("drop_datetime")
    drop_labels = json.dumps([drop.title for drop in drops])
    drop_revenues = json.dumps([float(drop.revenue or 0) for drop in drops])
    return render(
        request,
        "marketplace/admin_dashboard.html",
        {
            "total_revenue": total_revenue or Decimal("0.00"),
            "total_items": total_items or 0,
            "active_artisans": Artisan.objects.count(),
            **stock_counts,
            "drop_labels": drop_labels,
            "drop_revenues": drop_revenues,
        },
    )


@staff_member_required
def export_accounting_csv(request):
    orders = Order.objects.order_by("-created_at")
    return _report_csv_response(
        "crafts-happy-accounting.csv",
        ("Order ID", "Date", "Customer Name", "Total Amount"),
        (
            (
                order.order_number,
                timezone.localtime(order.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                order.customer_name,
                order.total_amount,
            )
            for order in orders
        ),
    )


@staff_member_required
def export_inventory_csv(request):
    products = Product.objects.select_related("artisan", "drop").order_by("name")
    return _report_csv_response(
        "crafts-happy-inventory.csv",
        ("Product Name", "Artisan", "Drop", "Price", "Stock Quantity"),
        (
            (
                product.name,
                product.artisan.name,
                product.drop.title,
                product.price,
                product.stock_quantity,
            )
            for product in products
        ),
    )


@staff_member_required
def export_accounting_pdf(request):
    orders = Order.objects.order_by("-created_at")
    rows = [
        (
            order.order_number,
            timezone.localtime(order.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            order.customer_name,
            order.total_amount,
        )
        for order in orders
    ]
    return _report_pdf_response(
        "CRAFTS HAPPY Accounting Report",
        ("Order ID", "Date", "Customer Name", "Total Amount"),
        rows,
        "crafts-happy-accounting.pdf",
    )


@staff_member_required
def export_inventory_pdf(request):
    products = Product.objects.select_related("artisan", "drop").order_by("name")
    rows = [
        (
            product.name,
            product.artisan.name,
            product.drop.title,
            product.price,
            product.stock_quantity,
        )
        for product in products
    ]
    return _report_pdf_response(
        "CRAFTS HAPPY Inventory Report",
        ("Product Name", "Artisan", "Drop", "Price", "Stock Quantity"),
        rows,
        "crafts-happy-inventory.pdf",
        page_size=landscape(A4),
    )


class SignUpView(CreateView):
    form_class = UserCreationForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


class StoreLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True


def _session_cart(request):
    stored_cart = request.session.get("cart", {})
    if not isinstance(stored_cart, dict):
        stored_cart = {}

    cart = {}
    for product_id, quantity in stored_cart.items():
        try:
            normalized_id = str(int(product_id))
        except (TypeError, ValueError):
            continue
        if (
            normalized_id != "0"
            and isinstance(quantity, int)
            and not isinstance(quantity, bool)
            and quantity > 0
        ):
            cart[normalized_id] = quantity

    if cart != stored_cart:
        request.session["cart"] = cart
    return cart


def _cart_context(request):
    cart = _session_cart(request)
    products = Product.objects.filter(pk__in=cart).select_related("artisan", "drop")
    products_by_id = {str(product.pk): product for product in products}

    items = []
    for product_id, quantity in list(cart.items()):
        product = products_by_id.get(product_id)
        if product is None:
            cart.pop(product_id, None)
            continue
        items.append(
            {
                "product": product,
                "quantity": quantity,
                "line_total": product.price * quantity,
            }
        )

    request.session["cart"] = cart
    total = sum(
        (item["line_total"] for item in items), start=Decimal("0.00")
    )
    return {
        "cart": items,
        "cart_items": items,
        "cart_total": total,
        "total": total,
    }


def home(request):
    active_drop = (
        Drop.objects.filter(is_active=True)
        .order_by("drop_datetime")
        .first()
    )
    if active_drop is None:
        active_drop = (
            Drop.objects.filter(drop_datetime__gte=timezone.now())
            .order_by("drop_datetime")
            .first()
        )

    products = Product.objects.select_related("artisan", "drop").all()
    return render(
        request,
        "marketplace/home.html",
        {"active_drop": active_drop, "products": products},
    )


def drop_calendar(request):
    now = timezone.now()
    drops = Drop.objects.prefetch_related("products").order_by("drop_datetime")
    return render(
        request,
        "marketplace/drop_calendar.html",
        {
            "drops": drops,
            "now": now,
            "has_upcoming_drops": drops.filter(drop_datetime__gte=now).exists(),
            "has_past_drops": drops.filter(drop_datetime__lt=now).exists(),
            "upcoming_drops": Drop.objects.filter(drop_datetime__gte=now)
            .prefetch_related("products")
            .order_by("drop_datetime"),
            "past_drops": Drop.objects.filter(drop_datetime__lt=now)
            .prefetch_related("products")
            .order_by("-drop_datetime"),
        },
    )


def product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related("artisan", "drop"), pk=product_id
    )
    return render(request, "marketplace/product_detail.html", {"product": product})


def add_to_cart(request, product_id):
    if request.method != "POST":
        return redirect("product_detail", product_id=product_id)

    product = get_object_or_404(Product, pk=product_id)
    try:
        quantity = int(request.POST.get("quantity", "1"))
    except (TypeError, ValueError):
        quantity = 0

    cart = _session_cart(request)
    current_quantity = cart.get(str(product.pk), 0)
    if quantity < 1:
        messages.error(request, "Enter a valid quantity.")
    elif product.stock_quantity < current_quantity + quantity:
        messages.error(
            request,
            f"Only {product.stock_quantity} of {product.name} are currently available.",
        )
    else:
        cart[str(product.pk)] = current_quantity + quantity
        request.session["cart"] = cart
        messages.success(request, f"Added {product.name} to your cart.")

    return redirect("product_detail", product_id=product.pk)


def view_cart(request):
    return render(request, "marketplace/cart.html", _cart_context(request))


def remove_from_cart(request, product_id):
    if request.method != "POST":
        return redirect("cart")

    cart = _session_cart(request)
    cart.pop(str(product_id), None)
    request.session["cart"] = cart
    messages.success(request, "Item removed from your cart.")
    return redirect("cart")


class SoldOutError(Exception):
    def __init__(self, product_name):
        self.product_name = product_name
        super().__init__(product_name)


def checkout(request):
    context = _cart_context(request)
    cart = _session_cart(request)
    if not cart:
        messages.error(request, "Your cart is empty.")
        return render(request, "marketplace/checkout.html", context)

    if request.method != "POST":
        return render(request, "marketplace/checkout.html", context)

    customer_name = request.POST.get("customer_name", "").strip()
    customer_email = request.POST.get("customer_email", "").strip()
    shipping_address = request.POST.get("shipping_address", "").strip()
    city = request.POST.get("city", "").strip()
    postal_code = request.POST.get("postal_code", "").strip()
    country = request.POST.get("country", "South Korea").strip()
    required_fields = {
        "customer_name": customer_name,
        "shipping_address": shipping_address,
        "city": city,
        "postal_code": postal_code,
        "country": country,
    }
    missing_fields = [field for field, value in required_fields.items() if not value]
    field_limits = {
        "customer_name": 160,
        "shipping_address": 255,
        "city": 100,
        "postal_code": 20,
        "country": 100,
    }
    overlong_fields = [
        field
        for field, value in required_fields.items()
        if len(value) > field_limits[field]
    ]
    if missing_fields:
        messages.error(request, "Complete all name and shipping address fields.")
    if overlong_fields:
        messages.error(request, "One or more shipping details are too long.")
    valid_email = True
    try:
        validate_email(customer_email)
    except ValidationError:
        messages.error(request, "Enter a valid email address.")
        valid_email = False
    if missing_fields or overlong_fields or not valid_email:
        return render(
            request,
            "marketplace/checkout.html",
            {
                **context,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "shipping_address": shipping_address,
                "city": city,
                "postal_code": postal_code,
                "country": country,
            },
        )

    try:
        with transaction.atomic():
            products = {
                str(product.pk): product
                for product in Product.objects.filter(pk__in=cart)
            }
            if len(products) != len(cart):
                raise SoldOutError("An item in your cart")

            for product_id, quantity in cart.items():
                product = products[product_id]
                updated = Product.objects.filter(
                    pk=product.pk,
                    stock_quantity__gte=quantity,
                ).update(stock_quantity=F("stock_quantity") - quantity)
                if updated != 1:
                    raise SoldOutError(product.name)

            total_amount = sum(
                (
                    products[product_id].price * quantity
                    for product_id, quantity in cart.items()
                ),
                start=Decimal("0.00"),
            )
            order = Order.objects.create(
                customer_name=customer_name,
                customer_email=customer_email,
                user=request.user if request.user.is_authenticated else None,
                shipping_address=shipping_address,
                city=city,
                postal_code=postal_code,
                country=country,
                total_amount=total_amount,
            )
            OrderItem.objects.bulk_create(
                [
                    OrderItem(
                        order=order,
                        product=products[product_id],
                        quantity=quantity,
                        price_at_purchase=products[product_id].price,
                    )
                    for product_id, quantity in cart.items()
                ]
            )
    except SoldOutError as error:
        messages.error(
            request,
            f"Sorry, {error.product_name} just sold out. Your order was not placed.",
        )
        return render(
            request,
            "marketplace/checkout.html",
            {
                **_cart_context(request),
                "customer_name": customer_name,
                "customer_email": customer_email,
                "shipping_address": shipping_address,
                "city": city,
                "postal_code": postal_code,
                "country": country,
            },
        )

    request.session["cart"] = {}
    request.session["last_order_id"] = order.pk
    return redirect("order_success")


def order_success(request):
    order_id = request.session.get("last_order_id")
    if not order_id:
        messages.error(request, "No recent order was found.")
        return redirect("home")

    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"), pk=order_id
    )
    return render(request, "marketplace/order_success.html", {"order": order})


@login_required(login_url="login")
def order_history(request):
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("items__product")
        .order_by("-created_at")
    )
    return render(request, "marketplace/order_history.html", {"orders": orders})
