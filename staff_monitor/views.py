# staff_monitor/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import Staff, PerformanceReport, DepartmentHead, Department, SubDepartment, HRPrivileges, IncidentReport
from .forms import PerformanceReportForm, DepartmentHeadForm, StaffForm, DepartmentForm, SubDepartmentFormSet, IncidentReportForm, StaffBulkUploadForm
from django import forms
import random
import string
from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.http import JsonResponse, HttpResponse
from datetime import date, datetime
from django.db.models import ProtectedError
from django.contrib.auth.hashers import make_password
from django.contrib.auth import update_session_auth_hash
import pandas as pd
import uuid
from django.db import models
from django.contrib.auth import authenticate, login as auth_login
from django.views.decorators.csrf import csrf_protect
import logging
import os
from django.db import connection
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.core.files.base import ContentFile
import sys
from io import BytesIO
from PIL import Image
from django.db import models
from django.db.models import Q

# Create logger
logger = logging.getLogger(__name__)

# Helper functions
def is_admin(user):
    return user.is_staff

def is_hr_head(user):
    try:
        department_head = DepartmentHead.objects.get(user=user)
        # Check if user is from HR department or has HR privileges
        return (department_head.department.name.lower() == 'hr' or 
                department_head.is_hr_head or 
                (department_head.subdepartment and department_head.subdepartment.name.lower() == 'hr'))
    except DepartmentHead.DoesNotExist:
        return False

# Helper function to check if user is admin or HR head with appropriate privilege
def has_privilege(user, privilege_name=None):
    if user.is_staff:  # Django admin user
        return True
    try:
        dept_head = DepartmentHead.objects.get(user=user)
        
        # Special case: department heads from HR department or subdepartment always have HR privileges
        if dept_head.department.name.lower() == "hr" or (dept_head.subdepartment and dept_head.subdepartment.name.lower() == "hr"):
            return True
            
        if dept_head.is_hr_head:
            # If no specific privilege is checked, return True for any HR head
            if privilege_name is None:
                return True
                
            # Check for specific privilege
            try:
                # Get or create privileges
                privileges, created = HRPrivileges.objects.get_or_create(hr_head=dept_head)
                if created:
                    # Set default privileges
                    privileges.can_add_staff = True
                    privileges.can_edit_staff = True
                    privileges.can_view_all_reports = True
                    privileges.save()
                
                return getattr(privileges, privilege_name, False)
            except Exception as e:
                print(f"Error checking privilege {privilege_name}: {str(e)}")
                return False
    except DepartmentHead.DoesNotExist:
        # Not a department head
        return False
    
    # Default: deny privilege
    return False

# Check if user can perform an action based on privileges
def can_perform_action(user, privilege_name):
    # Django admin always has all privileges
    if user.is_staff:
        return True
        
    try:
        # Check if user is an HR head with the specific privilege
        department_head = DepartmentHead.objects.get(user=user)
        
        # Special case: department heads from HR department or subdepartment always have HR privileges
        if department_head.department.name.lower() == "hr" or (department_head.subdepartment and department_head.subdepartment.name.lower() == "hr"):
            # Always return True for HR department heads
            return True
        
        # For other department heads, check if they're marked as HR head and have the privilege
        if department_head.is_hr_head:
            try:
                # Try to get privileges - create them if they don't exist
                privileges, created = HRPrivileges.objects.get_or_create(hr_head=department_head)
                if created:
                    # Set default privileges
                    privileges.can_add_staff = True
                    privileges.can_edit_staff = True
                    privileges.can_view_all_reports = True
                    privileges.save()
                
                # Check if the specific privilege is granted
                has_privilege = getattr(privileges, privilege_name, False)
                return has_privilege
            except Exception as e:
                # Log the error but don't crash
                print(f"Error checking privilege {privilege_name} for {department_head.user.get_full_name()}: {str(e)}")
                return False
                
        # Main department heads (not subdepartment heads) can manage their staff
        if department_head.subdepartment is None:
            if privilege_name in ['can_add_staff', 'can_edit_staff']:
                return True
        
        # Even subdepartment heads can view their assigned staff 
        if privilege_name == 'can_view_assigned_staff':
            return True
            
    except (DepartmentHead.DoesNotExist, AttributeError) as e:
        pass
        
    return False

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_delete_reports') or u.is_staff)
def delete_report(request, report_id):
    try:
        report = get_object_or_404(PerformanceReport, id=report_id)
        
        # Create appropriate success message based on whether it's a staff or department head report
        if report.staff:
            report_info = f"Performance report for {report.staff.user.get_full_name()} on {report.date}"
        elif report.department_head:
            report_info = f"Performance report for {report.department_head.user.get_full_name()} on {report.date}"
        else:
            report_info = f"Performance report on {report.date}"
            
        report.delete()
        messages.success(request, f'{report_info} deleted successfully.')
    except PerformanceReport.DoesNotExist:
        messages.error(request, 'Report not found.')
    return redirect('report_list')

@login_required
def dashboard(request):
    # Get user's role and permissions
    is_admin = request.user.is_staff
    user_is_hr_head = is_hr_head(request.user)
    
    # For department heads
    if not is_admin and not user_is_hr_head:
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            is_main_department_head = department_head.subdepartment is None
            
            # Get assigned staff based on department head type
            if is_main_department_head:
                # For main department heads - get only directly assigned staff
                assigned_staff = Staff.objects.filter(
                    managed_by=department_head  # Only directly assigned staff
                )
                
                # Get subdepartment heads
                subdepartment_heads = DepartmentHead.objects.filter(
                    department=department_head.department, 
                    subdepartment__isnull=False
                )
                
                # Get all staff in department for reference (but not for management)
                department_staff = Staff.objects.filter(
                    department=department_head.department
                ).exclude(managed_by=department_head)
            else:
                # For subdepartment heads - get only directly assigned staff
                assigned_staff = Staff.objects.filter(
                    managed_by=department_head  # Only directly assigned staff
                )
                
                # Get all staff in subdepartment for reference (but not for management)
                department_staff = Staff.objects.filter(
                    department=department_head.department,
                    subdepartment=department_head.subdepartment
                ).exclude(managed_by=department_head)
                
                subdepartment_heads = []  # Subdepartment heads don't have subdepartment heads
            
            # Debug information
            print(f"Department Head: {department_head.user.get_full_name()}")
            print(f"Is Main Department Head: {is_main_department_head}")
            print(f"Department: {department_head.department}")
            print(f"Subdepartment: {department_head.subdepartment}")
            print(f"Directly Assigned Staff Count: {assigned_staff.count()}")
            print(f"Department/Subdepartment Staff Count: {department_staff.count()}")
            
            context = {
                'is_main_department_head': is_main_department_head,
                    'department_head': department_head,
                'assigned_staff': assigned_staff,
                'department_staff': department_staff,  # Staff in department/subdepartment but not assigned
                'subdepartment_heads': subdepartment_heads,
                'show_welcome': True,  # Show welcome message on login
                'has_assigned_staff': assigned_staff.exists(),  # Flag for directly assigned staff
                'has_department_staff': department_staff.exists()  # Flag for other staff in department
            }
            return render(request, 'staff_monitor/dashboard.html', context)
        except DepartmentHead.DoesNotExist:
            messages.warning(request, 'You are not registered as a department head. Please contact the administrator.')
            return redirect('profile')
    
    # For admin users
    if is_admin:
        departments = Department.objects.all()
        superintendents = DepartmentHead.objects.filter(is_hr_head=False)
        staff_list = Staff.objects.all().select_related('user', 'department', 'subdepartment')
        context = {
            'is_admin': True,
            'departments': departments,
            'superintendents': superintendents,
            'staff_list': staff_list,
        }
        return render(request, 'staff_monitor/dashboard.html', context)
    
    # For HR heads
    if user_is_hr_head:
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            privileges = department_head.privileges
            staff_list = Staff.objects.all().select_related('user', 'department', 'subdepartment')
            context = {
                'is_hr_head': True,
                'department_head': department_head,
                'privileges': privileges,
                'staff_list': staff_list,
            }
            return render(request, 'staff_monitor/dashboard.html', context)
        except DepartmentHead.DoesNotExist:
            messages.error(request, 'HR head profile not found. Please contact the administrator.')
            return redirect('profile')
    
    # Default case - no permissions
    return render(request, 'staff_monitor/dashboard.html', {'is_admin': False})

