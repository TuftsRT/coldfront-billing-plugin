from django.contrib import admin

from .models import (
    CostCenter,
    CostCenterAssignment,
    NoCostQuota,
    NoCostQuotaAllotment,
    NoCostQuotaAllotmentFailure,
    NoCostQuotaGroup,
)


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ['name', 'cost_center_type']
    search_fields = ['name', 'cost_center_type']
    ordering = ['name', 'cost_center_type']


@admin.register(CostCenterAssignment)
class CostCenterAssignmentAdmin(admin.ModelAdmin):
    list_display = ['project', 'assignments', 'created', 'modified']
    list_filter = ['created', 'modified']
    search_fields = ['project__title', 'project__pi__username']
    readonly_fields = ['created', 'modified']

    fieldsets = [
        (None, {'fields': ['project', 'assignments']}),
        ('Timestamps', {'fields': ['created', 'modified'], 'classes': ['collapse']}),
    ]


@admin.register(NoCostQuota)
class NoCostQuotaAdmin(admin.ModelAdmin):
    list_display = ['user', 'quota_type', 'description', 'amount_tb', 'units', 'increment_gb', 'created', 'updated']
    list_filter = ['quota_type', 'created', 'updated']
    search_fields = ['user__username', 'user__email', 'quota_type']
    readonly_fields = ['created', 'updated']
    ordering = ['user', 'quota_type']


@admin.register(NoCostQuotaAllotment)
class NoCostQuotaAllotmentAdmin(admin.ModelAdmin):
    list_display = ['no_cost_quota', 'allocation', 'amount_tb', 'created', 'updated']
    list_filter = ['no_cost_quota__quota_type', 'created', 'updated']
    search_fields = ['no_cost_quota__user__username', 'allocation__project__title']
    readonly_fields = ['created', 'updated']
    ordering = ['no_cost_quota', 'allocation']


@admin.register(NoCostQuotaGroup)
class NoCostQuotaGroupAdmin(admin.ModelAdmin):
    list_display = ['group', 'quota_type', 'description', 'amount_tb', 'units', 'increment_gb', 'created', 'updated']
    list_filter = ['quota_type', 'created', 'updated']
    search_fields = ['group__name', 'quota_type']
    readonly_fields = ['created', 'updated']
    ordering = ['group__name', 'quota_type']


@admin.register(NoCostQuotaAllotmentFailure)
class NoCostQuotaAllotmentFailureAdmin(admin.ModelAdmin):
    """Requested allotments that couldn't be applied. Set resolved at/by to mark one dealt with."""

    list_display = ['allocation', 'no_cost_quota', 'message', 'created', 'resolved_at', 'resolved_by']
    list_filter = [('resolved_at', admin.EmptyFieldListFilter), 'created']
    search_fields = ['allocation__project__title', 'no_cost_quota__user__username', 'message']
    readonly_fields = ['allocation', 'no_cost_quota', 'requested_value', 'message', 'created']
    raw_id_fields = ['resolved_by']

    def has_add_permission(self, request):
        # failures are recorded by the signal that hit them, not entered by hand
        return False
