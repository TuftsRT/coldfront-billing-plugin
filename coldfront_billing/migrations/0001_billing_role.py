from django.db import migrations

from coldfront_billing.constants import BILLING_ROLE_NAME, MANAGER_ROLE_NAME


def add_role(apps, schema_editor):
    RoleChoice = apps.get_model('project', 'ProjectUserRoleChoice')
    for role in (BILLING_ROLE_NAME, MANAGER_ROLE_NAME):
        RoleChoice.objects.get_or_create(name=role)


def remove_role(apps, schema_editor):
    RoleChoice = apps.get_model('project', 'ProjectUserRoleChoice')
    for role in (BILLING_ROLE_NAME, MANAGER_ROLE_NAME):
        RoleChoice.objects.filter(name=role).delete()


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.RunPython(add_role, remove_role),
    ]
