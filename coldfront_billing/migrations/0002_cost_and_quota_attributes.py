from django.db import migrations

from coldfront_billing.constants import COST_ATTR_NAME, QUOTA_ATTR_NAME


def create_billing_attributes(apps, schema_editor):
    AllocationAttributeType = apps.get_model("allocation", "AllocationAttributeType")
    AttributeType = apps.get_model("allocation", "AttributeType")

    float_attr_type, _ = AttributeType.objects.get_or_create(name="Float")

    AllocationAttributeType.objects.get_or_create(
        name=QUOTA_ATTR_NAME,
        defaults={
            "attribute_type": float_attr_type,
            "has_usage": True,
            "is_changeable": True,
            "is_unique": True,
        },
    )

    ResourceAttributeType = apps.get_model("resource", "ResourceAttributeType")
    AttributeType = apps.get_model("resource", "AttributeType")

    float_attr_type, _ = AttributeType.objects.get_or_create(name="Float")

    ResourceAttributeType.objects.get_or_create(
        name=COST_ATTR_NAME,
        defaults={
            "attribute_type": float_attr_type,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("coldfront_billing", "0001_billing_role"),
    ]

    operations = [
        migrations.RunPython(create_billing_attributes),
    ]