@login_required
def performance_form(request, staff_id):
    staff = get_object_or_404(Staff, id=staff_id)
    
    # Check if user has permission to evaluate this staff member
    if not request.user.is_staff:  # If not admin
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            
            # HR heads can evaluate any staff
            if department_head.is_hr_head or department_head.department.name.lower() == "hr":
                # Continue with evaluation
                pass
            # Regular department heads can only evaluate staff in their department
            elif staff.department != department_head.department:
                messages.error(request, 'You do not have permission to evaluate staff from other departments.')
                return redirect('dashboard')
        except DepartmentHead.DoesNotExist:
            messages.error(request, 'You do not have permission to evaluate staff.')
            return redirect('dashboard')

    if request.method == 'POST':
        try:
            # Check if report exists for the date
            evaluation_date = request.POST.get('date')
            if PerformanceReport.objects.filter(staff=staff, date=evaluation_date).exists():
                messages.error(request, 'A performance report already exists for this date.')
                return redirect('performance_form', staff_id=staff_id)

            # Function to safely convert string to integer
            def get_rating(key):
                try:
                    return int(request.POST.get(key, 0))
                except (ValueError, TypeError):
                    return 0

            # Create new performance report
            report = PerformanceReport(
                staff=staff,
                evaluator=request.user,
                date=evaluation_date,
                
                # Section A: Job Knowledge/Professionalism
                job_responsibility=get_rating('a1'),
                communication_skills=get_rating('a2'),
                patient_requirements=get_rating('a3'),
                negotiation_skills=get_rating('a4'),
                management_relationship=get_rating('a5'),
                policy_adherence=get_rating('a6'),
                ethical_behavior=get_rating('a7'),
                honesty_transparency=get_rating('a8'),

                # Section B: Productivity
                workload_management=get_rating('b1'),
                additional_responsibilities=get_rating('b2'),
                work_procedure=get_rating('b3'),

                # Section C: Quality of Work
                accuracy_reliability=get_rating('c1'),
                clear_communication=get_rating('c2'),
                attendance_punctuality=get_rating('c3'),
                responsibility_accountability=get_rating('c4'),

                # Section D: Interpersonal & Working Relationships
                interaction_effectiveness=get_rating('d1'),
                interpersonal_skills=get_rating('d2'),
                team_cooperation=get_rating('d3'),
                sensitivity=get_rating('d4'),
                cross_functional_collaboration=get_rating('d5'),

                # Section E: Leadership
                proactive_behavior=get_rating('e1'),
                work_ideas=get_rating('e2'),
                resource_competence=get_rating('e3'),
                mentoring_skills=get_rating('e4'),
                delegation_skills=get_rating('e5'),
                decision_making=get_rating('e6'),

                # Section F: Planning & Organizing
                work_prioritization=get_rating('f1'),
                timely_completion=get_rating('f2'),
                policy_compliance=get_rating('f3'),
                behavior_consistency=get_rating('f4'),
                pressure_handling=get_rating('f5'),

                # Section G: Adaptability
                change_adaptability=get_rating('g1'),
                learning_attitude=get_rating('g2'),
                emotional_intelligence=get_rating('g3'),

                # Section H: Result Orientation
                commitment_drive=get_rating('h1'),
                timely_decisions=get_rating('h2'),
                obstacle_handling=get_rating('h3'),

                # Section I: Clarity of Vision
                hospital_vision=get_rating('i1'),
                department_vision=get_rating('i2'),

                # Section J: Problem Solving
                problem_identification=get_rating('j1'),
                solution_approach=get_rating('j2'),
                pressure_case_handling=get_rating('j3'),

                # Additional fields
                special_remarks=request.POST.get('remarks', '')
            )
            report.save()
            messages.success(request, 'Performance evaluation submitted successfully.')
            return redirect('dashboard')

        except Exception as e:
            messages.error(request, f'Error submitting evaluation: {str(e)}')
            return redirect('performance_form', staff_id=staff_id)

    return render(request, 'staff_monitor/performance_form.html', {
        'staff': staff,
        'today': date.today(),
    })

@login_required
def performance_form_department_head(request, department_head_id):
    department_head = get_object_or_404(DepartmentHead, id=department_head_id)
    
    # Check if user has permission to evaluate this department head
    if not request.user.is_staff:  # If not admin
        try:
            main_department_head = DepartmentHead.objects.get(user=request.user)
            
            # HR heads can evaluate any department head
            if main_department_head.is_hr_head or main_department_head.department.name.lower() == "hr" or (main_department_head.subdepartment and main_department_head.subdepartment.name.lower() == "hr"):
                # Continue with feedback
                pass
            # Regular department heads can only evaluate subdepartment heads in their department
            elif department_head.department != main_department_head.department or main_department_head.subdepartment is not None:
                messages.error(request, 'You do not have permission to evaluate department heads from other departments.')
                return redirect('dashboard')
        except DepartmentHead.DoesNotExist:
            messages.error(request, 'You do not have permission to evaluate department heads.')
            return redirect('dashboard')

    # Initialize form with user data
    initial_data = {'prepared_by': request.user.get_full_name()}
    
    if request.method == 'POST':
        form = IncidentReportForm(request.POST, request.FILES, initial={'user': request.user})
        
        if form.is_valid():
            try:
                # Get incident types and related parties (not in the form)
                incident_types = request.POST.getlist('incident_type')
                other_incident_type = request.POST.get('other_incident_type', '')
                incident_description = request.POST.get('incident_description', '')
                related_parties = request.POST.getlist('related_party')
                
                # Process individuals involved
                individual_names = request.POST.getlist('individual_name[]')
                individual_departments = request.POST.getlist('individual_department[]')
                individual_positions = request.POST.getlist('individual_position[]')
                individual_roles = request.POST.getlist('individual_role[]')
                
                # Create a list of individual dictionaries
                individuals = []
                for i in range(len(individual_names)):
                    if individual_names[i]:  # Only add if name is provided
                        individuals.append({
                            'name': individual_names[i],
                            'department': individual_departments[i] if i < len(individual_departments) else '',
                            'position': individual_positions[i] if i < len(individual_positions) else '',
                            'role': individual_roles[i] if i < len(individual_roles) else ''
                        })
                
                # Create incident report from form data but don't save yet
                incident_report = form.save(commit=False)
                incident_report.department_head = department_head
                incident_report.reporter = request.user
                incident_report.incident_description = incident_description
                
                # Set reporter position based on user role
                if request.user.is_staff:
                    reporter_position = "HR Director"
                else:
                    try:
                        main_department_head = DepartmentHead.objects.get(user=request.user)
                        if main_department_head.is_hr_head:
                            reporter_position = f"HR Head - {main_department_head.department.name}"
                        else:
                            reporter_position = f"Department Head - {main_department_head.department.name}"
                    except DepartmentHead.DoesNotExist:
                        reporter_position = "Unknown"
                
                incident_report.reporter_position = reporter_position
                
                # Generate a report number if not provided
                if not incident_report.report_number:
                    # Format: IR-YYYYMMDD-DHID-Count
                    date_str = incident_report.incident_date.strftime('%Y%m%d')
                    
                    # Get the count of reports for this department head on this date
                    existing_count = IncidentReport.objects.filter(
                        department_head=department_head,
                        incident_date=incident_report.incident_date
                    ).count()
                    
                    # Create the report number
                    incident_report.report_number = f"IR-{date_str}-DH{department_head.id}-{existing_count + 1:03d}"
                
                # Process the uploaded photo and rename it based on the report number
                if 'incident_photo' in request.FILES:
                    photo = request.FILES['incident_photo']
                    processed_photo = handle_incident_photo_upload(photo, incident_report.report_number)
                    if processed_photo:
                        incident_report.incident_photo = processed_photo
                
                # Set status
                incident_report.status = 'reported'
                
                # Save the report to get an ID
                incident_report.save()
                
                # Set JSON fields using helper methods
                incident_report.set_incident_types(incident_types)
                incident_report.set_related_parties(related_parties)
                incident_report.set_individuals_involved(individuals)
                
                # Save again with the JSON fields
                incident_report.save()
                
                messages.success(request, 'Incident report submitted successfully.')
                return redirect('dashboard')
            except Exception as e:
                messages.error(request, f'Error submitting incident report: {str(e)}')
        else:
            # Form validation failed
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        # GET request, initialize empty form
        form = IncidentReportForm(initial={'user': request.user})

    # Prepare context for template
    context = {
        'department_head': department_head,
        'today': date.today(),
        'form': form,
        'is_department_head_incident': True
    }
    
    # Add main department head to context if applicable
    if not request.user.is_staff:
        try:
            main_department_head = DepartmentHead.objects.get(user=request.user)
            context['main_department_head'] = main_department_head
        except DepartmentHead.DoesNotExist:
            pass

    return render(request, 'staff_monitor/feedback_form.html', context)

@login_required
@user_passes_test(is_admin)
def manage_hr_privileges(request, head_id):
    department_head = get_object_or_404(DepartmentHead, id=head_id)
    
    # Ensure the department head is marked as HR head
    if not department_head.is_hr_head:
        department_head.is_hr_head = True
        department_head.save()
    
    # Get or create privileges
    privileges, created = HRPrivileges.objects.get_or_create(hr_head=department_head)
    
    if request.method == 'POST':
        # Update privileges based on form submission
        privileges.can_add_staff = 'can_add_staff' in request.POST
        privileges.can_edit_staff = 'can_edit_staff' in request.POST
        privileges.can_delete_staff = 'can_delete_staff' in request.POST
        privileges.can_add_department_head = 'can_add_department_head' in request.POST
        privileges.can_edit_department_head = 'can_edit_department_head' in request.POST
        privileges.can_delete_department_head = 'can_delete_department_head' in request.POST
        privileges.can_manage_departments = 'can_manage_departments' in request.POST
        privileges.can_view_all_reports = 'can_view_all_reports' in request.POST
        privileges.can_delete_reports = 'can_delete_reports' in request.POST
        privileges.save()
        
        messages.success(request, f'Privileges updated for {department_head.user.get_full_name()}')
        return redirect('hr_privileges_list')
    
    return render(request, 'staff_monitor/manage_hr_privileges.html', {
        'department_head': department_head,
        'privileges': privileges
    })

@login_required
@user_passes_test(is_admin)
def hr_privileges_list(request):
    # Get department heads marked as HR
    hr_heads = DepartmentHead.objects.filter(is_hr_head=True)
    
    # Also include department heads whose department name is "HR"
    hr_department_heads = DepartmentHead.objects.filter(department__name__iexact="HR", is_hr_head=False)
    
    # Also include department heads whose subdepartment name is "HR"
    hr_subdepartment_heads = DepartmentHead.objects.filter(subdepartment__name__iexact="HR", is_hr_head=False)
    
    # Mark department heads from HR department or subdepartment as HR heads if they're not already
    for head in list(hr_department_heads) + list(hr_subdepartment_heads):
        head.is_hr_head = True
        head.save()
        hr_heads = hr_heads | DepartmentHead.objects.filter(id=head.id)
    
    # Debug - add message with count
    messages.info(request, f'Found {hr_heads.count()} HR heads')
    
    # For each HR head, check if they have privileges setup
    for head in hr_heads:
        try:
            head.has_privileges = hasattr(head, 'privileges')
            if not head.has_privileges:
                # Create privileges automatically if it doesn't exist
                privileges = HRPrivileges.objects.create(hr_head=head)
                privileges.can_add_staff = True
                privileges.can_edit_staff = True
                privileges.can_view_all_reports = True
                privileges.save()
                head.has_privileges = True
                messages.success(request, f'HR privileges automatically set up for {head.user.get_full_name()}')
        except Exception as e:
            head.has_privileges = False
            messages.error(request, f'Error checking privileges for {head.user.get_full_name()}: {str(e)}')
    
    # Get all other department heads who are not HR heads
    all_other_heads = DepartmentHead.objects.filter(is_hr_head=False).exclude(
        models.Q(department__name__iexact="HR") | models.Q(subdepartment__name__iexact="HR")
    )
    
    return render(request, 'staff_monitor/hr_privileges_list.html', {
        'hr_heads': hr_heads,
        'all_other_heads': all_other_heads
    })

