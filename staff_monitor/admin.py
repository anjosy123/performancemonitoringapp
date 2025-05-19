# staff_monitor/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Department, DepartmentHead, Staff, PerformanceReport, SubDepartment

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)

@admin.register(SubDepartment)
class SubDepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'created_at')
    list_filter = ('department',)
    search_fields = ('name', 'department__name')
    ordering = ('department', 'name',)

@admin.register(DepartmentHead)
class DepartmentHeadAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'contact_number')
    search_fields = ('user__username', 'department__name')
    list_filter = ('department',)

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_id', 'department', 'position', 'joining_date')
    search_fields = ('user__username', 'employee_id', 'department__name')
    list_filter = ('department', 'position')

@admin.register(PerformanceReport)
class PerformanceReportAdmin(admin.ModelAdmin):
    list_display = ('staff', 'evaluator', 'date', 'total_score', 'percentage')
    search_fields = ('staff__user__username', 'evaluator__username')
    list_filter = ('date', 'staff__department')
    readonly_fields = ('total_score', 'percentage')