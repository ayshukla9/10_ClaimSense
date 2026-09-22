# ClaimSense Part 4 - Data Model Notes

## Project and App Naming

The Django project is named `claimsense_project` because it represents
the overall ClaimSense web application.

The Django app is named `claims` because it contains the core domain
models for patients, insurance plans, providers, medical bills, and
bill line items.

## Models

ClaimSense contains five core models:

1. InsurancePlan
2. Patient
3. Provider
4. Bill
5. BillLineItem

## Relationships

- A Patient is linked to one active InsurancePlan.
- An InsurancePlan may be associated with multiple Providers.
- A Patient may have multiple Bills.
- A Provider may issue multiple Bills.
- An InsurancePlan may be associated with multiple Bills.
- A Bill may contain multiple BillLineItems.

## on_delete Decisions

`PROTECT` is used for Patient, Provider, and InsurancePlan relationships
referenced by Bills. This prevents historical billing records from
losing the entities associated with them.

`CASCADE` is used between Bill and BillLineItem because a line item
has no independent meaning without its parent Bill.

## Unique Constraints

BillLineItem uses a multi-field UniqueConstraint on `(bill, line_number)`.
This prevents duplicate line numbers within the same bill.

Bill uses a multi-field UniqueConstraint on `(patient, reference_number)`.
This prevents the same bill reference from being entered twice for the
same patient.

Provider uses a multi-field UniqueConstraint on `(name, insurance_plan)`.
This prevents duplicate provider entries within the same insurance plan.

## Ordering

- InsurancePlan records are ordered alphabetically by name.
- Patient records are ordered alphabetically by name.
- Provider records are ordered alphabetically by name.
- Bills are ordered by bill date in descending order.
- BillLineItems are ordered by Bill and then line number.

## Test Data and Validation

All test data used in ClaimSense is synthetic.

Five Bills and their related BillLineItems were created in Django Admin.

The multi-field uniqueness constraint was validated by attempting to
create a duplicate line number within the same Bill.

The `PROTECT` behavior was validated by attempting to delete a Provider
referenced by existing Bills.

The `CASCADE` behavior was validated by deleting a temporary Bill and
confirming that its related BillLineItems were also deleted.

## Reference

Django 5.2 model field documentation:
https://docs.djangoproject.com/en/5.2/ref/models/fields/
## Superuser Accounts (corrected)

The assignment requires a superuser named `tester` or `mohitg2` (both variants
appear in the assignment text), password `uiuc12345`. The originally submitted
database only had personal accounts (`Pooja`, `Omkar`), which is why grading
marked this requirement as missing (-1pt).

Both required accounts now exist in this database, alongside the original ones:

| Username | Password | Role |
| --- | --- | --- |
| `tester` | `uiuc12345` | required by assignment |
| `mohitg2` | `uiuc12345` | required by assignment |
| `Pooja` | (team's own) | original team superuser |
| `Omkar` | (team's own) | original team staff account |
