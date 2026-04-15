from django import forms

from ..models import BillingScheduleSettings
from ..utils import validate_emails


class BillingScheduleSettingsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notification_email'].required = True
        self.fields['notification_email'].label = 'Email addresses'
        self.fields['notification_email'].help_text = 'Separate multiple addresses with semicolons or commas.'
        monthly = BillingScheduleSettings.SCHEDULE_MONTHLY
        labels = dict(BillingScheduleSettings.SCHEDULE_TYPE_CHOICES)
        self.fields['schedule_type'] = forms.CharField(
            max_length=20,
            required=False,
            widget=forms.Select(
                choices=[(monthly, labels[monthly])],
                attrs={
                    'class': 'form-control custom-select w-auto d-inline-block',
                    'aria-label': 'Schedule type (monthly only)',
                    'disabled': True,
                },
            ),
        )
        self.fields['schedule_type'].initial = monthly

    class Meta:
        model = BillingScheduleSettings
        fields = [
            'scheduling_enabled',
            'schedule_type',
            'start_date',
            'end_date',
            'notification_email',
            'email_subject',
            'email_content',
            'autoassign_no_cost_quota',
        ]
        widgets = {
            'scheduling_enabled': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input',
                    'aria-controls': 'scheduling-details',
                }
            ),
            'start_date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control w-auto d-inline-block',
                    'aria-label': 'Start date',
                }
            ),
            'end_date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control w-auto',
                    'aria-label': 'End date',
                }
            ),
            'notification_email': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'name@example.com; other@example.com',
                    'autocomplete': 'email',
                    'aria-label': 'Notification email addresses',
                }
            ),
            'email_subject': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'aria-label': 'Email subject',
                }
            ),
            'email_content': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 5,
                    'aria-label': 'Email content',
                }
            ),
            'autoassign_no_cost_quota': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input',
                    'aria-label': 'Autoassign no cost quota',
                }
            ),
        }

    def clean_notification_email(self):
        raw = self.cleaned_data.get('notification_email') or ''

        raw = raw.strip()
        if not raw:
            return ''

        valid_recipients, invalid_recipients = validate_emails(raw)

        if invalid_recipients:
            raise forms.ValidationError(
                'Invalid email address(es): %(addrs)s',
                params={'addrs': ', '.join(invalid_recipients)},
                code='invalid_notification_emails',
            )

        return '; '.join(valid_recipients)

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['schedule_type'] = BillingScheduleSettings.SCHEDULE_MONTHLY

        scheduling_enabled = cleaned_data.get('scheduling_enabled')

        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        notification_email = cleaned_data.get('notification_email')

        if scheduling_enabled:
            if not start_date:
                self.add_error('start_date', 'Start date is required when scheduling is enabled.')
            if not notification_email:
                self.add_error(
                    'notification_email',
                    'Email addresses are required when scheduling is enabled.',
                )

        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'End date cannot be earlier than start date.')

        return cleaned_data
