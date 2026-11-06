from uuid import uuid4

from django.conf import settings
from django.db import models


def generate_order_number():
    return uuid4().hex[:12].upper()


class Artisan(models.Model):
    name = models.CharField(max_length=120, unique=True)
    bio = models.TextField()
    specialty = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Drop(models.Model):
    title = models.CharField(max_length=160, unique=True)
    drop_datetime = models.DateTimeField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["drop_datetime"]

    def __str__(self):
        return self.title


class Product(models.Model):
    name = models.CharField(max_length=160)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    drop = models.ForeignKey(Drop, on_delete=models.PROTECT, related_name="products")
    artisan = models.ForeignKey(
        Artisan, on_delete=models.PROTECT, related_name="products"
    )
    image_url = models.URLField(max_length=500)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Order(models.Model):
    order_number = models.CharField(
        max_length=12, unique=True, default=generate_order_number, editable=False
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marketplace_orders",
    )
    customer_name = models.CharField(max_length=160)
    customer_email = models.EmailField()
    shipping_address = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=100, default="South Korea")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="order_items"
    )
    quantity = models.PositiveIntegerField()
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity} × {self.product.name} ({self.order.order_number})"
