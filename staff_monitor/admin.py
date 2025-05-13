# staff_monitor/admin.py

from django.contrib import admin
from .models import Department, MedicalSuperintendent, Staff, PerformanceReport

@admin.register(MedicalSuperintendent)
class MedicalSuperintendentAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'contact_number')
    search_fields = ('user__username', 'department')

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_id', 'department', 'position', 'joining_date')
    search_fields = ('user__username', 'employee_id', 'department')
    list_filter = ('department', 'position')

@admin.register(PerformanceReport)
class PerformanceReportAdmin(admin.ModelAdmin):
    list_display = ('staff', 'evaluator', 'date', 'overall_performance')
    list_filter = ('date', 'overall_performance')
    search_fields = ('staff__user__username', 'evaluator__username')

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)