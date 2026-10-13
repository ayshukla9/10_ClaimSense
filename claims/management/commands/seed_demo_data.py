"""Explicit, repeatable synthetic patients, providers and bills for live demonstrations."""
import os
import random
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from claims.models import Bill, BillLineItem, InsurancePlan, Patient, Provider

CENT = Decimal("0.01")
OUT_OF_NETWORK_COVERAGE = Decimal("0.40")

# (name, netid, plan name, plan type, deductible, coinsurance %, out-of-pocket max, providers)
# Every person is fictional and every address is @example.com. Providers are
# (name, network status, kind of service); each plan gets its own, so staff
# charts show one bar per provider instead of repeated names.
PATIENTS = [
    ("Emma Carter", "ecarter1", "IlliniCare Student PPO", "PPO", 1500, 20, 6000, [
        ("Campus Health Center", "IN", "clinic"),
        ("Urbana Imaging Center", "IN", "imaging"),
        ("Regional Emergency Clinic", "OUT", "emergency"),
    ]),
    ("Liam Nguyen", "lnguyen2", "Prairie Health HMO", "HMO", 500, 10, 4000, [
        ("Prairie Family Medicine", "IN", "clinic"),
        ("Prairie Physical Therapy", "IN", "therapy"),
        ("Lakeside Specialty Hospital", "OUT", "hospital"),
    ]),
    ("Sofia Ramirez", "sramirez3", "Midwest Select EPO", "EPO", 2000, 25, 7000, [
        ("Midwest Primary Care", "IN", "clinic"),
        ("Champaign Family Dental", "IN", "dental"),
        ("Green Street Urgent Care", "OUT", "emergency"),
    ]),
    ("Noah Patel", "npatel4", "Heartland Family PPO", "PPO", 1000, 20, 5000, [
        ("Heartland Medical Group", "IN", "clinic"),
        ("Heartland Diagnostic Imaging", "IN", "imaging"),
        ("Riverbend Surgical Hospital", "OUT", "hospital"),
    ]),
    ("Ava Johnson", "ajohnson5", "Lincoln High-Deductible Plan", "OTHER", 3000, 30, 8000, [
        ("Lincoln Square Clinic", "IN", "clinic"),
        ("Lincoln Sports Therapy", "IN", "therapy"),
        ("Eastside Emergency Center", "OUT", "emergency"),
    ]),
]

# kind of service -> (description, procedure reference, typical charge)
SERVICES = {
    "clinic": [
        ("Primary care visit", "PCP-001", 180),
        ("Blood panel", "LAB-201", 300),
        ("Flu vaccination", "IMM-110", 65),
        ("Follow-up office visit", "PCP-002", 120),
    ],
    "imaging": [
        ("MRI imaging", "IMG-101", 1200),
        ("Radiology interpretation", "RAD-102", 250),
        ("Chest x-ray imaging", "IMG-103", 320),
        ("Ultrasound imaging", "IMG-104", 540),
    ],
    "therapy": [
        ("Physical therapy evaluation", "PT-401", 210),
        ("Physical therapy session", "PT-402", 140),
        ("Therapeutic exercise", "PT-403", 95),
    ],
    "dental": [
        ("Dental cleaning", "DEN-501", 150),
        ("Dental x-ray imaging", "DEN-502", 110),
        ("Cavity filling", "DEN-503", 280),
    ],
    "emergency": [
        ("Emergency department visit", "ER-301", 1800),
        ("Emergency blood panel", "ER-302", 420),
        ("Sutures and wound care", "ER-303", 650),
    ],
    "hospital": [
        ("Specialist consultation visit", "SPC-601", 450),
        ("CT scan imaging", "IMG-105", 1650),
        ("Outpatient surgery", "SUR-602", 4200),
    ],
}

BILLS_PER_PATIENT = 8


