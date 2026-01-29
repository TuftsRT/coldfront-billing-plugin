from django.db import migrations

from coldfront_billing.constants import cost_attr_name, quota_attr_name


def create_billing_attributes(apps, schema_editor):
    AllocationAttributeType = apps.get_model('allocation', 'AllocationAttributeType')
    AttributeType = apps.get_model('allocation', 'AttributeType')

    float_attr_type, _ = AttributeType.objects.get_or_create(name='Float')

    AllocationAttributeType.objects.get_or_create(
        name=quota_attr_name,
        defaults={
            'attribute_type': float_attr_type,
            'has_usage': True,
            'is_changeable': True,
        },
    )

    ResourceAttributeType = apps.get_model('resource', 'ResourceAttributeType')
    AttributeType = apps.get_model('resource', 'AttributeType')

    text_attr_type, _ = AttributeType.objects.get_or_create(name='Text')

    ResourceAttributeType.objects.get_or_create(
        name=cost_attr_name,
        defaults={
            'attribute_type': text_attr_type,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ('coldfront_billing', '0001_billing_role'),
    ]

    operations = [
        migrations.RunPython(create_billing_attributes),
    ]