@login_required
@user_passes_test(is_admin)
def toggle_hr_status(request, head_id):
    department_head = get_object_or_404(DepartmentHead, id=head_id)
    
    # Check if this is an HR department or subdepartment member
    is_hr_department = department_head.department.name.lower() == "hr"
    is_hr_subdepartment = department_head.subdepartment and department_head.subdepartment.name.lower() == "hr"
    
    if is_hr_department or is_hr_subdepartment:
        # HR department or subdepartment members should always have HR head status
        if not department_head.is_hr_head:
            department_head.is_hr_head = True
            department_head.save()
            if is_hr_department:
                messages.success(request, f'{department_head.user.get_full_name()} is from HR department and has been granted HR privileges automatically')
            else:
                messages.success(request, f'{department_head.user.get_full_name()} is from HR subdepartment and has been granted HR privileges automatically')
    else:
        # For non-HR department members, toggle the status
        department_head.is_hr_head = not department_head.is_hr_head
        department_head.save()
        
        if not department_head.is_hr_head:
            # If HR status is turned off, delete privileges
            try:
                privileges = HRPrivileges.objects.get(hr_head=department_head)
                privileges.delete()
                messages.success(request, f'HR privileges removed for {department_head.user.get_full_name()}')
            except HRPrivileges.DoesNotExist:
                pass
        else:
            # If HR status is turned on, create default privileges
            try:
                privileges = HRPrivileges.objects.create(hr_head=department_head)
                privileges.can_add_staff = True
                privileges.can_edit_staff = True
                privileges.can_view_all_reports = True
                privileges.save()
                messages.success(request, f'Default HR privileges set for {department_head.user.get_full_name()}')
            except Exception as e:
                messages.error(request, f'Error setting up privileges: {str(e)}')
    
    return redirect('hr_privileges_list')

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_delete_reports') or u.is_staff)
def delete_incident_report(request, report_id):
    try:
        report = get_object_or_404(IncidentReport, id=report_id)
        
        # Create appropriate success message based on whether it's a staff or department head report
        if report.staff:
            report_info = f"Incident report #{report.report_number} for {report.staff.user.get_full_name()}"
        elif report.department_head:
            report_info = f"Incident report #{report.report_number} for {report.department_head.user.get_full_name()}"
        else:
            report_info = f"Incident report #{report.report_number}"
            
        report.delete()
        messages.success(request, f'{report_info} deleted successfully.')
    except IncidentReport.DoesNotExist:
        messages.error(request, 'Report not found.')
    except Exception as e:
        messages.error(request, f'Error deleting report: {str(e)}')
    return redirect('incident_report_list')

@login_required
def view_incident_report(request, report_id):
    report = get_object_or_404(IncidentReport, id=report_id)
    
    # Check permissions
    if not request.user.is_staff:
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            
            # Prevent department heads from viewing their own reports
            if report.department_head and report.department_head.id == department_head.id:
                messages.error(request, 'You cannot view your own incident reports.')
                return redirect('incident_report_list')
            
            # HR heads can view any report (except their own, handled above)
            if department_head.is_hr_head or department_head.department.name.lower() == "hr" or (department_head.subdepartment and department_head.subdepartment.name.lower() == "hr"):
                # Continue with viewing the report
                pass
            # Regular department heads can only view reports from their department
            elif (report.staff and report.staff.department != department_head.department) or \
                 (report.department_head and report.department_head.department != department_head.department):
                messages.error(request, 'You do not have permission to view this report.')
                return redirect('incident_report_list')
            # Subdepartment heads can only view reports for staff assigned to them
            elif department_head.subdepartment is not None:
                if report.staff and report.staff not in department_head.managed_staff.all():
                    messages.error(request, 'You do not have permission to view this report.')
                    return redirect('incident_report_list')
        except DepartmentHead.DoesNotExist:
            messages.error(request, 'You do not have permission to view reports.')
            return redirect('dashboard')

    return render(request, 'staff_monitor/print_incident_report.html', {
        'report': report,
        'incident_types': report.get_incident_types(),
        'related_parties': report.get_related_parties(),
        'individuals_involved': report.get_individuals_involved(),
    })

@login_required
def print_incident_report(request, report_id):
    # Reuse the view_incident_report logic but with print parameter
    report = get_object_or_404(IncidentReport, id=report_id)
    
    # Check permissions
    if not request.user.is_staff:
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            
            # Prevent department heads from viewing their own reports
            if report.department_head and report.department_head.id == department_head.id:
                messages.error(request, 'You cannot view your own incident reports.')
                return redirect('incident_report_list')
            
            # HR heads can view any report (except their own, handled above)
            if department_head.is_hr_head or department_head.department.name.lower() == "hr" or (department_head.subdepartment and department_head.subdepartment.name.lower() == "hr"):
                # Continue with viewing the report
                pass
            # Regular department heads can only view reports from their department
            elif (report.staff and report.staff.department != department_head.department) or \
                 (report.department_head and report.department_head.department != department_head.department):
                messages.error(request, 'You do not have permission to view this report.')
                return redirect('incident_report_list')
            # Subdepartment heads can only view reports for staff assigned to them
            elif department_head.subdepartment is not None:
                if report.staff and report.staff not in department_head.managed_staff.all():
                    messages.error(request, 'You do not have permission to view this report.')
                    return redirect('incident_report_list')
        except DepartmentHead.DoesNotExist:
            messages.error(request, 'You do not have permission to view reports.')
            return redirect('dashboard')

    return render(request, 'staff_monitor/print_incident_report.html', {
        'report': report,
        'incident_types': report.get_incident_types(),
        'related_parties': report.get_related_parties(),
        'individuals_involved': report.get_individuals_involved(),
        'print_mode': True
    })

@login_required
def profile(request):
    """View function to display the user's profile page."""
    user = request.user
    context = {'user': user}
    
    # Add different context data based on user type
    if user.is_staff:
        context['is_staff'] = True
    else:
        try:
            # Check if user is a department head
            department_head = DepartmentHead.objects.get(user=user)
            context['is_department_head'] = True
            context['position'] = department_head.designation
            context['department_name'] = department_head.department.name
            context['contact_number'] = department_head.contact_number
            
            if department_head.subdepartment:
                context['subdepartment_name'] = department_head.subdepartment.name
        except DepartmentHead.DoesNotExist:
            try:
                # Check if user is a staff member
                staff = Staff.objects.get(user=user)
                context['is_staff_member'] = True
                context['employee_id'] = staff.employee_id
                context['position'] = staff.position
                context['department_name'] = staff.department.name
                context['staff'] = staff
                if staff.subdepartment:
                    context['subdepartment_name'] = staff.subdepartment.name
            except Staff.DoesNotExist:
                # User is neither admin, department head, nor staff
                pass
    
    return render(request, 'staff_monitor/profile.html', context)