class Command(BaseCommand):
    help = (
        "Add labelled synthetic patients, providers, bills and line items for demos "
        "without changing existing records. Safe to run more than once."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--accounts", action="store_true",
            help="Also create one login per demo patient (username = netid) and link it. "
                 "Needs --password or the DEMO_PASSWORD environment variable.",
        )
        parser.add_argument("--password", help="Password for accounts created by --accounts.")
        parser.add_argument(
            "--link", action="append", default=[], metavar="USERNAME=NETID",
            help="Link an existing account (e.g. a Google signup) to a demo patient. Repeatable.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        links = self._parse_links(options["link"])
        password = options["password"] or os.environ.get("DEMO_PASSWORD")
        if options["accounts"] and not password:
            raise CommandError("--accounts needs --password or DEMO_PASSWORD.")

        created = dict.fromkeys(("plans", "patients", "providers", "bills", "line items", "accounts"), 0)
        patients = {}
        for index, row in enumerate(PATIENTS):
            patient = self._patient(row[:-1], created)
            patients[patient.netid] = patient
            self._bills(index, patient, row[-1], created)

        # Explicit links first, so --accounts only fills in patients nobody has claimed.
        for username, netid in links:
            if netid not in patients:
                raise CommandError(f"Unknown demo netid: {netid}")
            user = get_user_model().objects.filter(username=username).first()
            if user is None:
                raise CommandError(f"No account named {username}; sign up first.")
            self._link(patients[netid], user)
        if options["accounts"]:
            for patient in patients.values():
                if patient.user_id is None:
                    self._account(patient, password, created)

        summary = ", ".join(f"{count} {label}" for label, count in created.items())
        self.stdout.write(self.style.SUCCESS(f"Created {summary}. Existing records were preserved."))

    def _parse_links(self, values):
        links = []
        for value in values:
            username, sep, netid = value.partition("=")
            if not (sep and username and netid):
                raise CommandError(f"Expected USERNAME=NETID, got: {value}")
            links.append((username, netid))
        return links

    def _patient(self, row, created):
        name, netid, plan_name, plan_type, deductible, coinsurance, oop_max = row
        patient = Patient.objects.filter(netid=netid).select_related("insurance_plan").first()
        if patient is not None:
            if patient.name != name:
                raise CommandError(f"Conflicting patient for netid {netid}: {patient.name}")
            return patient
        # A plan belongs to at most one patient, so never borrow one that is taken.
        if InsurancePlan.objects.filter(name=plan_name).exists():
            raise CommandError(f"Conflicting catalogue entry: {plan_name}")
        plan = InsurancePlan.objects.create(
            name=plan_name, plan_type=plan_type, deductible=deductible,
            coinsurance_pct=coinsurance, out_of_pocket_max=oop_max,
        )
        created["plans"] += 1
        created["patients"] += 1
        return Patient.objects.create(
            name=name, netid=netid, email=f"{netid}@example.com", insurance_plan=plan,
        )

    def _bills(self, index, patient, provider_rows, created):
        plan = patient.insurance_plan
        providers = []
        for name, status, kind in provider_rows:
            provider, was_created = Provider.objects.get_or_create(
                name=name, insurance_plan=plan, defaults={"network_status": status},
            )
            created["providers"] += was_created
            providers.append((provider, kind))
        # Mostly in-network care, with the occasional out-of-network surprise.
        weights = [1 if status == "OUT" else 3 for _, status, _ in provider_rows]

        # Seeded per patient so every run plans exactly the same bills.
        rng = random.Random(f"claimsense-demo-{patient.netid}")
        for number in range(1, BILLS_PER_PATIENT + 1):
            provider, kind = rng.choices(providers, weights)[0]
            bill_date = date(2026, 1, 1 + index * 2) if number == 1 else date(
                2026, rng.randint(1, 9), rng.randint(1, 28)
            )
            services = rng.sample(SERVICES[kind], rng.randint(1, 3))
            charges = [self._charge(rng, typical) for _, _, typical in services]

            bill, was_created = Bill.objects.get_or_create(
                patient=patient, reference_number=f"DEMO-{index + 1}{number:03d}",
                defaults={"provider": provider, "insurance_plan": plan, "bill_date": bill_date},
            )
            if not was_created:
                continue
            created["bills"] += 1
            for line_number, ((description, reference, _), charged) in enumerate(zip(services, charges), 1):
                covered = self._covered(charged, plan, provider)
                BillLineItem.objects.create(
                    bill=bill, line_number=line_number, description=description,
                    procedure_reference=reference, charged_amount=charged,
                    estimated_covered_amount=covered,
                    estimated_patient_responsibility=charged - covered,
                )
                created["line items"] += 1

    @staticmethod
    def _charge(rng, typical):
        # Within 15% of the typical price, rounded to the nearest $5.
        return Decimal(round(typical * rng.uniform(0.85, 1.15) / 5) * 5)

    @staticmethod
    def _covered(charged, plan, provider):
        if provider.network_status == "IN":
            share = 1 - Decimal(plan.coinsurance_pct) / 100
        else:
            share = OUT_OF_NETWORK_COVERAGE
        return (charged * share).quantize(CENT)

    def _account(self, patient, password, created):
        User = get_user_model()
        user = User.objects.filter(username=patient.netid).first()
        if user is None:
            user = User.objects.create_user(patient.netid, email=patient.email, password=password)
            created["accounts"] += 1
        self._link(patient, user)

    def _link(self, patient, user):
        if patient.user_id == user.pk:
            return
        if patient.user_id is not None:
            raise CommandError(f"{patient.netid} is already linked to another account.")
        if Patient.objects.filter(user=user).exists():
            raise CommandError(f"{user.username} is already linked to another patient.")
        patient.user = user
        patient.save(update_fields=["user"])
        self.stdout.write(f"Linked {user.username} to {patient.name}.")
