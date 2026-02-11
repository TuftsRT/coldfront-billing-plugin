from django.contrib import admin
from .models import CostCenterAssignment, CostCenter


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ['dept_id']
    search_fields = ['dept_id']
    ordering = ['dept_id']


@admin.register(CostCenterAssignment)
class CostCenterAssignmentAdmin(admin.ModelAdmin):

    list_display = ['project', "assignments",'created', 'modified']
    list_filter = ['created', 'modified']
    search_fields = ['project__title', 'project__pi__username']
    readonly_fields = ['created', 'modified']

    fieldsets = [
        (None, {
            'fields': ['project', 'assignments']
        }),
        ('Timestamps', {
            'fields': ['created', 'modified'],
            'classes': ['collapse']
        }),
    ]

