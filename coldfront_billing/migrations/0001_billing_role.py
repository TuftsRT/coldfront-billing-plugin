from django.db import migrations


def add_role(apps, schema_editor):
    RoleChoice = apps.get_model('project', 'ProjectUserRoleChoice')
    RoleChoice.objects.get_or_create(name='Billing')


def remove_role(apps, schema_editor):
    RoleChoice = apps.get_model('project', 'ProjectUserRoleChoice')
    RoleChoice.objects.filter(name='Billing').delete()


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.RunPython(add_role, remove_role),
    ]
