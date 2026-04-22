from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('coldfront_billing', '0006_cost_center_type')]

    operations = [
        migrations.CreateModel(
            name='BillingScheduleSettings',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'scheduling_enabled',
                    models.BooleanField(default=True),
                ),
                (
                    'start_date',
                    models.DateField(),
                ),
                (
                    'end_date',
                    models.DateField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    'notification_email',
                    models.CharField(
                        blank=True,
                        default='',
                        help_text='One or more addresses separated by semicolon or comma.',
                        max_length=2048,
                    ),
                ),
                (
                    'email_subject',
                    models.CharField(
                        blank=True,
                        default='',
                        max_length=255,
                    ),
                ),
                (
                    'email_content',
                    models.TextField(
                        blank=True,
                        default='',
                    ),
                ),
                (
                    'autoassign_no_cost_quota',
                    models.BooleanField(default=False),
                ),
                (
                    'scheduler_external_id',
                    models.CharField(
                        blank=True,
                        default='',
                        help_text='Optional external scheduler identifier.',
                        max_length=255,
                    ),
                ),
                (
                    'created_at',
                    models.DateTimeField(
                        auto_now_add=True,
                    ),
                ),
                (
                    'updated_at',
                    models.DateTimeField(
                        auto_now=True,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Billing schedule settings',
                'verbose_name_plural': 'Billing schedule settings',
            },
        ),
    ]
