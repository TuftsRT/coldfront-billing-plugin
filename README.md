# coldfront-billing-plugin

A [ColdFront](https://github.com/coldfront/coldfront) plugin that adds storage billing, cost tracking, and allocation quota management to your ColdFront deployment.

## Features

- **Cost tracking** — calculates monthly storage costs per allocation from quota (TB) and cost-per-TB resource attributes
- **Cost center routing** — assigns project charges to department and grant cost centers with configurable percentage splits
- **No-cost quotas** — allocates free storage quota to users (individually or via Django groups) that can be applied against paid allocations
- **Billing reports** — generates and emails a monthly CSV report with per-department cost breakdowns
- **Automated scheduling** — runs monthly billing report generation via [django-q2](https://django-q2.readthedocs.io/), with optional no-cost quota auto-assignment
- **Billing dashboard** — list and detail views for PIs and billing staff showing allocation costs and quota usage
- **Allocation workflow integration** — intercepts ColdFront's allocation create/change views to collect quota and cost center information upfront

## Requirements

- Python ≥ 3.10
- ColdFront ≥ 1.1.9, < 2 (Bootstrap 5)
- Django 5.2+
- [django-q2](https://django-q2.readthedocs.io/) (optional, required for scheduled reports)

Version 3 targets ColdFront 1.1.9, whose templates use Bootstrap 5. For ColdFront 1.1.7/1.1.8
(Bootstrap 4), use the 2.x releases from the `bootstrap4` branch.

The plugin's templates and scripts use Bootstrap 5's `data-bs-*` attributes and don't call
Bootstrap from JavaScript: ColdFront's bundle doesn't expose Bootstrap's API (there is no
`window.bootstrap` or `$.fn.modal`). Popovers are set up by ColdFront at page load, so they only
work on elements present when the page loads.

## Installation

```bash
pip install coldfront-billing
```

## Configuration

### 1. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    # ... existing ColdFront apps ...
    'coldfront_billing',
]
```

The plugin automatically registers its signal handlers and overrides ColdFront's `AllocationCreateView` and `AllocationChangeView` with billing-aware versions.

### 2. Add URL patterns

In your project's `urls.py`, include the plugin's URL patterns:

```python
from django.urls import path, include

urlpatterns = [
    # ... existing URL patterns ...
    path('', include('coldfront_billing.urls')),
]
```

### 3. Configure ColdFront resource attributes

The plugin reads quota and cost values from ColdFront's allocation/resource attribute system. Create the following attributes in your ColdFront instance:

| Attribute | Type | Description |
|---|---|---|
| `quota_in_terabyte` | `AllocationAttributeType` | Storage quota for an allocation, in TB |
| `cost_per_terabyte` | `ResourceAttributeType` | Monthly cost per TB for a storage resource |
| `no_cost_quota_type` | `ResourceAttributeType` | Identifies which no-cost quota type applies to a resource |
| `allocation_no_cost_quota` | `AllocationAttributeType` | Tracks applied no-cost quota on an allocation (optional) |

The attribute names are configurable via environment variables (see [Environment variables](#environment-variables) below).

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Configure ColdFront roles (optional)

The plugin checks for two Django group roles:

- **Billing** — users who can view billing dashboards across all projects
- **Manager** — users with elevated access in billing views

Create these Django groups and assign users as needed.

## Settings

All settings are optional and have sensible defaults.

### Django settings

Configure these in your `local_settings.py` or equivalent:

| Setting | Default | Description |
|---|---|---|
| `COLDFRONT_BILLING_ALLOCATION_EMAIL_ENABLED` | ColdFront's `EMAIL_ENABLED` | Whether to send quota-approval emails to the PI and requester. Unset (or `None`), it follows `EMAIL_ENABLED`, so turning off ColdFront's emails turns these off too. Doesn't affect the monthly billing report, which is controlled by the schedule's "Schedule enabled" setting. |
| `COLDFRONT_BILLING_EMAIL_FROM` | `'billing@tufts.com'` | From address for billing notification emails |
| `COLDFRONT_BILLING_ALLOCATION_EMAIL_SUBJECT` | `'Storage quota updated for {project_name}'` | Subject template for quota-approval emails |
| `COLDFRONT_BILLING_ALLOCATION_EMAIL_BODY` | *(see below)* | Body template for quota-approval emails |
| `COLDFRONT_BILLING_ALLOCATION_EMAIL_NO_COST_PENDING` | `'The no-cost quota you asked to apply to this allocation is still to be applied, so the cost above does not include it yet.'` | Added to the body, after a blank line, when a no-cost quota the requester asked to apply couldn't be applied automatically. Takes the same placeholders as the body |
| `COLDFRONT_BILLING_MAX_COST_CENTER_ASSIGNMENTS` | `10` | Maximum cost center rows per project |
| `COLDFRONT_BILLIG_REPORTS_TOTAL_DEPT_NAME` | `'C800260'` | Department code used for report totals row |
| `COLDFRONT_BILLIG_REPORTS_TOTAL_DESCRIPTION` | `'Storage Charges'` | Description used for report totals row |
| `COLDFRONT_BILLING_REPORT_HOUR` | `8` | Hour of day (UTC) to run the monthly billing report |
| `COLDFRONT_BILLING_USE_TEST_SCHEDULING` | `False` | Use 5-minute schedule instead of monthly (for testing) |
| `COLDFRONT_BILLING_DEFAULT_QUOTA` | `0` | Default quota (TB) when attribute is missing |
| `COLDFRONT_BILLING_DEFAULT_COST` | `10` | Default cost ($/TB) when attribute is missing |

Default email body template:
```
The storage quota amount for your project {project_name} has been changed to {quota_amount}.
This new quota will incur a monthly cost of {cost}.
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `COLDFRONT_BILLING_QUOTA_ATTRIBUTE_NAME` | `quota_in_terabyte` | Name of the AllocationAttributeType for quota |
| `COLDFRONT_BILLING_COST_ATTRIBUTE_NAME` | `cost_per_terabyte` | Name of the ResourceAttributeType for cost |
| `COLDFRONT_BILLING_NO_COST_QUOTA_TYPE_ATTR_NAME` | `no_cost_quota_type` | Name of the ResourceAttributeType for no-cost quota type |

## No-Cost Quotas

No-cost quotas let you allocate free storage to users that they can apply to reduce or eliminate costs on paid allocations.

- **Per-user quotas** — grant a specific TB amount to a user for a given quota type
- **Group-based quotas** — assign a `NoCostQuotaGroup` to a Django group; a `NoCostQuota` is automatically created for each user added to the group
- **Allotments** — a portion of a user's no-cost quota applied to a specific allocation; tracked separately so the remaining balance is always visible
- **Auto-assignment** — the scheduled billing task can automatically apply no-cost quotas to eligible allocations
- **Allotment failures** — when a requester asks to apply a no-cost quota, the allotment is made as the allocation becomes active or its change is approved. If it can't be made (the quota has run out, say, or the amount isn't a multiple of the increment), the allocation is still activated; the failure is logged and recorded as a `NoCostQuotaAllotmentFailure`, listed in the Django admin. It's resolved automatically once an allotment from that quota is saved for the allocation, or by setting its resolved fields in the admin. Unresolved failures are there for a site to surface however it likes, such as in an alerts list

