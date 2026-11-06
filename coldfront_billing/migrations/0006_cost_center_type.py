from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("coldfront_billing", "0005_no_cost_quota_group")]

    operations = [
        migrations.RenameField(
            model_name="CostCenter",
            old_name="dept_id",
            new_name="name",
        ),
        migrations.AddField(
            model_name="CostCenter",
            name="cost_center_type",
            field=models.CharField(
                max_length=16,
                choices=[
                    ("department", "department"),
                    ("grant", "grant"),
                ],
                default="department",
                help_text="Cost center type (department or grant)",
            ),
        ),
    ]
