from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseForbidden
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import UpdateView

from coldfront_billing.forms import BillingScheduleSettingsForm
from coldfront_billing.models import BillingScheduleSettings


class ManageReportsView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    template_name = 'reports/manage.html'
    form_class = BillingScheduleSettingsForm
    success_url = reverse_lazy('reports_manage')

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return AccessMixin.handle_no_permission(self)
        return HttpResponseForbidden('You are not allowed to access this page.')

    def get_object(self, queryset=None):
        """
        Singleton settings row.
        Creates it automatically on first access.
        """
        obj, _created = BillingScheduleSettings.objects.get_or_create(
            pk=1,
            defaults={
                'scheduling_enabled': True,
                'start_date': timezone.localdate(),
                'notification_email': '',
                'email_subject': '',
                'email_content': '',
                'autoassign_no_cost_quota': False,
            },
        )
        return obj

    def form_valid(self, form):
        response = super().form_valid(form)

        messages.success(self.request, 'Billing scheduling settings were updated.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['schedule_settings'] = self.object
        return context
