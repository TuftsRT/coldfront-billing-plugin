from django.db import migrations, models
from django.db.models.deletion import CASCADE


class Migration(migrations.Migration):
    dependencies = [
        ("coldfront_billing", "0004_no_cost_quota"),
    ]

    operations = [
        migrations.CreateModel(
            name="NoCostQuotaGroup",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "group",
                    models.OneToOneField(
                        help_text="Django Group - when a user is added to this group, a NoCostQuota is created for them",
                        on_delete=CASCADE,
                        related_name="no_cost_quota_group",
                        to="auth.group",
                    ),
                ),
                ("quota_type", models.CharField(max_length=64, help_text="Storage quota name")),
                (
                    "description",
                    models.CharField(
                        blank=True,
                        help_text="Human-readable description of the quota type",
                        max_length=128,
                    ),
                ),
                ("amount", models.FloatField(help_text="Total quota amount")),
                (
                    "units",
                    models.CharField(
                        choices=[("TB", "TB"), ("GB", "GB")],
                        default="TB",
                        help_text="Units for the quota (default: TB). Allowed: TB, GB.",
                        max_length=16,
                    ),
                ),
                ("minimum_increment", models.FloatField(help_text="Minimum allocation increment")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
