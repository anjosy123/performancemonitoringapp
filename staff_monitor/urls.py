# staff_monitor/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('evaluate/<int:staff_id>/', views.performance_form, name='performance_form'),
    path('reports/', views.report_list, name='report_list'),
    path('add-department-head/', views.add_superintendent, name='add_superintendent'),
    path('add-staff/', views.add_staff, name='add_staff'),
    path('delete-report/<int:report_id>/', views.delete_report, name='delete_report'),
    path('get-subdepartments/<int:department_id>/', views.get_subdepartments, name='get_subdepartments'),
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
    path('department/add/', views.add_department, name='add_department'),
    path('departments/', views.department_list, name='department_list'),
    path('department/edit/<int:department_id>/', views.edit_department, name='edit_department'),
    path('department/delete/<int:department_id>/', views.delete_department, name='delete_department'),
    path('edit-department-head/<int:superintendent_id>/', views.edit_superintendent, name='edit_superintendent'),
    path('delete-department-head/<int:superintendent_id>/', views.delete_superintendent, name='delete_superintendent'),
    path('edit-staff/<int:staff_id>/', views.edit_staff, name='edit_staff'),
    path('delete-staff/<int:staff_id>/', views.delete_staff, name='delete_staff'),
    path('performance/<int:staff_id>/', views.performance_form, name='performance_form'),
    path('report/<int:report_id>/view/', views.view_report, name='view_report'),
    path('report/<int:report_id>/print/', views.print_report, name='print_report'),
    path('department-heads/', views.superintendent_list, name='superintendent_list'),
    path('staff/', views.staff_list, name='staff_list'),
    
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='staff_monitor/login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
]