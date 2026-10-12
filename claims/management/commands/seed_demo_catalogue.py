"""Explicit, repeatable synthetic catalogue setup for assignment demonstrations."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from claims.models import InsurancePlan


class Command(BaseCommand):
    help = "Add six labelled synthetic catalogue plans without changing existing records."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for plan_type, count in (("HMO", 3), ("EPO", 2), ("OTHER", 1)):
            for number in range(1, count + 1):
                name = f"Synthetic A5 demo {plan_type} {number}"
                existing = InsurancePlan.objects.filter(name=name)
                if existing.exists():
                    if existing.count() != 1 or existing.get().plan_type != plan_type:
                        raise CommandError(f"Conflicting catalogue entry: {name}")
                    continue
                InsurancePlan.objects.create(
                    name=name, plan_type=plan_type, deductible=0,
                    coinsurance_pct=0, out_of_pocket_max=0,
                )
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f"Created {created} synthetic plans. Existing records were preserved."
        ))
