from django.db import models

# Create your models here.
from django.db import models


class InsurancePlan(models.Model):
    """
    Represents a patient's active health insurance plan.
    Stores simplified insurance rules used to estimate medical bill costs.
    """

    PLAN_TYPES = [
        ("PPO", "PPO"),
        ("HMO", "HMO"),
        ("EPO", "EPO"),
        ("OTHER", "Other"),
    ]

    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=10, choices=PLAN_TYPES)
    deductible = models.DecimalField(max_digits=10, decimal_places=2)
    coinsurance_pct = models.DecimalField(max_digits=5, decimal_places=2)
    out_of_pocket_max = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.plan_type})"


class Patient(models.Model):
    """
    Represents a ClaimSense user whose medical bills are tracked.
    Each patient is linked to one active insurance plan.
    """

    name = models.CharField(max_length=100)
    netid = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True)

    insurance_plan = models.OneToOneField(
        InsurancePlan,
        on_delete=models.PROTECT,
        related_name="patient",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Provider(models.Model):
    """
    Represents a hospital, clinic, or healthcare provider.
    Stores the provider's network status for a particular insurance plan.
    """

    NETWORK_STATUS = [
        ("IN", "In Network"),
        ("OUT", "Out of Network"),
    ]

    name = models.CharField(max_length=150)

    insurance_plan = models.ForeignKey(
        InsurancePlan,
        on_delete=models.PROTECT,
        related_name="providers",
    )

    network_status = models.CharField(
        max_length=3,
        choices=NETWORK_STATUS,
    )

    class Meta:
        ordering = ["name"]

        constraints = [
            models.UniqueConstraint(
                fields=["name", "insurance_plan"],
                name="unique_provider_per_plan",
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.get_network_status_display()}"


class Bill(models.Model):
    """
    Represents one medical bill received by a patient.
    Connects the patient, provider, and insurance plan active at the time.
    """

    reference_number = models.CharField(max_length=50)

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="bills",
    )

    provider = models.ForeignKey(
        Provider,
        on_delete=models.PROTECT,
        related_name="bills",
    )

    insurance_plan = models.ForeignKey(
        InsurancePlan,
        on_delete=models.PROTECT,
        related_name="bills",
    )

    bill_date = models.DateField()

    class Meta:
        ordering = ["-bill_date"]

        constraints = [
            models.UniqueConstraint(
                fields=["patient", "reference_number"],
                name="unique_bill_reference_per_patient",
            )
        ]

    def __str__(self):
        return f"{self.reference_number} - {self.patient.name}"


class BillLineItem(models.Model):
    """
    Represents an individual charge within a medical bill.
    Each line item stores the amount charged and the estimated
    insurer and patient responsibility.
    """

    bill = models.ForeignKey(
        Bill,
        on_delete=models.CASCADE,
        related_name="line_items",
    )

    line_number = models.PositiveIntegerField()
    description = models.CharField(max_length=200)

    procedure_reference = models.CharField(
        max_length=50,
        blank=True,
    )

    charged_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    estimated_covered_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    estimated_patient_responsibility = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    class Meta:
        ordering = ["bill", "line_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["bill", "line_number"],
                name="unique_line_number_per_bill",
            )
        ]

    def __str__(self):
        return f"{self.bill.reference_number} - Line {self.line_number}"