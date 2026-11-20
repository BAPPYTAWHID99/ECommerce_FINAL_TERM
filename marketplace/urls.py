from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path(
        "admin-dashboard/export-accounting-csv/",
        views.export_accounting_csv,
        name="export_accounting_csv",
    ),
    path(
        "admin-dashboard/export-inventory-csv/",
        views.export_inventory_csv,
        name="export_inventory_csv",
    ),
    path(
        "admin-dashboard/export-accounting-pdf/",
        views.export_accounting_pdf,
        name="export_accounting_pdf",
    ),
    path(
        "admin-dashboard/export-inventory-pdf/",
        views.export_inventory_pdf,
        name="export_inventory_pdf",
    ),
    path(
        "admin-dashboard/<slug:entity>/",
        views.AdminEntityListView.as_view(),
        name="admin_entity_list",
    ),
    path(
        "admin-dashboard/<slug:entity>/create/",
        views.AdminEntityCreateView.as_view(),
        name="admin_entity_create",
    ),
    path(
        "admin-dashboard/<slug:entity>/<int:pk>/edit/",
        views.AdminEntityUpdateView.as_view(),
        name="admin_entity_edit",
    ),
    path(
        "admin-dashboard/<slug:entity>/<int:pk>/delete/",
        views.AdminEntityDeleteView.as_view(),
        name="admin_entity_delete",
    ),
    path("login/", views.StoreLoginView.as_view(), name="login"),
    path("signup/", views.SignUpView.as_view(), name="signup"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("my-orders/", views.order_history, name="order_history"),
    path("drops/", views.drop_calendar, name="drop_calendar"),
    path("products/<int:product_id>/", views.product_detail, name="product_detail"),
    path("cart/", views.view_cart, name="cart"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path(
        "cart/remove/<int:product_id>/",
        views.remove_from_cart,
        name="remove_from_cart",
    ),
    path("checkout/", views.checkout, name="checkout"),
    path("order/success/", views.order_success, name="order_success"),
]
