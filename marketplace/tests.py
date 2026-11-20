import csv
import io
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Artisan, Drop, Order, OrderItem, Product


class AdminDashboardReportingTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="report-admin",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(user)
        self.artisan = Artisan.objects.create(
            name="김민수",
            bio="Handmade ceramics",
            specialty="Ceramics",
        )
        self.drop = Drop.objects.create(
            title="겨울의 온기",
            drop_datetime=timezone.now() + timedelta(days=1),
        )
        self.available_product = Product.objects.create(
            name="손으로 빚은 그릇",
            description="Ceramic bowl",
            price=Decimal("2.00"),
            stock_quantity=11,
            drop=self.drop,
            artisan=self.artisan,
            image_url="https://example.com/bowl.jpg",
        )
        self.low_stock_product = Product.objects.create(
            name="Small cup",
            description="Ceramic cup",
            price=Decimal("3.00"),
            stock_quantity=10,
            drop=self.drop,
            artisan=self.artisan,
            image_url="https://example.com/cup.jpg",
        )
        Product.objects.create(
            name="Sold out plate",
            description="Ceramic plate",
            price=Decimal("4.00"),
            stock_quantity=0,
            drop=self.drop,
            artisan=self.artisan,
            image_url="https://example.com/plate.jpg",
        )
        self.order = Order.objects.create(
            customer_name="Test Customer",
            customer_email="customer@example.com",
            total_amount=Decimal("15.00"),
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.available_product,
            quantity=3,
            price_at_purchase=Decimal("2.00"),
        )

    def test_dashboard_metrics_and_drop_revenue(self):
        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_revenue"], Decimal("15.00"))
        self.assertEqual(response.context["total_items"], 21)
        self.assertEqual(response.context["active_artisans"], 1)
        self.assertEqual(response.context["stock_in_stock"], 1)
        self.assertEqual(response.context["stock_low"], 1)
        self.assertEqual(response.context["stock_sold_out"], 1)
        self.assertEqual(
            json.loads(response.context["drop_labels"]), ["겨울의 온기"]
        )
        self.assertEqual(response.context["drop_revenues"], "[6.0]")
        self.assertContains(response, "CRAFTS HAPPY")

    def test_dashboard_and_exports_require_staff_access(self):
        self.client.logout()

        for route_name in (
            "admin_dashboard",
            "export_accounting_csv",
            "export_inventory_csv",
            "export_accounting_pdf",
            "export_inventory_pdf",
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 302)

    def test_staff_can_find_dashboard_from_storefront(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, reverse("admin_dashboard"))
        self.assertContains(response, ">Dashboard</a>")

    def test_staff_can_manage_all_dashboard_sections(self):
        cases = (
            (
                "artisans",
                Artisan,
                {
                    "name": "New Maker",
                    "bio": "A test artisan",
                    "specialty": "Textiles",
                },
                {"specialty": "Ceramics"},
                "specialty",
                "Ceramics",
            ),
            (
                "drops",
                Drop,
                {
                    "title": "New Drop",
                    "drop_datetime": "2030-01-02T03:04",
                    "is_active": "on",
                },
                {
                    "title": "Updated Drop",
                    "drop_datetime": "2030-01-03T03:04",
                    "is_active": "on",
                },
                "title",
                "Updated Drop",
            ),
            (
                "orders",
                Order,
                {
                    "customer_name": "New Customer",
                    "customer_email": "new@example.com",
                    "shipping_address": "1 Market Street",
                    "city": "Seoul",
                    "postal_code": "12345",
                    "country": "South Korea",
                    "total_amount": "25.00",
                },
                {"customer_name": "Updated Customer"},
                "customer_name",
                "Updated Customer",
            ),
            (
                "products",
                Product,
                {
                    "name": "New Product",
                    "description": "A test product",
                    "price": "12.50",
                    "stock_quantity": "8",
                    "drop": str(self.drop.pk),
                    "artisan": str(self.artisan.pk),
                    "image_url": "https://example.com/new-product.jpg",
                },
                {"stock_quantity": "9"},
                "stock_quantity",
                9,
            ),
            (
                "order-items",
                OrderItem,
                {
                    "order": str(self.order.pk),
                    "product": str(self.available_product.pk),
                    "quantity": "2",
                    "price_at_purchase": "2.00",
                },
                {"quantity": "4"},
                "quantity",
                4,
            ),
        )

        for entity, model, create_data, updates, field_name, expected in cases:
            with self.subTest(entity=entity):
                list_url = reverse("admin_entity_list", kwargs={"entity": entity})
                self.assertEqual(self.client.get(list_url).status_code, 200)

                response = self.client.post(
                    reverse("admin_entity_create", kwargs={"entity": entity}),
                    create_data,
                )
                self.assertEqual(response.status_code, 302)
                instance = model.objects.latest("pk")

                response = self.client.post(
                    reverse(
                        "admin_entity_edit",
                        kwargs={"entity": entity, "pk": instance.pk},
                    ),
                    {**create_data, **updates},
                )
                self.assertEqual(response.status_code, 302)
                instance.refresh_from_db()
                self.assertEqual(getattr(instance, field_name), expected)

                response = self.client.post(
                    reverse(
                        "admin_entity_delete",
                        kwargs={"entity": entity, "pk": instance.pk},
                    )
                )
                self.assertEqual(response.status_code, 302)
                self.assertFalse(model.objects.filter(pk=instance.pk).exists())

    def test_csv_exports_contain_requested_columns_and_rows(self):
        accounting = self.client.get(
            reverse("export_accounting_csv")
        )
        accounting_rows = list(csv.reader(io.StringIO(accounting.content.decode())))
        self.assertEqual(
            accounting_rows[0],
            ["Order ID", "Date", "Customer Name", "Total Amount"],
        )
        self.assertEqual(accounting_rows[1][0], self.order.order_number)
        self.assertEqual(accounting_rows[1][2:], ["Test Customer", "15.00"])

        inventory = self.client.get(
            reverse("export_inventory_csv")
        )
        inventory_rows = list(csv.reader(io.StringIO(inventory.content.decode())))
        self.assertEqual(
            inventory_rows[0],
            ["Product Name", "Artisan", "Drop", "Price", "Stock Quantity"],
        )
        self.assertEqual(
            inventory_rows[1],
            ["Small cup", "김민수", "겨울의 온기", "3.00", "10"],
        )

    def test_pdf_exports_generate_downloadable_pdfs(self):
        for route_name in (
            "export_accounting_pdf",
            "export_inventory_pdf",
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/pdf")
                self.assertTrue(
                    b"".join(response.streaming_content).startswith(b"%PDF")
                )
