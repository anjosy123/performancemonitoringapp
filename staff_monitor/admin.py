# staff_monitor/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Department, DepartmentHead, Staff, PerformanceReport, SubDepartment, HRPrivileges, IncidentReport

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
    list_display = ('user', 'department', 'contact_number', 'is_hr_head')
    search_fields = ('user__username', 'department__name')
    list_filter = ('department', 'is_hr_head')
    actions = ['make_hr_head', 'remove_hr_head', 'setup_hr_privileges']

    def make_hr_head(self, request, queryset):
        queryset.update(is_hr_head=True)
        self.message_user(request, f"{queryset.count()} department head(s) marked as HR head.")
    make_hr_head.short_description = "Mark selected department heads as HR heads"
    
    def remove_hr_head(self, request, queryset):
        # Remove HR privileges first
        for head in queryset:
            try:
                HRPrivileges.objects.filter(hr_head=head).delete()
            except:
                pass
        queryset.update(is_hr_head=False)
        self.message_user(request, f"{queryset.count()} department head(s) removed from HR head role.")
    remove_hr_head.short_description = "Remove HR head status"
    
    def setup_hr_privileges(self, request, queryset):
        count = 0
        for head in queryset:
            if head.is_hr_head:
                privileges, created = HRPrivileges.objects.get_or_create(hr_head=head)
                count += 1
                if created:
                    # Enable all permissions by default
                    privileges.can_add_staff = True
                    privileges.can_edit_staff = True 
                    privileges.can_view_all_reports = True
                    privileges.save()
        self.message_user(request, f"Set up privileges for {count} HR heads.")
    setup_hr_privileges.short_description = "Setup HR privileges for selected HR heads"

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_id', 'department', 'position', 'qualification', 'joining_date')
    search_fields = ('user__username', 'employee_id', 'department__name')
    list_filter = ('department', 'position')

@admin.register(PerformanceReport)
class PerformanceReportAdmin(admin.ModelAdmin):
    list_display = ('staff', 'evaluator', 'date', 'total_score', 'percentage')
    search_fields = ('staff__user__username', 'evaluator__username')
    list_filter = ('date', 'staff__department')
    readonly_fields = ('total_score', 'percentage')

@admin.register(HRPrivileges)
class HRPrivilegesAdmin(admin.ModelAdmin):
    list_display = ('hr_head', 'can_add_staff', 'can_edit_staff', 'can_delete_staff', 'can_view_all_reports')
    list_filter = ('can_add_staff', 'can_edit_staff', 'can_delete_staff', 'can_manage_departments')

@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = ('report_number', 'staff', 'incident_date', 'incident_location', 'status')
    list_filter = ('incident_date', 'status', 'staff__department')
    search_fields = ('report_number', 'staff__user__username', 'staff__user__first_name', 'staff__user__last_name', 'incident_location')
    readonly_fields = ('created_at', 'updated_at')