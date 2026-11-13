"""Create (or update) a staff login, e.g. the grader's test account for the analytics dashboard.

    python manage.py create_staff_account mohitg2 --password '<password>'
    STAFF_PASSWORD='<password>' python manage.py create_staff_account mohitg2

Staff (not superuser): can open /analytics/ and see all records, cannot use /admin/ user management.
The password is never stored in the repo; pass it on the command line or in STAFF_PASSWORD.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update a staff (non-superuser) account."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--password", default=os.environ.get("STAFF_PASSWORD", ""))
        parser.add_argument("--email", default="")

    def handle(self, *args, username, password, email, **opts):
        if not password:
            raise CommandError("Give --password or set STAFF_PASSWORD.")
        user, created = get_user_model().objects.get_or_create(username=username, defaults={"email": email})
        user.is_staff, user.is_active = True, True
        if email:
            user.email = email
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} staff account {username!r}."))
