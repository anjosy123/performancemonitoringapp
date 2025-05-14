# staff_monitor/admin.py

from django.contrib import admin
from .models import Department, MedicalSuperintendent, Staff, PerformanceReport

@admin.register(MedicalSuperintendent)
class MedicalSuperintendentAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'contact_number')
    search_fields = ('user__username', 'department__name')

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_id', 'department', 'position', 'joining_date')
    search_fields = ('user__username', 'employee_id', 'department__name')
    list_filter = ('department', 'position')

@admin.register(PerformanceReport)
class PerformanceReportAdmin(admin.ModelAdmin):
    list_display = ('staff', 'evaluator', 'date', 'get_percentage')
    list_filter = ('date', 'staff__department')
    search_fields = ('staff__user__username', 'evaluator__username')

    def get_percentage(self, obj):
        return f"{obj.percentage:.2f}%"
    get_percentage.short_description = 'Performance Score'

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)