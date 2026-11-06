from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import CreateView

from .models import Drop, Order, OrderItem, Product


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
