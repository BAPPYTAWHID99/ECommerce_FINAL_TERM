from django import forms

from .models import Artisan, Drop, Order, OrderItem, Product


class AdminModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = (
                    "h-4 w-4 rounded border-stone-600 accent-amber-500"
                )
            else:
                field.widget.attrs["class"] = (
                    "mt-1 block w-full rounded-xl border border-white/10 "
                    "bg-[#111111] px-3 py-2.5 text-sm text-stone-100 "
                    "outline-none transition focus:border-amber-500"
                )


class ArtisanForm(AdminModelForm):
    class Meta:
        model = Artisan
        fields = ("name", "bio", "specialty")
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}


class DropForm(AdminModelForm):
    drop_datetime = forms.DateTimeField(
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"),
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"type": "datetime-local"},
        ),
    )

    class Meta:
        model = Drop
        fields = ("title", "drop_datetime", "is_active")


class OrderForm(AdminModelForm):
    class Meta:
        model = Order
        fields = (
            "customer_name",
            "customer_email",
            "shipping_address",
            "city",
            "postal_code",
            "country",
            "total_amount",
        )


class OrderItemForm(AdminModelForm):
    class Meta:
        model = OrderItem
        fields = ("order", "product", "quantity", "price_at_purchase")


class ProductForm(AdminModelForm):
    class Meta:
        model = Product
        fields = (
            "name",
            "description",
            "price",
            "stock_quantity",
            "drop",
            "artisan",
            "image_url",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
