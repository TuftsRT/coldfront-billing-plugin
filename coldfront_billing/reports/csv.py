import csv
from datetime import datetime
from io import StringIO
from decimal import Decimal

from coldfront.core.project.models import Project
from django.core.exceptions import ObjectDoesNotExist

from coldfront_billing.constants import (
    BILLING_REPORTS_TOTAL_DEPT_NAME,
    BILLING_REPORTS_TOTAL_DESCRIPTION,
    BILLING_ATTRIBUTE_NAME,
    BILLING_DEBIT_ACCOUNT_NAME,
    BILLING_CREDIT_ACCOUNT_NAME,
    BILLING_DESCRIPTION_PREFIX,
    BILLING_IGNORE_DEPTID_PREFIX_LIST,
)
from coldfront_billing.data.billing import create_billing_allocations
from coldfront_billing.prefetch import get_projects_prefetch
from coldfront_billing.utils import get_month_abbr, elide_middle


def create_csv_report() -> tuple[str, str]:
    filename = f'report_{datetime.now().strftime("%Y-%m-%d_%H-%M")}.csv'
    month = get_month_abbr()

    projects = get_projects_prefetch(Project.objects.all())

    with StringIO() as output:
        writer = csv.writer(output)
        writer.writerow(['Account', 'DeptId', 'Project Number', 'Cost', 'Description'])
        total_cost = 0

        for project in projects:
            try:
                assignments = project.cost_center_assignment.assignments or []
            except ObjectDoesNotExist:
                continue

            billing_allocations = create_billing_allocations(getattr(project, BILLING_ATTRIBUTE_NAME, []))
            project_cost = sum(b.total_cost for b in billing_allocations)

            if not project_cost:
                continue

            user_id = project.pi.username
            # description is limited to 30 characters, so we need to elide the project title if it's too long
            description = f'{month}-{BILLING_DESCRIPTION_PREFIX}-{user_id}-'
            description += elide_middle(project.title, max_length=30 - len(description))
    
            for assignment in sorted(assignments, key=lambda x: x.get('department')):
                dept_id = assignment.get('department')
                if any(dept_id.lower().startswith(prefix.lower()) for prefix in BILLING_IGNORE_DEPTID_PREFIX_LIST):
                    continue
                pct = assignment.get('percentage')
                grant = assignment.get('grant', '')
                cost = (project_cost * Decimal(int(pct) / 100)).quantize(Decimal('0.01'))  # Round to 2 decimal places
                total_cost += cost
                writer.writerow(
                    (
                        BILLING_DEBIT_ACCOUNT_NAME,
                        dept_id,
                        grant,
                        f'{cost:.2f}',
                        description,
                    )
                )
        writer.writerow(
            (
                BILLING_CREDIT_ACCOUNT_NAME,
                BILLING_REPORTS_TOTAL_DEPT_NAME,
                '',
                f'-{total_cost:.2f}',
                f'{month}-{BILLING_DESCRIPTION_PREFIX}-{BILLING_REPORTS_TOTAL_DESCRIPTION}',
            )
        )

        return filename, output.getvalue()
