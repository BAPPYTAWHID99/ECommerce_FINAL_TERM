import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a superuser from deployment environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")

        if not username or not email or not password:
            raise CommandError(
                "Set DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, "
                "and DJANGO_SUPERUSER_PASSWORD to create the deployment admin."
            )

        user_model = get_user_model()
        existing_user = user_model._default_manager.filter(username=username).first()
        if existing_user:
            if existing_user.is_staff and existing_user.is_superuser:
                self.stdout.write("Deployment admin already exists; no changes made.")
                return
            raise CommandError(
                "That username already belongs to a non-admin account. "
                "Choose a different DJANGO_SUPERUSER_USERNAME."
            )

        user_model._default_manager.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS("Deployment admin created."))
