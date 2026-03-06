from django.contrib import admin

from .models import CostCenter, CostCenterAssignment, NoCostQuota, NoCostQuotaAllotment


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ['dept_id']
    search_fields = ['dept_id']
    ordering = ['dept_id']


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
    list_display = ['user', 'quota_type', 'description', 'amount', 'units', 'minimum_increment', 'created', 'updated']
    list_filter = ['quota_type', 'created', 'updated']
    search_fields = ['user__username', 'user__email', 'quota_type']
    readonly_fields = ['created', 'updated']
    ordering = ['user', 'quota_type']


@admin.register(NoCostQuotaAllotment)
class NoCostQuotaAllotmentAdmin(admin.ModelAdmin):
    list_display = ['no_cost_quota', 'allocation', 'amount', 'created', 'updated']
    list_filter = ['no_cost_quota__quota_type', 'created', 'updated']
    search_fields = ['no_cost_quota__user__username', 'allocation__project__title']
    readonly_fields = ['created', 'updated']
    ordering = ['no_cost_quota', 'allocation']
