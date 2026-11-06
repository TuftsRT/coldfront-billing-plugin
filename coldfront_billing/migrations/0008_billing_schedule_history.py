from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("coldfront_billing", "0007-billing_schedule_settings")]

    operations = [
        migrations.CreateModel(
            name="BillingScheduleHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("started", models.DateTimeField()),
                (
                    "stopped",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("success", "Success"),
                            ("FAILED_AUTOASSIGN", "Failed autoassign"),
                            ("FAILED_REPORT", "Failed report"),
                            ("FAILED_MAIL", "Failed mail"),
                        ],
                        max_length=64,
                    ),
                ),
                ("details", models.TextField(blank=True, default="")),
            ],
            options={
                "verbose_name": "Billing schedule history",
                "verbose_name_plural": "Billing schedule histories",
            },
        ),
    ]