@login_required
def update_profile(request):
    """View function to handle profile updates."""
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'personal':
            # Handle personal details update
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            
            # Update user basic info
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save()
            
            # Update additional info if applicable
            if not request.user.is_staff:
                try:
                    department_head = DepartmentHead.objects.get(user=request.user)
                    contact_number = request.POST.get('contact_number')
                    if contact_number:
                        department_head.contact_number = contact_number
                        department_head.save()
                except DepartmentHead.DoesNotExist:
                    pass
            
            messages.success(request, 'Profile updated successfully.')
            
        elif form_type == 'password':
            # Handle password change
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            # Validate current password
            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
                return redirect('profile')
            
            # Validate new password
            if len(new_password) < 8:
                messages.error(request, 'Password must be at least 8 characters long.')
                return redirect('profile')
            
            # Validate password confirmation
            if new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
                return redirect('profile')
            
            # Change password
            request.user.set_password(new_password)
            request.user.save()
            
            # Update session to prevent logout
            update_session_auth_hash(request, request.user)
            
            messages.success(request, 'Password changed successfully.')
    
    return redirect('profile')

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_add_staff') or u.is_staff)
def bulk_upload_staff(request):
    if request.method == 'POST':
        form = StaffBulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']
            df = pd.read_excel(excel_file)
            
            # Validate required columns - using the new column names
            required_columns = ['name', 'employee_id', 'position', 'department', 'joining_date']
            
            # Check if all required columns exist
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                messages.error(request, f"Missing required columns: {', '.join(missing_columns)}")
                return redirect('staff_list')
            
            success_count = 0
            error_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    # Get or create department
                    department_name = str(row['department']).strip()
                    department, _ = Department.objects.get_or_create(name=department_name)
                    
                    # Get subdepartment if provided
                    subdepartment = None
                    if 'subdepartment' in df.columns and pd.notna(row['subdepartment']):
                        subdepartment_name = str(row['subdepartment']).strip()
                        subdepartment, _ = SubDepartment.objects.get_or_create(
                            name=subdepartment_name,
                            department=department
                        )
                    
                    # Create user account
                    username = str(row['employee_id']).strip()
                    email = f"{username}@example.com"  # You can modify this as needed
                    password = 'changeme123'  # You can change this default as needed
                    
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=str(row['name']).strip().split()[0],
                        last_name=' '.join(str(row['name']).strip().split()[1:]) if len(str(row['name']).strip().split()) > 1 else ''
                    )
                    
                    # Create staff record
                    staff = Staff.objects.create(
                        user=user,
                        employee_id=str(row['employee_id']).strip(),
                        department=department,
                        subdepartment=subdepartment,
                        position=str(row['position']).strip(),
                        joining_date=row['joining_date'] if pd.notna(row['joining_date']) else None
                    )
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append(f"Row {index + 2}: {str(e)}")
            
            if success_count > 0:
                messages.success(request, f"Successfully added {success_count} staff members.")
            if error_count > 0:
                messages.error(request, f"Failed to add {error_count} staff members. See details below.")
                for error in errors:
                    messages.error(request, error)
            
            return redirect('staff_list')
        else:
            form = StaffBulkUploadForm()
    
    # Generate template Excel file
    if 'download_template' in request.GET:
        # Create a DataFrame with the required columns
        template_data = {
            'name': ['John Doe', 'Jane Smith'],  # Example names
            'employee_id': ['EMP001', 'EMP002'],  # Example employee IDs
            'email': ['john@example.com', 'jane@example.com'],  # Example emails
            'position': ['Nurse', 'Doctor'],  # Example positions
            'department': ['Nursing', 'Medical'],  # Example departments
            'subdepartment': ['Emergency', 'General'],  # Example subdepartments
            'qualification': ['BSc Nursing', 'MBBS'],  # Example qualifications
            'contact_info': ['1234567890', '9876543210'],  # Example contact info
            'joining_date': ['12.05.2024', '15.05.2024'],  # Example joining dates in DD.MM.YYYY format
            'appointment_date': ['12.05.2024', '15.05.2024']  # Example appointment dates in DD.MM.YYYY format
        }
        
        df = pd.DataFrame(template_data)
        
        # Create a BytesIO object to store the Excel file
        output = BytesIO()
        
        # Create Excel writer object
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Staff Template', index=False)
            
            # Get the workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets['Staff Template']
            
            # Add some formatting
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D9E1F2',
                'border': 1
            })
            
            # Format the header row
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 15)  # Set column width
            
            # Add data validation for required fields
            required_fields = ['name', 'employee_id', 'position', 'department', 'joining_date']
            for col_num, value in enumerate(df.columns.values):
                if value in required_fields:
                    worksheet.data_validation(1, col_num, 1000, col_num, {
                        'validate': 'custom',
                        'value': '=LEN(TRIM(A1))>0',
                        'error_message': f'{value} is required',
                        'error_title': 'Required Field',
                        'input_message': f'Please enter {value}',
                        'input_title': 'Required Field'
                    })
                    
                    # Add date format and validation for date columns
                    if value in ['joining_date', 'appointment_date']:
                        # Set date format to DD.MM.YYYY
                        date_format = workbook.add_format({'num_format': 'dd.mm.yyyy'})
                        worksheet.set_column(col_num, col_num, 15, date_format)
                        
                        # Add date validation
                        worksheet.data_validation(1, col_num, 1000, col_num, {
                            'validate': 'date',
                            'criteria': 'between',
                            'minimum': '01.01.2000',
                            'maximum': '31.12.2100',
                            'error_message': 'Please enter a valid date in DD.MM.YYYY format',
                            'error_title': 'Invalid Date',
                            'input_message': 'Enter date in DD.MM.YYYY format',
                            'input_title': 'Date Format'
                        })
            
            # Set up the response
            output.seek(0)
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename=staff_upload_template.xlsx'
            return response
    
    return render(request, 'staff_monitor/bulk_upload_staff.html', {'form': form})

@login_required
def heartbeat(request):
    """
    Simple view to handle heartbeat requests for keeping the session alive.
    More efficient than hitting dashboard or other complex views.
    """
    # Check if we need to clear credentials from session
    if request.headers.get('X-Clear-Credentials'):
        if 'show_credentials' in request.session:
            del request.session['show_credentials']
            request.session.modified = True
    
    if request.method == 'HEAD':
        return HttpResponse(status=200)
    return HttpResponse("OK")

@login_required
def manage_subdepartment_staff(request, subdepartment_head_id):
    # Get the subdepartment head being managed
    subdepartment_head = get_object_or_404(DepartmentHead, id=subdepartment_head_id)
    
    # Security check: ensure current user is either admin or main department head
    if not request.user.is_staff:  # If not admin
        try:
            main_department_head = DepartmentHead.objects.get(user=request.user)
            # Check if this is the main department head (no subdepartment)
            if main_department_head.subdepartment is not None or main_department_head.department != subdepartment_head.department:
                messages.error(request, 'You do not have permission to manage staff assignments.')
                return redirect('dashboard')
        except DepartmentHead.DoesNotExist:
            messages.error(request, 'You do not have permission to manage staff assignments.')
            return redirect('dashboard')
    
    # Get all staff in the same department
    all_department_staff = Staff.objects.filter(
        department=subdepartment_head.department,
        subdepartment=subdepartment_head.subdepartment
    )
    
    # Get currently assigned staff
    assigned_staff = subdepartment_head.managed_staff.all()
    
    if request.method == 'POST':
        # Get list of staff IDs from form submission
        staff_ids = request.POST.getlist('staff_assignments')
        
        # Clear existing assignments
        subdepartment_head.managed_staff.clear()
        
        # Add new assignments
        if staff_ids:
            staff_to_assign = Staff.objects.filter(id__in=staff_ids)
            for staff in staff_to_assign:
                subdepartment_head.managed_staff.add(staff)
        
        messages.success(request, f'Staff assignments updated for {subdepartment_head.user.get_full_name()}')
        return redirect('dashboard')
    
    return render(request, 'staff_monitor/manage_subdepartment_staff.html', {
        'subdepartment_head': subdepartment_head,
        'all_staff': all_department_staff,
        'assigned_staff': assigned_staff
    })

@login_required
def hr_privileges_view(request):
    """View function to display HR privileges for the current HR department head."""
    # First check if the user is authenticated before proceeding
    if not request.user.is_authenticated:
        messages.error(request, "You need to login first.")
        return redirect('login')
        
    # Check if the user is admin, which should redirect to hr_privileges_list instead
    if request.user.is_staff:
        return redirect('hr_privileges_list')
        
    try:
        # Check if the user is a department head
        department_head = DepartmentHead.objects.get(user=request.user)
        
        # Only HR heads should access this page
        if not department_head.is_hr_head and department_head.department.name.lower() != "hr" and not (department_head.subdepartment and department_head.subdepartment.name.lower() == "hr"):
            messages.error(request, "You do not have HR privileges to view this page.")
            return redirect('dashboard')
            
        # Get or create privileges
        privileges, created = HRPrivileges.objects.get_or_create(hr_head=department_head)
        if created:
            # Set default privileges for new HR heads
            privileges.can_view_all_reports = True
            privileges.save()
            
        return render(request, 'staff_monitor/hr_privileges_view.html', {
            'department_head': department_head,
            'privileges': privileges
        })
        
    except DepartmentHead.DoesNotExist:
        messages.error(request, "You do not have access to this page.")
        return redirect('dashboard')

# Add this debug view at the end of the file
def debug_view(request):
    """Debug view to check database connection and environment"""
    import os
    import json
    from django.http import HttpResponse
    from django.db import connections
    from django.contrib.auth.models import User
    
    # Check if user is authenticated
    authenticated = request.user.is_authenticated
    username = request.user.username if authenticated else 'Not authenticated'
    
    # Collect debug information
    debug_info = {
        'authenticated': authenticated,
        'username': username,
        'database_info': {
            'engine': connections['default'].settings_dict['ENGINE'],
            'name': connections['default'].settings_dict['NAME'],
            'user': connections['default'].settings_dict['USER'],
            'host': connections['default'].settings_dict['HOST'],
            'port': connections['default'].settings_dict['PORT'],
        },
        'superusers': [
            {'username': user.username, 'email': user.email, 'is_active': user.is_active} 
            for user in User.objects.filter(is_superuser=True)
        ],
        'render_environment': os.environ.get('RENDER', 'Not set'),
        'debug_mode': os.environ.get('DEBUG', 'Not set'),
    }
    
    # Database connection test
    try:
        connections['default'].ensure_connection()
        debug_info['database_connection'] = 'Connected'
    except Exception as e:
        debug_info['database_connection'] = f'Error: {str(e)}'
    
    # Return as formatted JSON
    response = HttpResponse(
        json.dumps(debug_info, indent=2), 
        content_type='application/json'
    )
    return response

