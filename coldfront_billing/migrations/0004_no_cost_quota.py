import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from coldfront_billing.constants import NO_COST_QUOTA_TYPE_ATTR_NAME


def create_storage_tier_attribute_type(apps, schema_editor):
    ResourceAttributeType = apps.get_model('resource', 'ResourceAttributeType')
    AttributeType = apps.get_model('resource', 'AttributeType')

    text_attr_type, _ = AttributeType.objects.get_or_create(name='Text')

    ResourceAttributeType.objects.get_or_create(
        name=NO_COST_QUOTA_TYPE_ATTR_NAME,
        defaults={
            'attribute_type': text_attr_type,
        },
    )


def remove_storage_tier_attribute_type(apps, schema_editor):
    ResourceAttributeType = apps.get_model('resource', 'ResourceAttributeType')
    ResourceAttributeType.objects.filter(name=NO_COST_QUOTA_TYPE_ATTR_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('allocation', '__first__'),
        ('coldfront_billing', '0003_cost_center_assignment'),
    ]

    operations = [
        migrations.CreateModel(
            name='NoCostQuota',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'quota_type',
                    models.CharField(max_length=64, help_text='Storage no-cost quota type (e.g. tier_1, tier_2).'),
                ),
                ('amount', models.FloatField(help_text='Total quota amount')),
                ('units', models.CharField(default='TB', max_length=16, help_text='Units for the quota (TB or GB)')),
                ('minimum_increment', models.FloatField(help_text='Minimum allocation increment')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='no_cost_quotas',
                        to=settings.AUTH_USER_MODEL,
                        help_text='User who owns this no-cost quota',
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='NoCostQuotaAllotment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.FloatField(help_text='Allocated quota amount in TB')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                (
                    'allocation',
                    models.ForeignKey(
                        help_text='Allocation for a resource with no-cost quota type',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='no_cost_quota_allotments',
                        to='allocation.allocation',
                    ),
                ),
                (
                    'no_cost_quota',
                    models.ForeignKey(
                        help_text='No-cost quota used for this allotment',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='allotments',
                        to='coldfront_billing.nocostquota',
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name='nocostquota',
            constraint=models.UniqueConstraint(
                fields=['user', 'quota_type'],
                name='uniq_nocostquota_user_quota_type',
            ),
        ),
        migrations.AddConstraint(
            model_name='nocostquotaallotment',
            constraint=models.UniqueConstraint(
                fields=['no_cost_quota', 'allocation'],
                name='uniq_nocostquotaallotment_quota_allocation',
            ),
        ),
        migrations.RunPython(
            create_storage_tier_attribute_type,
            reverse_code=remove_storage_tier_attribute_type,
        ),
    ]
