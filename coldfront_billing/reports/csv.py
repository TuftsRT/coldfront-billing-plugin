import csv
from datetime import datetime
from io import StringIO

from coldfront.core.project.models import Project
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from coldfront_billing.constants import (
    BILLIG_REPORTS_TOTAL_DEPT_NAME,
    BILLIG_REPORTS_TOTAL_DESCRIPTION,
    BILLING_ATTRIBUTE_NAME,
)
from coldfront_billing.data.billing import create_billing_allocations
from coldfront_billing.prefetch import get_projects_prefetch
from coldfront_billing.utils import get_month_abbr

ACCOUNT_NAME = getattr(
    settings,
    'COLDFRONT_BILLING_ACCOUNT_NAME',
    1234,
)
DESCRIPTION_PREFIX = getattr(
    settings,
    'COLDFRONT_BILLING_DESCRIPTION_PREFIX',
    'TTS',
)


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
            description = f'{month}-{DESCRIPTION_PREFIX}-{user_id}-{project.title}'

            for assignement in sorted(assignments, key=lambda x: x.get('department')):
                dept_id = assignement.get('department')
                pct = assignement.get('percentage')
                grant = assignement.get('grant', '')
                cost = round(project_cost * (int(pct) / 100), 2)
                total_cost += cost
                writer.writerow(
                    (
                        ACCOUNT_NAME,
                        dept_id,
                        grant,
                        f'{cost:.2f}',
                        description,
                    )
                )
        writer.writerow(
            (
                ACCOUNT_NAME,
                BILLIG_REPORTS_TOTAL_DEPT_NAME,
                '',
                f'-{total_cost:.2f}',
                f'{month}-{DESCRIPTION_PREFIX}-{BILLIG_REPORTS_TOTAL_DESCRIPTION}',
            )
        )

        return filename, output.getvalue()
