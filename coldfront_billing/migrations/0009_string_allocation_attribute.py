from django.db import migrations

from coldfront_billing.constants import ALLOCATION_QUOTA_ATTRIBUTE_NAME


def create_string_allocation_attribute(apps, schema_editor):
    AllocationAttributeType = apps.get_model("allocation", "AllocationAttributeType")
    AttributeType = apps.get_model("allocation", "AttributeType")

    text_attr_type, _ = AttributeType.objects.get_or_create(name="Text")

    AllocationAttributeType.objects.get_or_create(
        name=ALLOCATION_QUOTA_ATTRIBUTE_NAME,
        defaults={
            "attribute_type": text_attr_type,
            "has_usage": False,
            "is_changeable": True,
            "is_unique": True,
        },
    )


def remove_string_allocation_attribute(apps, schema_editor):
    AllocationAttributeType = apps.get_model("allocation", "AllocationAttributeType")
    AllocationAttributeType.objects.filter(name=ALLOCATION_QUOTA_ATTRIBUTE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coldfront_billing", "0008_billing_schedule_history"),
    ]

    operations = [
        migrations.RunPython(create_string_allocation_attribute, remove_string_allocation_attribute),
    ]