## Scheduled Reports

When django-q2 is installed and a worker is running, the plugin can send monthly billing reports automatically.

Configure the schedule via the **Manage Reports** admin page (`/billing/reports/manage`). Options include:

- Schedule frequency (monthly, with configurable hour)
- Email recipients for the report
- Whether to auto-assign no-cost quotas before generating the report

The **Billing Schedule History** page (`/billing/reports/history`) shows execution logs for past report runs.

To send a report immediately without waiting for the schedule, use the **Send Report** page (`/billing/reports/send`).

## URL Reference

| URL | Name | Description |
|---|---|---|
| `/billing/` | `billing_index` | Billing dashboard (list of projects with costs) |
| `/billing/<project_id>/` | `billing_details` | Per-project allocation cost breakdown |
| `/billing/reports/manage` | `reports_manage` | Admin: configure billing schedule |
| `/billing/reports/export` | `reports_export` | Download CSV billing report |
| `/billing/reports/send` | `reports_send` | Manually trigger report email |
| `/billing/reports/history` | `reports_billing_history` | Billing schedule execution history |
| `/no-cost-quota/manage/` | `manage_no_cost_quota` | Manage user no-cost quotas |
| `/no-cost-quota/assign/` | `assign_no_cost_quota` | Assign no-cost quota allotments to allocations |

## Development

### Setup

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running tests

```bash
pytest
```

### Code style

The project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check .
ruff format .
```

## License
This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).