@csrf_protect
def custom_login(request):
    """Custom login view with detailed error handling"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '/')
        
        logger.info(f"Login attempt for user: {username}")
        
        try:
            # Check if user exists
            user_exists = User.objects.filter(username=username).exists()
            if not user_exists:
                logger.warning(f"Login failed - user does not exist: {username}")
                messages.error(request, f"User '{username}' does not exist.")
                return render(request, 'staff_monitor/login.html', {'next': next_url})
                
            # Try to authenticate
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                # User authenticated successfully
                auth_login(request, user)
                logger.info(f"User logged in successfully: {username}")
                
                # Redirect to next page or dashboard
                return redirect(next_url if next_url and next_url != '/' else 'dashboard')
            else:
                # Authentication failed
                logger.warning(f"Login failed - invalid password for: {username}")
                messages.error(request, "Invalid password. Please try again.")
                return render(request, 'staff_monitor/login.html', {'next': next_url})
                
        except Exception as e:
            # Catch any unexpected errors
            logger.error(f"Login error for {username}: {str(e)}")
            messages.error(request, f"Login error: {str(e)}")
            return render(request, 'staff_monitor/login.html', {'next': next_url})
    
    # If GET request or user is already logged in
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    # Show login form
    next_url = request.GET.get('next', '/')
    return render(request, 'staff_monitor/login.html', {'next': next_url})

def debug_db_connection(request):
    """
    Debug view to check database connection.
    This should only be accessible temporarily for troubleshooting.
    """
    import json
    from django.http import JsonResponse
    from django.db import connection
    from django.contrib.auth.models import User
    import os
    
    # Only allow this in debug mode
    if not os.environ.get('DEBUG', 'False') == 'True' and not request.user.is_superuser:
        return JsonResponse({"error": "Debug views are not available in production"}, status=403)
    
    try:
        # Check if we can execute a simple query
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_connection = "Working"
            
        # Check if auth tables exist
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='auth_user'")
            row = cursor.fetchone()
            auth_user_exists = row[0] > 0
            
        # Get database settings (sanitized)
        db_settings = connection.settings_dict.copy()
        if 'PASSWORD' in db_settings:
            db_settings['PASSWORD'] = '***HIDDEN***'
        
        # Try to get user count
        user_count = User.objects.count()
        
        return JsonResponse({
            "database_connection": db_connection,
            "auth_user_table_exists": auth_user_exists,
            "user_count": user_count,
            "database_engine": connection.vendor,
            "database_settings": db_settings,
            "database_url_var": "Set" if os.environ.get('DATABASE_URL') else "Not set",
            "render_var": "Set" if os.environ.get('RENDER') else "Not set",
            "debug_var": os.environ.get('DEBUG', 'Not set')
        })
    except Exception as e:
        return JsonResponse({
            "error": str(e),
            "database_url_var": "Set" if os.environ.get('DATABASE_URL') else "Not set",
            "render_var": "Set" if os.environ.get('RENDER') else "Not set",
            "debug_var": os.environ.get('DEBUG', 'Not set'),
            "database_settings": connection.settings_dict.get('ENGINE', 'Unknown')
        }, status=500)

@login_required
def report_list(request):
    try:
        if request.user.is_staff:
            # Admin sees all reports
            reports = PerformanceReport.objects.all().order_by('-date')
        else:
            try:
                # Check if the user is a department head
                department_head = DepartmentHead.objects.get(user=request.user)
                
                # Check if HR head with all-reports privilege
                if department_head.is_hr_head and hasattr(department_head, 'privileges') and department_head.privileges.can_view_all_reports:
                    reports = PerformanceReport.objects.exclude(department_head=department_head).order_by('-date')
                elif department_head.department.name.lower() == "hr" or (department_head.subdepartment and department_head.subdepartment.name.lower() == "hr"):
                    reports = PerformanceReport.objects.exclude(department_head=department_head).order_by('-date')
                else:
                    if department_head.subdepartment is None:
                        reports = PerformanceReport.objects.filter(
                            models.Q(staff__department=department_head.department) | 
                            models.Q(department_head__department=department_head.department)
                        ).exclude(department_head=department_head).order_by('-date')
                    else:
                        managed_staff_ids = department_head.managed_staff.values_list('id', flat=True)
                        reports = PerformanceReport.objects.filter(
                            models.Q(staff_id__in=managed_staff_ids)
                        ).exclude(department_head=department_head).order_by('-date')
            except DepartmentHead.DoesNotExist:
                reports = PerformanceReport.objects.none()
        
        return render(request, 'staff_monitor/report_list.html', {
            'reports': reports,
            'rating_choices': PerformanceReport.RATING_CHOICES
        })
    except Exception as e:
        messages.error(request, f"Error loading reports: {str(e)}")
        return redirect('dashboard')

@login_required
def incident_report_list(request):
    try:
        # Check permissions (same as performance reports)
        if request.user.is_staff:
            # Admin sees all reports
            is_authorized = True
            # Get all incident reports
            reports = IncidentReport.objects.all().order_by('-incident_date', '-incident_time')
        else:
            try:
                # Check if the user is a department head
                department_head = DepartmentHead.objects.get(user=request.user)
                
                # Check if HR head with all-reports privilege
                if department_head.is_hr_head and hasattr(department_head, 'privileges') and department_head.privileges.can_view_all_reports:
                    is_authorized = True
                    # HR head sees all reports except their own
                    reports = IncidentReport.objects.exclude(
                        department_head=department_head
                    ).order_by('-incident_date', '-incident_time')
                elif department_head.department.name.lower() == "hr" or (department_head.subdepartment and department_head.subdepartment.name.lower() == "hr"):
                    is_authorized = True
                    # HR department or subdepartment sees all reports except their own
                    reports = IncidentReport.objects.exclude(
                        department_head=department_head
                    ).order_by('-incident_date', '-incident_time')
                else:
                    # Regular department head is authorized to see their department's reports
                    is_authorized = True
                    
                    if department_head.subdepartment is None:
                        # Main department head sees all reports from their department except their own
                        reports = IncidentReport.objects.filter(
                            models.Q(staff__department=department_head.department) |
                            models.Q(department_head__department=department_head.department)
                        ).exclude(
                            department_head=department_head
                        ).order_by('-incident_date', '-incident_time')
                    else:
                        # Subdepartment head sees only reports for staff assigned to them, not their own
                        managed_staff_ids = department_head.managed_staff.values_list('id', flat=True)
                        reports = IncidentReport.objects.filter(
                            models.Q(staff_id__in=managed_staff_ids)
                        ).exclude(
                            department_head=department_head
                        ).order_by('-incident_date', '-incident_time')
                        
                        # Add debug message to check if reports are being found
                        print(f"Found {reports.count()} incident reports for subdepartment head {department_head.user.get_full_name()}")
                        print(f"Managed staff IDs for incidents: {list(managed_staff_ids)}")
            except DepartmentHead.DoesNotExist:
                is_authorized = False
                reports = IncidentReport.objects.none()
        
        if not is_authorized:
            messages.error(request, "You do not have permission to view incident reports.")
            return redirect('dashboard')
        
        # Get departments for filter
        departments = Department.objects.all().order_by('name')
            
        # Pass the reports to the template
        return render(request, 'staff_monitor/incident_report_list.html', {
            'reports': reports,
            'departments': departments,
            'status_choices': IncidentReport.STATUS_CHOICES
        })
        
    except Exception as e:
        messages.error(request, f"Error loading incident reports: {str(e)}")
        return redirect('dashboard')

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_add_department_head') or u.is_staff)
def add_superintendent(request):
    if request.method == 'POST':
        form = DepartmentHeadForm(request.POST)
        if form.is_valid():
            department_head = form.save()
            
            # Log information about the newly created department head
            print(f"Added department head: {department_head.user.get_full_name()} - Dept: {department_head.department.name}")
            if department_head.subdepartment:
                print(f"Primary Subdepartment: {department_head.subdepartment.name}")
            
            # Log managed subdepartments
            managed_subdepts = department_head.managed_subdepartments.all()
            if managed_subdepts.exists():
                subdept_names = [sd.name for sd in managed_subdepts]
                print(f"Managing subdepartments: {', '.join(subdept_names)}")
            
            # Check if email was sent
            if hasattr(department_head, 'email_sent'):
                if department_head.email_sent:
                    messages.success(request, 'Department Head added successfully. Login credentials have been sent to their email.')
                else:
                    # Email failed to send - use SweetAlert to display credentials
                    # Store the credentials in session to be accessed by JavaScript
                    request.session['show_credentials'] = {
                        'name': f"{department_head.user.first_name} {department_head.user.last_name}",
                        'username': department_head.user.email,
                        'password': department_head.user_password,
                        'department': department_head.department.name
                    }
                    
                    # Basic success message
                    messages.success(request, 'Department Head added successfully.')
                    messages.warning(request, 'Email delivery failed. Login credentials will be displayed on the next screen.')
            else:
                messages.success(request, 'Department Head added successfully.')
                
            return redirect('dashboard')
    else:
        form = DepartmentHeadForm()
    return render(request, 'staff_monitor/add_department_head.html', {'form': form})

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_add_staff') or u.is_staff)
def add_staff(request):
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            try:
                staff = form.save()
                
                # Check if email was sent
                if hasattr(staff, 'email_sent'):
                    if staff.email_sent:
                        messages.success(request, 'Staff member added successfully. Login credentials have been sent to their email.')
                    else:
                        # Email failed to send - use SweetAlert to display credentials
                        # Store the credentials in session to be accessed by JavaScript
                        request.session['show_credentials'] = {
                            'name': f"{staff.user.first_name} {staff.user.last_name}",
                            'username': staff.user.email,
                            'password': staff.user_password,
                            'department': staff.department.name
                        }
                        
                        # Basic success message
                        messages.success(request, 'Staff member added successfully.')
                        messages.warning(request, 'Email delivery failed. Login credentials will be displayed on the next screen.')
                else:
                    messages.success(request, 'Staff member added successfully.')
                
                return redirect('dashboard')
            except Exception as e:
                messages.error(request, f"Error adding staff: {str(e)}")
                return redirect('add_staff')
    else:
        form = StaffForm()
    return render(request, 'staff_monitor/add_staff.html', {'form': form})

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_edit_department_head') or u.is_staff)
def manage_department_head_staff(request, department_head_id):
    current_head = get_object_or_404(DepartmentHead, id=department_head_id)
    
    # Get all department heads in the same department
    department_heads = DepartmentHead.objects.filter(department=current_head.department)
    
    # Get available and assigned staff
    available_staff = Staff.objects.filter(
        department=current_head.department
    ).exclude(
        managed_by=current_head
    )
    
    assigned_staff = Staff.objects.filter(managed_by=current_head)
    
    context = {
        'current_head': current_head,
        'department_heads': department_heads,
        'available_staff': available_staff,
        'assigned_staff': assigned_staff,
    }
    
    return render(request, 'staff_monitor/manage_department_head_staff.html', context)

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_edit_department_head') or u.is_staff)
def assign_staff_to_head(request, department_head_id, staff_id):
    if request.method == 'POST':
        department_head = get_object_or_404(DepartmentHead, id=department_head_id)
        staff = get_object_or_404(Staff, id=staff_id)
        
        # Verify staff is in the same department
        if staff.department != department_head.department:
            messages.error(request, f"Cannot assign staff from different department.")
            return redirect('manage_department_head_staff', department_head_id=department_head_id)
        
        # Add staff to department head's managed staff
        staff.managed_by.add(department_head)
        
        messages.success(request, f"Successfully assigned {staff.user.get_full_name()} to {department_head.user.get_full_name()}")
    
    return redirect('manage_department_head_staff', department_head_id=department_head_id)

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_edit_department_head') or u.is_staff)
def unassign_staff_from_head(request, department_head_id, staff_id):
    if request.method == 'POST':
        department_head = get_object_or_404(DepartmentHead, id=department_head_id)
        staff = get_object_or_404(Staff, id=staff_id)
        
        # Remove staff from department head's managed staff
        staff.managed_by.remove(department_head)
        
        messages.success(request, f"Successfully removed {staff.user.get_full_name()} from {department_head.user.get_full_name()}")
    
    return redirect('manage_department_head_staff', department_head_id=department_head_id)

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_edit_department_head') or u.is_staff)
def assign_all_staff(request, department_head_id):
    department_head = get_object_or_404(DepartmentHead, id=department_head_id)
    
    # Get all available staff in the same department
    available_staff = Staff.objects.filter(
        department=department_head.department
    ).exclude(
        managed_by=department_head
    )
    
    # Assign all available staff
    for staff in available_staff:
        staff.managed_by.add(department_head)
    
    messages.success(request, f'Successfully assigned {available_staff.count()} staff members.')
    return redirect('manage_department_head_staff', department_head_id=department_head_id)

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_edit_department_head') or u.is_staff)
def unassign_all_staff(request, department_head_id):
    department_head = get_object_or_404(DepartmentHead, id=department_head_id)
    
    # Get all assigned staff
    assigned_staff = Staff.objects.filter(managed_by=department_head)
    count = assigned_staff.count()
    
    # Unassign all staff
    for staff in assigned_staff:
        staff.managed_by.remove(department_head)
    
    messages.success(request, f'Successfully unassigned {count} staff members.')
    return redirect('manage_department_head_staff', department_head_id=department_head_id)

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_edit_department_head') or u.is_staff)
def manage_department_head_staff(request, department_head_id):
    current_head = get_object_or_404(DepartmentHead, id=department_head_id)
    
    # Get all department heads in the same department
    department_heads = DepartmentHead.objects.filter(department=current_head.department)
    
    # Get available and assigned staff
    available_staff = Staff.objects.filter(
        department=current_head.department
    ).exclude(
        managed_by=current_head
    )
    
    assigned_staff = Staff.objects.filter(managed_by=current_head)
    
    context = {
        'current_head': current_head,
        'department_heads': department_heads,
        'available_staff': available_staff,
        'assigned_staff': assigned_staff,
    }
    
    return render(request, 'staff_monitor/manage_department_head_staff.html', context)

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_edit_department_head') or u.is_staff)
def transfer_staff(request, department_head_id):
    if request.method == 'POST':
        current_head = get_object_or_404(DepartmentHead, id=department_head_id)
        new_head_id = request.POST.get('new_head_id')
        
        if not new_head_id:
            messages.error(request, 'Please select a new department head.')
            return redirect('manage_department_head_staff', department_head_id=department_head_id)
        
        new_head = get_object_or_404(DepartmentHead, id=new_head_id)
        
        # Verify both heads are in the same department
        if current_head.department != new_head.department:
            messages.error(request, 'Cannot transfer staff between different departments.')
            return redirect('manage_department_head_staff', department_head_id=department_head_id)
        
        # Get all assigned staff
        assigned_staff = Staff.objects.filter(managed_by=current_head)
        count = assigned_staff.count()
        
        # Transfer all staff to new head
        for staff in assigned_staff:
            staff.managed_by.remove(current_head)
            staff.managed_by.add(new_head)
        
        messages.success(request, f'Successfully transferred {count} staff members to {new_head.user.get_full_name()}.')
        return redirect('manage_department_head_staff', department_head_id=new_head_id)
    
    return redirect('manage_department_head_staff', department_head_id=department_head_id)

@login_required
@user_passes_test(lambda u: is_admin(u) or can_perform_action(u, 'can_edit_staff'))
def center_management(request):
    # Get all staff and department heads
    staff_list = Staff.objects.all().select_related('user', 'department')
    department_heads = DepartmentHead.objects.all().select_related('user', 'department', 'subdepartment')
    departments = Department.objects.all()
    
    context = {
        'staff_list': staff_list,
        'department_heads': department_heads,
        'departments': departments,
        'is_admin': is_admin(request.user),
        'is_hr_head': hasattr(request.user, 'departmenthead') and request.user.departmenthead.is_hr_head
    }
    
    return render(request, 'staff_monitor/center_management.html', context)

@login_required
@user_passes_test(lambda u: is_admin(u) or can_perform_action(u, 'can_edit_staff'))
def update_staff_status(request, staff_id):
    if request.method == 'POST':
        staff = get_object_or_404(Staff, id=staff_id)
        new_status = request.POST.get('status')
        
        if new_status in ['active', 'on_leave', 'left_service']:
            old_status = staff.status
            staff.status = new_status
            staff.save()
            
            # Handle user account activation/deactivation
            user = staff.user
            if new_status == 'active':
                user.is_active = True
                user.save()
                messages.success(request, f"Successfully updated {staff.user.get_full_name()}'s status to {staff.get_status_display()} and enabled their account")
            else:
                user.is_active = False
                user.save()
                messages.success(request, f"Successfully updated {staff.user.get_full_name()}'s status to {staff.get_status_display()} and disabled their account")
        else:
            messages.error(request, "Invalid status provided")
    
    return redirect('center_management')

@login_required
@user_passes_test(lambda u: is_admin(u) or can_perform_action(u, 'can_edit_department_head'))
def update_department_head_status(request, head_id):
    if request.method == 'POST':
        department_head = get_object_or_404(DepartmentHead, id=head_id)
        new_status = request.POST.get('status')
        
        if new_status in ['active', 'on_leave', 'left_service']:
            old_status = department_head.status
            department_head.status = new_status
            department_head.save()
            
            # Handle user account activation/deactivation
            user = department_head.user
            if new_status == 'active':
                user.is_active = True
                user.save()
                messages.success(request, f"Successfully updated {department_head.user.get_full_name()}'s status to {department_head.get_status_display()} and enabled their account")
            else:
                user.is_active = False
                user.save()
                messages.success(request, f"Successfully updated {department_head.user.get_full_name()}'s status to {department_head.get_status_display()} and disabled their account")
        else:
            messages.error(request, "Invalid status provided")
    
    return redirect('center_management')

def handle_incident_photo_upload(photo, report_number):
    """Handle incident photo upload and return the processed photo path"""
    if photo:
        # Create a unique filename using report number and timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"incident_{report_number}_{timestamp}{os.path.splitext(photo.name)[1]}"
        return filename
    return None

@login_required
def staff_list(request):
    # For admin users and HR users - show all staff
    if request.user.is_staff or is_hr_head(request.user):
        staff_list = Staff.objects.all().select_related('user', 'department', 'subdepartment')
        departments = Department.objects.all()
        # Group staff by department
        staff_by_department = {}
        for dept in departments:
            staff_in_dept = staff_list.filter(department=dept)
            staff_by_department[dept.id] = {
                'name': dept.name,
                'staff': staff_in_dept,
            }
        show_by_department = True
    # For regular department heads - show only their department's staff
    else:
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            staff_list = Staff.objects.filter(department=department_head.department).select_related('user', 'department', 'subdepartment')
            departments = Department.objects.filter(id=department_head.department.id)
            staff_by_department = None
            show_by_department = False
        except DepartmentHead.DoesNotExist:
            staff_list = Staff.objects.none()
            departments = Department.objects.none()
            staff_by_department = None
            show_by_department = False
    context = {
        'staff_list': staff_list,
        'departments': departments,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user),
        'show_by_department': show_by_department,
        'staff_by_department': staff_by_department,
    }
    return render(request, 'staff_monitor/staff_list.html', context)

@login_required
def superintendent_list(request):
    # For admin users and HR users - show all department heads except HR department heads
    if request.user.is_staff or is_hr_head(request.user):
        superintendents = DepartmentHead.objects.exclude(
            models.Q(department__name__iexact='hr') | 
            models.Q(subdepartment__name__iexact='hr')
        ).select_related('user', 'department', 'subdepartment')
        departments = Department.objects.exclude(name__iexact='hr')
        show_by_department = False
    # For regular department heads - show only their department's staff
    else:
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            superintendents = DepartmentHead.objects.filter(department=department_head.department).select_related('user', 'department', 'subdepartment')
            departments = Department.objects.filter(id=department_head.department.id)
            show_by_department = False
        except DepartmentHead.DoesNotExist:
            superintendents = DepartmentHead.objects.none()
            departments = Department.objects.none()
            show_by_department = False
    
    # Group department heads by department for easier viewing
    superintendents_by_department = {}
    if show_by_department:
        for dept in departments:
            dept_heads = superintendents.filter(department=dept)
            if dept_heads.exists():
                superintendents_by_department[dept.id] = {
                    'name': dept.name,
                    'department_heads': dept_heads
                }
    
    context = {
        'superintendents': superintendents,
        'departments': departments,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user),
        'show_by_department': show_by_department,
        'department_head': DepartmentHead.objects.filter(user=request.user).first(),
        'superintendents_by_department': superintendents_by_department if show_by_department else None
    }
    
    return render(request, 'staff_monitor/superintendent_list.html', context)

@login_required
def feedback_form(request, staff_id):
    staff = get_object_or_404(Staff, id=staff_id)
    
    # Check if user has permission to report incidents for this staff
    if not request.user.is_staff and not is_hr_head(request.user):
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            if staff.department != department_head.department:
                messages.error(request, "You don't have permission to report incidents for this staff member.")
                return redirect('dashboard')
        except DepartmentHead.DoesNotExist:
            messages.error(request, "You don't have permission to report incidents.")
            return redirect('dashboard')
    
    if request.method == 'POST':
        form = IncidentReportForm(request.POST, request.FILES)
        if form.is_valid():
            # Generate report number
            report_number = f"IR{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create incident report
            incident_report = form.save(commit=False)
            incident_report.staff = staff
            incident_report.reporter = request.user
            incident_report.report_number = report_number
            
            # Handle photo upload
            photo = request.FILES.get('incident_photo')
            if photo:
                processed_photo = handle_incident_photo_upload(photo, report_number)
                incident_report.incident_photo = processed_photo
            
            incident_report.save()
            messages.success(request, 'Incident report submitted successfully.')
            return redirect('incident_report_list')
    else:
        form = IncidentReportForm()
    
    context = {
        'form': form,
        'staff': staff,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user)
    }
    
    return render(request, 'staff_monitor/feedback_form.html', context)

@login_required
def feedback_form_department_head(request, department_head_id):
    department_head = get_object_or_404(DepartmentHead, id=department_head_id)
    
    # Check if user has permission to report incidents for this department head
    if not request.user.is_staff and not is_hr_head(request.user):
        try:
            user_department_head = DepartmentHead.objects.get(user=request.user)
            if department_head.department != user_department_head.department:
                messages.error(request, "You don't have permission to report incidents for this department head.")
                return redirect('dashboard')
        except DepartmentHead.DoesNotExist:
            messages.error(request, "You don't have permission to report incidents.")
            return redirect('dashboard')
    
    if request.method == 'POST':
        form = IncidentReportForm(request.POST, request.FILES)
        if form.is_valid():
            # Generate report number
            report_number = f"IR{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create incident report
            incident_report = form.save(commit=False)
            incident_report.department_head = department_head
            incident_report.reporter = request.user
            incident_report.report_number = report_number
            
            # Handle photo upload
            photo = request.FILES.get('incident_photo')
            if photo:
                processed_photo = handle_incident_photo_upload(photo, report_number)
                incident_report.incident_photo = processed_photo
            
            incident_report.save()
            messages.success(request, 'Incident report submitted successfully.')
            return redirect('incident_report_list')
    else:
        form = IncidentReportForm()
    
    context = {
        'form': form,
        'department_head': department_head,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user)
    }
    
    return render(request, 'staff_monitor/feedback_form_department_head.html', context)

@login_required
def check_report_exists(request, staff_id, date):
    try:
        staff = get_object_or_404(Staff, id=staff_id)
        report_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Check if a report exists for this staff member on the given date
        report_exists = PerformanceReport.objects.filter(
            staff=staff,
            date=report_date
        ).exists()
        
        return JsonResponse({
            'exists': report_exists,
            'message': 'Report already exists for this date' if report_exists else 'No report exists for this date'
        })
    except ValueError:
        return JsonResponse({
            'error': 'Invalid date format. Please use YYYY-MM-DD format.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)

@login_required
def view_report(request, report_id):
    report = get_object_or_404(PerformanceReport, id=report_id)
    
    # Check if user has permission to view this report
    if not request.user.is_staff and not is_hr_head(request.user):
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            if report.staff and report.staff.department != department_head.department:
                messages.error(request, "You don't have permission to view this report.")
                return redirect('dashboard')
        except DepartmentHead.DoesNotExist:
            messages.error(request, "You don't have permission to view reports.")
            return redirect('dashboard')
    
    section_field_map = {
        'A. JOB KNOWLEDGE/ PROFESSIONALISM': [
            ('Understanding of job responsibility', 'job_responsibility'),
            ('Good communications skills', 'communication_skills'),
            ('Identifies & understand patient requirements and balance with hospital interest', 'patient_requirements'),
            ('Negotiation skills & ability to address queries/ doubts', 'negotiation_skills'),
            ('Effective Relationship with management', 'management_relationship'),
            ('Respect for policies, rules & hospital values', 'policy_adherence'),
            ('Has ethical behavior & positive attitude', 'ethical_behavior'),
            ('Honesty and transparency', 'honesty_transparency'),
        ],
        'B. PRODUCTIVITY': [
            ('Manages a fair work load', 'workload_management'),
            ('Takes additional responsibilities', 'additional_responsibilities'),
            ('Develops and follows work procedure', 'work_procedure'),
        ],
        'C. QUALITY OF WORK': [
            ('Demonstrates accuracy, thoroughness and reliability', 'accuracy_reliability'),
            ('Communicates views clearly & logically both in one to one conversation & group', 'clear_communication'),
            ('Attendance & punctuality', 'attendance_punctuality'),
            ('Has good responsibility & accountability', 'responsibility_accountability'),
        ],
        'D. INTERPERSONAL & WORKING RELATIONSHIPS': [
            ('Interacts effectively with patients, co-workers & public', 'interaction_effectiveness'),
            ('Has good interpersonal skills and gets along well with people', 'interpersonal_skills'),
            ('Seeks & provides help & cooperation from team members when required', 'team_cooperation'),
            ('Exhibits appropriate sensitivity to others feelings', 'sensitivity'),
            ('Collaborates effectively with cross-functional teams', 'cross_functional_collaboration'),
        ],
        'E. LEADERSHIP, INITIATIVES & RESOURCEFULNESS': [
            ('Displays proactive behavior', 'proactive_behavior'),
            ('Is meticulous in following through work ideas', 'work_ideas'),
            ('Displays competence of working within resources', 'resource_competence'),
            ('Displays mentoring or guiding others & taking charge when needed', 'mentoring_skills'),
            ('Has work delegation skills', 'delegation_skills'),
            ('Has good decision-making skills', 'decision_making'),
        ],
        'F. PLANNING & ORGANIZING EFFECTIVENESS': [
            ('Effectively prioritizes work & establishes work plans', 'work_prioritization'),
            ('Performs tasks thoroughly on time', 'timely_completion'),
            ('Works within organizational policies & guidelines', 'policy_compliance'),
            ('Consistency in behavior', 'behavior_consistency'),
            ('Displays ability to work under pressure', 'pressure_handling'),
        ],
        'G. ADAPTABILITY': [
            ('Displays adaptability to change, modifies behavior to deal effectively with change', 'change_adaptability'),
            ('Willing to learn from mistakes, treats change as an opportunity for learning & growth', 'learning_attitude'),
            ('Displays good emotional intelligence', 'emotional_intelligence'),
        ],
        'H. RESULT ORIENTATION': [
            ('Demonstrates string commitment & drive to achieve results', 'commitment_drive'),
            ('Takes timely decisions & ensure completion of tasks', 'timely_decisions'),
            ('Can be relied on to deliver despite obstacles or complex situations', 'obstacle_handling'),
        ],
        'I. CLARITY OF VISION': [
            ('Understands the philosophy of vision & mission of the hospital', 'hospital_vision'),
            ('Displays clarity of vision with respect to departments and organization', 'department_vision'),
        ],
        'J. PROBLEM SOLVING': [
            ('Has the ability to identify problems & identifies various dimensions of problem', 'problem_identification'),
            ('Identifies alternate approaches/ solutions to problems', 'solution_approach'),
            ('Ability to handle cases even under pressure', 'pressure_case_handling'),
        ],
    }
    context = {
        'report': report,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user),
        'staff': report.staff if report.staff else None,
        'department_head': report.department_head if report.department_head else None,
        'evaluator': report.evaluator,
        'section_field_map': section_field_map,
    }
    return render(request, 'staff_monitor/print_report.html', context)

@login_required
def print_report(request, report_id):
    report = get_object_or_404(PerformanceReport, id=report_id)
    
    # Check if user has permission to view this report
    if not request.user.is_staff and not is_hr_head(request.user):
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            if report.staff and report.staff.department != department_head.department:
                messages.error(request, "You don't have permission to view this report.")
                return redirect('dashboard')
        except DepartmentHead.DoesNotExist:
            messages.error(request, "You don't have permission to view reports.")
            return redirect('dashboard')
    
    section_field_map = {
        'A. JOB KNOWLEDGE/ PROFESSIONALISM': [
            ('Understanding of job responsibility', 'job_responsibility'),
            ('Good communications skills', 'communication_skills'),
            ('Identifies & understand patient requirements and balance with hospital interest', 'patient_requirements'),
            ('Negotiation skills & ability to address queries/ doubts', 'negotiation_skills'),
            ('Effective Relationship with management', 'management_relationship'),
            ('Respect for policies, rules & hospital values', 'policy_adherence'),
            ('Has ethical behavior & positive attitude', 'ethical_behavior'),
            ('Honesty and transparency', 'honesty_transparency'),
        ],
        'B. PRODUCTIVITY': [
            ('Manages a fair work load', 'workload_management'),
            ('Takes additional responsibilities', 'additional_responsibilities'),
            ('Develops and follows work procedure', 'work_procedure'),
        ],
        'C. QUALITY OF WORK': [
            ('Demonstrates accuracy, thoroughness and reliability', 'accuracy_reliability'),
            ('Communicates views clearly & logically both in one to one conversation & group', 'clear_communication'),
            ('Attendance & punctuality', 'attendance_punctuality'),
            ('Has good responsibility & accountability', 'responsibility_accountability'),
        ],
        'D. INTERPERSONAL & WORKING RELATIONSHIPS': [
            ('Interacts effectively with patients, co-workers & public', 'interaction_effectiveness'),
            ('Has good interpersonal skills and gets along well with people', 'interpersonal_skills'),
            ('Seeks & provides help & cooperation from team members when required', 'team_cooperation'),
            ('Exhibits appropriate sensitivity to others feelings', 'sensitivity'),
            ('Collaborates effectively with cross-functional teams', 'cross_functional_collaboration'),
        ],
        'E. LEADERSHIP, INITIATIVES & RESOURCEFULNESS': [
            ('Displays proactive behavior', 'proactive_behavior'),
            ('Is meticulous in following through work ideas', 'work_ideas'),
            ('Displays competence of working within resources', 'resource_competence'),
            ('Displays mentoring or guiding others & taking charge when needed', 'mentoring_skills'),
            ('Has work delegation skills', 'delegation_skills'),
            ('Has good decision-making skills', 'decision_making'),
        ],
        'F. PLANNING & ORGANIZING EFFECTIVENESS': [
            ('Effectively prioritizes work & establishes work plans', 'work_prioritization'),
            ('Performs tasks thoroughly on time', 'timely_completion'),
            ('Works within organizational policies & guidelines', 'policy_compliance'),
            ('Consistency in behavior', 'behavior_consistency'),
            ('Displays ability to work under pressure', 'pressure_handling'),
        ],
        'G. ADAPTABILITY': [
            ('Displays adaptability to change, modifies behavior to deal effectively with change', 'change_adaptability'),
            ('Willing to learn from mistakes, treats change as an opportunity for learning & growth', 'learning_attitude'),
            ('Displays good emotional intelligence', 'emotional_intelligence'),
        ],
        'H. RESULT ORIENTATION': [
            ('Demonstrates string commitment & drive to achieve results', 'commitment_drive'),
            ('Takes timely decisions & ensure completion of tasks', 'timely_decisions'),
            ('Can be relied on to deliver despite obstacles or complex situations', 'obstacle_handling'),
        ],
        'I. CLARITY OF VISION': [
            ('Understands the philosophy of vision & mission of the hospital', 'hospital_vision'),
            ('Displays clarity of vision with respect to departments and organization', 'department_vision'),
        ],
        'J. PROBLEM SOLVING': [
            ('Has the ability to identify problems & identifies various dimensions of problem', 'problem_identification'),
            ('Identifies alternate approaches/ solutions to problems', 'solution_approach'),
            ('Ability to handle cases even under pressure', 'pressure_case_handling'),
        ],
    }
    context = {
        'report': report,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user),
        'staff': report.staff if report.staff else None,
        'department_head': report.department_head if report.department_head else None,
        'evaluator': report.evaluator,
        'section_field_map': section_field_map,
        'print_mode': True
    }
    return render(request, 'staff_monitor/print_report.html', context)

@login_required
@user_passes_test(lambda u: is_admin(u) or can_perform_action(u, 'can_manage_departments'))
def add_department(request):
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            try:
                department = form.save()
                messages.success(request, f'Department "{department.name}" added successfully.')
                return redirect('department_list')
            except Exception as e:
                messages.error(request, f'Error adding department: {str(e)}')
    else:
        form = DepartmentForm()
    
    context = {
        'form': form,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user),
        'title': 'Add Department'
    }
    
    return render(request, 'staff_monitor/department_form.html', context)

@login_required
@user_passes_test(lambda u: is_admin(u) or can_perform_action(u, 'can_manage_departments'))
def department_list(request):
    departments = Department.objects.all().prefetch_related('subdepartments')
    
    # Get counts for each department
    for department in departments:
        department.staff_count = Staff.objects.filter(department=department).count()
        department.head_count = DepartmentHead.objects.filter(department=department).count()
        department.subdepartment_count = department.subdepartments.count()
    
    context = {
        'departments': departments,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user),
        'can_manage_departments': can_perform_action(request.user, 'can_manage_departments')
    }
    
    return render(request, 'staff_monitor/department_list.html', context)

@login_required
@user_passes_test(lambda u: is_admin(u) or can_perform_action(u, 'can_manage_departments'))
def edit_department(request, department_id):
    department = get_object_or_404(Department, id=department_id)
    
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            try:
                updated_department = form.save()
                messages.success(request, f'Department "{updated_department.name}" updated successfully.')
                return redirect('department_list')
            except Exception as e:
                messages.error(request, f'Error updating department: {str(e)}')
    else:
        form = DepartmentForm(instance=department)
    
    context = {
        'form': form,
        'department': department,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user),
        'title': f'Edit Department: {department.name}'
    }
    
    return render(request, 'staff_monitor/department_form.html', context)

@login_required
@user_passes_test(lambda u: is_admin(u) or can_perform_action(u, 'can_manage_departments'))
def delete_department(request, department_id):
    department = get_object_or_404(Department, id=department_id)
    
    # Check if department has any staff or department heads
    staff_count = Staff.objects.filter(department=department).count()
    head_count = DepartmentHead.objects.filter(department=department).count()
    subdept_count = department.subdepartments.count()
    
    if request.method == 'POST':
        try:
            department_name = department.name
            department.delete()
            messages.success(request, f'Department "{department_name}" deleted successfully.')
            return redirect('department_list')
        except Exception as e:
            messages.error(request, f'Error deleting department: {str(e)}')
            return redirect('department_list')
    
    context = {
        'department': department,
        'staff_count': staff_count,
        'head_count': head_count,
        'subdept_count': subdept_count,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user),
        'title': f'Delete Department: {department.name}'
    }
    
    return render(request, 'staff_monitor/department_confirm_delete.html', context)

@login_required
def get_subdepartments(request, department_id):
    try:
        department = Department.objects.get(id=department_id)
        subdepartments = SubDepartment.objects.filter(department=department).order_by('name')
        
        data = [{'id': sub.id, 'name': sub.name} for sub in subdepartments]
        return JsonResponse({'subdepartments': data})
    except Department.DoesNotExist:
        return JsonResponse({'error': 'Department not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@user_passes_test(lambda u: is_admin(u) or can_perform_action(u, 'can_edit_staff'))
def edit_staff(request, staff_id):
    staff = get_object_or_404(Staff, id=staff_id)
    
    if request.method == 'POST':
        form = StaffForm(request.POST, instance=staff)
        if form.is_valid():
            try:
                updated_staff = form.save()
                messages.success(request, f'Staff member "{updated_staff.user.get_full_name()}" updated successfully.')
                return redirect('staff_list')
            except Exception as e:
                messages.error(request, f'Error updating staff member: {str(e)}')
    else:
        form = StaffForm(instance=staff)
    
    context = {
        'form': form,
        'staff': staff,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user),
        'title': f'Edit Staff: {staff.user.get_full_name()}'
    }
    
    return render(request, 'staff_monitor/staff_form.html', context)

@login_required
@user_passes_test(lambda u: is_admin(u) or can_perform_action(u, 'can_delete_staff'))
def delete_staff(request, staff_id):
    staff = get_object_or_404(Staff, id=staff_id)
    
    # Check if staff has any performance reports or incident reports
    performance_reports = PerformanceReport.objects.filter(staff=staff).count()
    incident_reports = IncidentReport.objects.filter(staff=staff).count()
    
    if request.method == 'POST':
        try:
            staff_name = staff.user.get_full_name()
            staff.delete()
            messages.success(request, f'Staff member "{staff_name}" deleted successfully.')
            return redirect('staff_list')
        except Exception as e:
            messages.error(request, f'Error deleting staff member: {str(e)}')
            return redirect('staff_list')
    
    context = {
        'staff': staff,
        'performance_reports': performance_reports,
        'incident_reports': incident_reports,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user),
        'title': f'Delete Staff: {staff.user.get_full_name()}'
    }
    
    return render(request, 'staff_monitor/staff_confirm_delete.html', context)

@login_required
@user_passes_test(lambda u: is_admin(u) or can_perform_action(u, 'can_edit_department_head'))
def edit_superintendent(request, superintendent_id):
    department_head = get_object_or_404(DepartmentHead, id=superintendent_id)
    
    if request.method == 'POST':
        form = DepartmentHeadForm(request.POST, instance=department_head)
        if form.is_valid():
            try:
                updated_head = form.save()
                messages.success(request, f'Department Head "{updated_head.user.get_full_name()}" updated successfully.')
                return redirect('superintendent_list')
            except Exception as e:
                messages.error(request, f'Error updating department head: {str(e)}')
    else:
        form = DepartmentHeadForm(instance=department_head)
    
    # Get all departments and subdepartments
    departments = Department.objects.all()
    subdepartments = SubDepartment.objects.filter(department=department_head.department)
    
    context = {
        'form': form,
        'department_head': department_head,
        'departments': departments,
        'subdepartments': subdepartments,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user),
        'title': f'Edit Department Head: {department_head.user.get_full_name()}'
    }
    
    return render(request, 'staff_monitor/superintendent_form.html', context)

@login_required
@user_passes_test(lambda u: is_admin(u) or can_perform_action(u, 'can_delete_department_head'))
def delete_superintendent(request, superintendent_id):
    department_head = get_object_or_404(DepartmentHead, id=superintendent_id)
    
    # Check if department head has any managed staff, performance reports, or incident reports
    managed_staff_count = department_head.managed_staff.count()
    performance_reports = PerformanceReport.objects.filter(department_head=department_head).count()
    incident_reports = IncidentReport.objects.filter(department_head=department_head).count()
    
    if request.method == 'POST':
        try:
            head_name = department_head.user.get_full_name()
            department_head.delete()
            messages.success(request, f'Department Head "{head_name}" deleted successfully.')
            return redirect('superintendent_list')
        except Exception as e:
            messages.error(request, f'Error deleting department head: {str(e)}')
            return redirect('superintendent_list')
    
    context = {
        'department_head': department_head,
        'managed_staff_count': managed_staff_count,
        'performance_reports': performance_reports,
        'incident_reports': incident_reports,
        'is_admin': request.user.is_staff,
        'is_hr_head': is_hr_head(request.user),
        'title': f'Delete Department Head: {department_head.user.get_full_name()}'
    }
    
    return render(request, 'staff_monitor/superintendent_confirm_delete.html', context)
