from django.db import migrations

from coldfront_billing.constants import BILLING_ROLE_NAME


def add_role(apps, schema_editor):
    RoleChoice = apps.get_model('project', 'ProjectUserRoleChoice')
    RoleChoice.objects.get_or_create(name=BILLING_ROLE_NAME)


def remove_role(apps, schema_editor):
    RoleChoice = apps.get_model('project', 'ProjectUserRoleChoice')
    RoleChoice.objects.filter(name=BILLING_ROLE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.RunPython(add_role, remove_role),
    ]
