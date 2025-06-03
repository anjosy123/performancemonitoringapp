# staff_monitor/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from django.urls import reverse
from django.shortcuts import redirect

urlpatterns = [
    # Dashboard and main views
    path('', views.dashboard, name='dashboard'),
    path('staff/', views.staff_list, name='staff_list'),
    path('department-heads/', views.superintendent_list, name='superintendent_list'),
    path('reports/', views.report_list, name='report_list'),
    path('incident-reports/', views.incident_report_list, name='incident_report_list'),
    
    # Performance evaluation
    path('evaluate/<int:staff_id>/', views.performance_form, name='performance_form'),
    path('evaluate-department-head/<int:department_head_id>/', views.performance_form_department_head, name='performance_form_department_head'),
    path('feedback/<int:staff_id>/', views.feedback_form, name='feedback_form'),
    path('feedback-department-head/<int:department_head_id>/', views.feedback_form_department_head, name='feedback_form_department_head'),
    path('check-report-exists/<int:staff_id>/<str:date>/', views.check_report_exists, name='check_report_exists'),
    path('report/<int:report_id>/view/', views.view_report, name='view_report'),
    path('report/<int:report_id>/print/', views.print_report, name='print_report'),
    path('delete-report/<int:report_id>/', views.delete_report, name='delete_report'),
    
    # Department management
    path('department/add/', views.add_department, name='add_department'),
    path('departments/', views.department_list, name='department_list'),
    path('department/edit/<int:department_id>/', views.edit_department, name='edit_department'),
    path('department/delete/<int:department_id>/', views.delete_department, name='delete_department'),
    path('get-subdepartments/<int:department_id>/', views.get_subdepartments, name='get_subdepartments'),
    
    # Staff management
    path('add-staff/', views.add_staff, name='add_staff'),
    path('edit-staff/<int:staff_id>/', views.edit_staff, name='edit_staff'),
    path('delete-staff/<int:staff_id>/', views.delete_staff, name='delete_staff'),
    path('bulk-upload-staff/', views.bulk_upload_staff, name='bulk_upload_staff'),
    
    # Department head management
    path('add-department-head/', views.add_superintendent, name='add_superintendent'),
    path('edit-department-head/<int:superintendent_id>/', views.edit_superintendent, name='edit_superintendent'),
    path('delete-department-head/<int:superintendent_id>/', views.delete_superintendent, name='delete_superintendent'),
    
    # HR Privileges management
    path('hr-privileges/list/', views.hr_privileges_list, name='hr_privileges_list'),
    path('hr-privileges/view/', views.hr_privileges_view, name='hr_privileges_view'),
    path('hr-privileges/manage/<int:head_id>/', views.manage_hr_privileges, name='manage_hr_privileges'),
    path('hr-privileges/toggle/<int:head_id>/', views.toggle_hr_status, name='toggle_hr_status'),
    path('hr-privileges/', lambda request: redirect('hr_privileges_view'), name='hr_privileges_redirect'),
    
    # Staff assignment to subdepartment heads
    path('manage-subdepartment-staff/<int:subdepartment_head_id>/', views.manage_subdepartment_staff, name='manage_subdepartment_staff'),
    
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='staff_monitor/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # Password reset
    path('password_reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='staff_monitor/password_reset.html',
             email_template_name='staff_monitor/password_reset_email.html',
             subject_template_name='staff_monitor/password_reset_subject.txt'
         ),
         name='password_reset'),
    path('password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='staff_monitor/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='staff_monitor/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='staff_monitor/password_reset_complete.html'
         ),
         name='password_reset_complete'),
    path('delete_incident_report/<int:report_id>/', views.delete_incident_report, name='delete_incident_report'),
    path('view_incident_report/<int:report_id>/', views.view_incident_report, name='view_incident_report'),
    path('print_incident_report/<int:report_id>/', views.print_incident_report, name='print_incident_report'),
    
    # User profile management
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='staff_monitor/password_change.html',
        success_url='/profile/'
    ), name='password_change'),
    
    # Session management
    path('heartbeat/', views.heartbeat, name='heartbeat'),
]