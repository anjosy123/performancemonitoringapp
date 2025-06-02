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

# Helper function to check if user is admin or HR head with appropriate privilege
def has_privilege(user, privilege_name=None):
    if user.is_staff:  # Django admin user
        return True
    try:
        dept_head = DepartmentHead.objects.get(user=user)
        
        # Special case: department heads from HR department always have HR privileges
        if dept_head.department.name.lower() == "hr":
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
        return False
    except (DepartmentHead.DoesNotExist, AttributeError):
        return False

# Helper function to check if user is admin or HR head with specific privilege
def can_perform_action(user, privilege_name):
    # Django admin always has all privileges
    if user.is_staff:
        return True
    
    try:
        # Check if user is an HR head with the specific privilege
        department_head = DepartmentHead.objects.get(user=user)
        
        # Special case: department heads from HR department always have HR privileges
        if department_head.department.name.lower() == "hr":
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
    except (DepartmentHead.DoesNotExist, AttributeError) as e:
        pass
    
    return False

# Original is_admin function for compatibility
def is_admin(user):
    return user.is_staff

@login_required
def dashboard(request):
    if request.user.is_staff:
        # Admin sees all staff and superintendents
        staff_list = Staff.objects.all()
        superintendents = DepartmentHead.objects.all()
        departments = Department.objects.all()
        
        # Calculate staff count for each superintendent
        for superintendent in superintendents:
            # Count staff members in the superintendent's department
            superintendent.staff_count = Staff.objects.filter(department=superintendent.department).count()
        
        return render(request, 'staff_monitor/dashboard.html', {
            'staff_list': staff_list,
            'superintendents': superintendents,
            'departments': departments,
            'is_admin': True  # Flag to indicate admin role
        })
    else:
        try:
            # Check if the user is a department head
            department_head = DepartmentHead.objects.get(user=request.user)
            
            # Check if this is an HR head
            if department_head.is_hr_head:
                # Get available privileges
                try:
                    privileges = department_head.privileges
                except HRPrivileges.DoesNotExist:
                    privileges = None
                    
                # Get data based on privileges
                staff_list = Staff.objects.all()
                superintendents = DepartmentHead.objects.all()
                departments = Department.objects.all()
                
                # Calculate staff count for each superintendent
                for superintendent in superintendents:
                    superintendent.staff_count = Staff.objects.filter(department=superintendent.department).count()
                
                return render(request, 'staff_monitor/dashboard.html', {
                    'staff_list': staff_list,
                    'superintendents': superintendents,
                    'departments': departments,
                    'is_hr_head': True,
                    'department_head': department_head,
                    'privileges': privileges
                })
            
            # Determine if this is a main department head or subdepartment head
            is_main_department_head = department_head.subdepartment is None
            
            if is_main_department_head:
                # Main department head sees all staff from their department
                staff_list = Staff.objects.filter(department=department_head.department)
                
                # Get subdepartment heads under this department
                subdepartment_heads = DepartmentHead.objects.filter(
                    department=department_head.department, 
                    subdepartment__isnull=False
                )
                
                return render(request, 'staff_monitor/dashboard.html', {
                    'staff_list': staff_list,
                    'department_head': department_head,
                    'is_main_department_head': True,
                    'subdepartment_heads': subdepartment_heads
                })
            else:
                # Subdepartment head sees only staff assigned to them
                staff_list = department_head.managed_staff.all()
                
                return render(request, 'staff_monitor/dashboard.html', {
                    'staff_list': staff_list,
                    'department_head': department_head,
                    'is_main_department_head': False
                })
                
        except DepartmentHead.DoesNotExist:
            # If the user is neither admin nor department head, show empty list
            staff_list = Staff.objects.none()
            return render(request, 'staff_monitor/dashboard.html', {
                'staff_list': staff_list,
                'is_admin': False
            })

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
            if main_department_head.is_hr_head or main_department_head.department.name.lower() == "hr":
                # Continue with evaluation
                pass
            # Regular department heads can only evaluate subdepartment heads in their department
            elif department_head.department != main_department_head.department or main_department_head.subdepartment is not None:
                messages.error(request, 'You do not have permission to evaluate department heads from other departments.')
                return redirect('dashboard')
        except DepartmentHead.DoesNotExist:
            messages.error(request, 'You do not have permission to evaluate department heads.')
            return redirect('dashboard')

    if request.method == 'POST':
        try:
            # Check if report exists for the date
            evaluation_date = request.POST.get('date')
            if PerformanceReport.objects.filter(department_head=department_head, date=evaluation_date).exists():
                messages.error(request, 'A performance report already exists for this date.')
                return redirect('performance_form_department_head', department_head_id=department_head_id)

            # Function to safely convert string to integer
            def get_rating(key):
                try:
                    return int(request.POST.get(key, 0))
                except (ValueError, TypeError):
                    return 0

            # Create new performance report
            report = PerformanceReport(
                department_head=department_head,
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
            return redirect('performance_form_department_head', department_head_id=department_head_id)

    return render(request, 'staff_monitor/performance_form.html', {
        'department_head': department_head,
        'today': date.today(),
        'is_department_head_evaluation': True
    })

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
                    reports = PerformanceReport.objects.all().order_by('-date')
                else:
                    # Department head sees only reports from their department
                    reports = PerformanceReport.objects.filter(
                        staff__department=department_head.department
                    ).order_by('-date')
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
                    reports = IncidentReport.objects.all().order_by('-incident_date', '-incident_time')
                elif department_head.department.name.lower() == "hr":
                    is_authorized = True
                    reports = IncidentReport.objects.all().order_by('-incident_date', '-incident_time')
                else:
                    # Regular department head is authorized to see their department's reports
                    is_authorized = True
                    reports = IncidentReport.objects.filter(
                        staff__department=department_head.department
                    ).order_by('-incident_date', '-incident_time')
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
            
            # Check if email was sent
            if hasattr(department_head, 'email_sent'):
                if department_head.email_sent:
                    messages.success(request, 'Department Head added successfully. Login credentials have been sent to their email.')
                else:
                    # Email failed to send
                    messages.success(request, 'Department Head added successfully.')
                    messages.warning(request, f'However, the system could not send login credentials via email. Please inform the user that their username is {department_head.user.email} and password is {department_head.user_password}')
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
                
                messages.success(request, 'Staff added successfully.')
                
                return redirect('dashboard')
            except forms.ValidationError as e:
                # Add validation errors back to the form
                form.add_error(None, str(e))
            except Exception as e:
                # Handle any other unexpected errors
                messages.error(request, f"An error occurred: {str(e)}")
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StaffForm()
    return render(request, 'staff_monitor/add_staff.html', {'form': form})

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_delete_reports') or u.is_staff)
def delete_report(request, report_id):
    try:
        report = get_object_or_404(PerformanceReport, id=report_id)
        report_info = f"Performance report for {report.staff.user.get_full_name()} on {report.date}"
        report.delete()
        messages.success(request, f'{report_info} deleted successfully.')
    except PerformanceReport.DoesNotExist:
        messages.error(request, 'Report not found.')
    return redirect('report_list')

@login_required
def check_report_exists(request, staff_id, date):
    staff = get_object_or_404(Staff, id=staff_id)
    
    # Check if user has permission to check this staff member's reports
    if not request.user.is_staff:
        try:
            superintendent = DepartmentHead.objects.get(user=request.user)
            if staff.department != superintendent.department:
                return JsonResponse({'error': 'Permission denied'}, status=403)
        except DepartmentHead.DoesNotExist:
            return JsonResponse({'error': 'Permission denied'}, status=403)

    exists = PerformanceReport.objects.filter(
        staff_id=staff_id,
        date=date
    ).exists()
    return JsonResponse({'exists': exists})

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_manage_departments') or u.is_staff)
def add_department(request):
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        formset = SubDepartmentFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            department = form.save()
            # Set the department for each subdepartment and save
            formset.instance = department
            formset.save()
            messages.success(request, 'Department added successfully.')
            return redirect('department_list')
    else:
        form = DepartmentForm()
        formset = SubDepartmentFormSet()
    
    return render(request, 'staff_monitor/add_department.html', {
        'form': form,
        'formset': formset
    })

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_manage_departments') or u.is_staff)
def department_list(request):
    departments = Department.objects.all().order_by('name')
    return render(request, 'staff_monitor/department_list.html', {
        'departments': departments
    })

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_manage_departments') or u.is_staff)
def edit_department(request, department_id):
    department = get_object_or_404(Department, id=department_id)
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        formset = SubDepartmentFormSet(request.POST, instance=department)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Department updated successfully.')
            return redirect('department_list')
    else:
        form = DepartmentForm(instance=department)
        formset = SubDepartmentFormSet(instance=department)
    
    return render(request, 'staff_monitor/add_department.html', {
        'form': form,
        'formset': formset,
        'department': department
    })

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_manage_departments') or u.is_staff)
def delete_department(request, department_id):
    department = get_object_or_404(Department, id=department_id)
    try:
        department.delete()
        messages.success(request, 'Department deleted successfully.')
    except ProtectedError:
        messages.error(
            request, 
            'Cannot delete this department as it has associated staff members.'
        )
    return redirect('department_list')

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_edit_department_head') or u.is_staff)
def edit_superintendent(request, superintendent_id):
    superintendent = get_object_or_404(DepartmentHead, id=superintendent_id)
    if request.method == 'POST':
        # Get a copy of POST data to modify
        post_data = request.POST.copy()
        
        # Ensure email is included (since it might be disabled in the form)
        if 'email' not in post_data or not post_data['email']:
            post_data['email'] = superintendent.user.email
        
        # Create form with modified POST data
        form = DepartmentHeadForm(post_data, instance=superintendent)
        
        # Check if the form is valid
        if form.is_valid():
            # Save the form
            department_head = form.save()
            
            # Log info about the update
            print(f"Updated department head: {department_head.user.get_full_name()} - Dept: {department_head.department.name}")
            if department_head.subdepartment:
                print(f"Subdepartment: {department_head.subdepartment.name}")
                
            messages.success(request, 'Department Head updated successfully.')
            
            if request.user.is_staff:
                return redirect('superintendent_list')
            else:
                return redirect('dashboard')
        else:
            # Log validation errors for debugging
            print(f"Form errors: {form.errors}")
    else:
        # When loading the form initially, populate with existing data
        form = DepartmentHeadForm(instance=superintendent, initial={
            'first_name': superintendent.user.first_name,
            'last_name': superintendent.user.last_name,
            'email': superintendent.user.email,
            'department': superintendent.department.id,
            'subdepartment': superintendent.subdepartment.id if superintendent.subdepartment else None,
        })
        
    return render(request, 'staff_monitor/add_department_head.html', {
        'form': form,
        'edit_mode': True,
        'superintendent': superintendent
    })

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_delete_department_head') or u.is_staff)
def delete_superintendent(request, superintendent_id):
    superintendent = get_object_or_404(DepartmentHead, id=superintendent_id)
    if request.method == 'POST':
        user = superintendent.user
        superintendent.delete()
        user.delete()
        messages.success(request, 'Department Head deleted successfully.')
    return redirect('dashboard')

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_edit_staff') or u.is_staff)
def edit_staff(request, staff_id):
    staff = get_object_or_404(Staff, id=staff_id)
    if request.method == 'POST':
        # Get a copy of POST data to modify
        post_data = request.POST.copy()
        
        # Ensure email is included (since it might be disabled in the form)
        if 'email' not in post_data or not post_data['email']:
            post_data['email'] = staff.user.email
            
        # Ensure employee_id is included (since it is disabled in the form)
        if 'employee_id' not in post_data or not post_data['employee_id']:
            post_data['employee_id'] = staff.employee_id
            
        form = StaffForm(post_data, instance=staff)
        if form.is_valid():
            try:
                staff = form.save()
                
                # Log info about the update
                print(f"Updated staff: {staff.user.get_full_name()} - Dept: {staff.department.name}")
                if staff.subdepartment:
                    print(f"Subdepartment: {staff.subdepartment.name}")
                    
                messages.success(request, 'Staff member updated successfully.')
                
                if request.user.is_staff:
                    return redirect('staff_list')
                else:
                    return redirect('dashboard')
                    
            except forms.ValidationError as e:
                # Add validation errors back to the form
                form.add_error(None, str(e))
            except Exception as e:
                # Handle any other unexpected errors
                messages.error(request, f"An error occurred: {str(e)}")
        else:
            # Log validation errors for debugging
            print(f"Form errors: {form.errors}")
    else:
        form = StaffForm(instance=staff, initial={
            'first_name': staff.user.first_name,
            'last_name': staff.user.last_name,
            'email': staff.user.email,
            'department': staff.department.id,
            'subdepartment': staff.subdepartment.id if staff.subdepartment else None,
        })
    return render(request, 'staff_monitor/add_staff.html', {
        'form': form,
        'edit_mode': True,
        'staff': staff
    })

@login_required
@user_passes_test(lambda u: can_perform_action(u, 'can_delete_staff') or u.is_staff)
def delete_staff(request, staff_id):
    try:
        staff = get_object_or_404(Staff, id=staff_id)
        
        # Store information for success message
        staff_name = staff.user.get_full_name()
        
        if request.method == 'POST':
            # Get the user associated with this staff
            user = staff.user
            
            # Delete the staff record
            staff.delete()
            
            # Delete the associated user account
            user.delete()
            
            messages.success(request, f'Staff member {staff_name} deleted successfully.')
            
            # Redirect to the appropriate page based on user type
            if request.user.is_staff:  # Admin user
                return redirect('staff_list')
            else:
                # Check if HR head
                try:
                    department_head = DepartmentHead.objects.get(user=request.user)
                    if department_head.is_hr_head or department_head.department.name.lower() == "hr":
                        return redirect('staff_list')
                except DepartmentHead.DoesNotExist:
                    pass
                
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid request method. Staff deletion requires POST method.')
            return redirect('staff_list')
            
    except Staff.DoesNotExist:
        messages.error(request, 'Staff member not found.')
        return redirect('staff_list')
    except Exception as e:
        messages.error(request, f'Error deleting staff member: {str(e)}')
        return redirect('staff_list')

@login_required
def view_report(request, report_id):
    report = get_object_or_404(PerformanceReport, id=report_id)
    
    # Check permissions
    if not request.user.is_staff:
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            
            # HR heads can view any report
            if department_head.is_hr_head or department_head.department.name.lower() == "hr":
                # Continue with viewing the report
                pass
            # Regular department heads can only view reports from their department
            elif report.staff.department != department_head.department:
                messages.error(request, 'You do not have permission to view this report.')
                return redirect('report_list')
        except DepartmentHead.DoesNotExist:
            messages.error(request, 'You do not have permission to view reports.')
            return redirect('dashboard')

    return render(request, 'staff_monitor/print_report.html', {
        'report': report,
        'sections': get_report_sections(report),
        'section_totals': get_section_totals(report)
    })

@login_required
def print_report(request, report_id):
    # Reuse the view_report logic but with print template
    return view_report(request, report_id)

def get_report_sections(report):
    """Helper function to organize report data into sections"""
    sections = {
        'A. JOB KNOWLEDGE/PROFESSIONALISM': [
            {'name': 'Understanding of job responsibility', 'value': report.job_responsibility},
            {'name': 'Good communications skills', 'value': report.communication_skills},
            {'name': 'Identifies & understand patient requirements', 'value': report.patient_requirements},
            {'name': 'Negotiation skills & ability to address queries', 'value': report.negotiation_skills},
            {'name': 'Effective Relationship with management', 'value': report.management_relationship},
            {'name': 'Respect for policies, rules & hospital values', 'value': report.policy_adherence},
            {'name': 'Has ethical behavior & positive attitude', 'value': report.ethical_behavior},
            {'name': 'Honesty and transparency', 'value': report.honesty_transparency}
        ],
        'B. PRODUCTIVITY': [
            {'name': 'Manages a fair work load', 'value': report.workload_management},
            {'name': 'Takes additional responsibilities', 'value': report.additional_responsibilities},
            {'name': 'Develops and follows work procedure', 'value': report.work_procedure}
        ],
        'C. QUALITY OF WORK': [
            {'name': 'Demonstrates accuracy, thoroughness and reliability', 'value': report.accuracy_reliability},
            {'name': 'Communicates views clearly & logically', 'value': report.clear_communication},
            {'name': 'Attendance & punctuality', 'value': report.attendance_punctuality},
            {'name': 'Has good responsibility & accountability', 'value': report.responsibility_accountability}
        ],
        'D. INTERPERSONAL & WORKING RELATIONSHIPS': [
            {'name': 'Interacts effectively with patients, co-workers & public', 'value': report.interaction_effectiveness},
            {'name': 'Has good interpersonal skills', 'value': report.interpersonal_skills},
            {'name': 'Seeks & provides help & cooperation', 'value': report.team_cooperation},
            {'name': 'Exhibits appropriate sensitivity to others feelings', 'value': report.sensitivity},
            {'name': 'Collaborates effectively with cross-functional teams', 'value': report.cross_functional_collaboration}
        ],
        'E. LEADERSHIP, INITIATIVES & RESOURCEFULNESS': [
            {'name': 'Displays proactive behavior', 'value': report.proactive_behavior},
            {'name': 'Is meticulous in following through work ideas', 'value': report.work_ideas},
            {'name': 'Displays competence of working within resources', 'value': report.resource_competence},
            {'name': 'Displays mentoring or guiding others', 'value': report.mentoring_skills},
            {'name': 'Has work delegation skills', 'value': report.delegation_skills},
            {'name': 'Has good decision-making skills', 'value': report.decision_making}
        ],
        'F. PLANNING & ORGANIZING EFFECTIVENESS': [
            {'name': 'Effectively prioritizes work & establishes work plans', 'value': report.work_prioritization},
            {'name': 'Performs tasks thoroughly on time', 'value': report.timely_completion},
            {'name': 'Works within organizational policies & guidelines', 'value': report.policy_compliance},
            {'name': 'Consistency in behavior', 'value': report.behavior_consistency},
            {'name': 'Displays ability to work under pressure', 'value': report.pressure_handling}
        ],
        'G. ADAPTABILITY': [
            {'name': 'Displays adaptability to change', 'value': report.change_adaptability},
            {'name': 'Willing to learn from mistakes', 'value': report.learning_attitude},
            {'name': 'Displays good emotional intelligence', 'value': report.emotional_intelligence}
        ],
        'H. RESULT ORIENTATION': [
            {'name': 'Demonstrates strong commitment & drive', 'value': report.commitment_drive},
            {'name': 'Takes timely decisions', 'value': report.timely_decisions},
            {'name': 'Can be relied on to deliver despite obstacles', 'value': report.obstacle_handling}
        ],
        'I. CLARITY OF VISION': [
            {'name': 'Understands the philosophy of vision & mission', 'value': report.hospital_vision},
            {'name': 'Displays clarity of vision with respect to departments', 'value': report.department_vision}
        ],
        'J. PROBLEM SOLVING': [
            {'name': 'Has the ability to identify problems', 'value': report.problem_identification},
            {'name': 'Identifies alternate approaches/solutions', 'value': report.solution_approach},
            {'name': 'Ability to handle cases under pressure', 'value': report.pressure_case_handling}
        ]
    }
    return sections

def get_section_totals(report):
    """Helper function to calculate section totals"""
    return {
        'A. JOB KNOWLEDGE/PROFESSIONALISM': sum([
            report.job_responsibility, report.communication_skills,
            report.patient_requirements, report.negotiation_skills,
            report.management_relationship, report.policy_adherence,
            report.ethical_behavior, report.honesty_transparency
        ]),
        'B. PRODUCTIVITY': sum([
            report.workload_management, report.additional_responsibilities,
            report.work_procedure
        ]),
        'C. QUALITY OF WORK': sum([
            report.accuracy_reliability, report.clear_communication,
            report.attendance_punctuality, report.responsibility_accountability
        ]),
        'D. INTERPERSONAL & WORKING RELATIONSHIPS': sum([
            report.interaction_effectiveness, report.interpersonal_skills,
            report.team_cooperation, report.sensitivity,
            report.cross_functional_collaboration
        ]),
        'E. LEADERSHIP, INITIATIVES & RESOURCEFULNESS': sum([
            report.proactive_behavior, report.work_ideas,
            report.resource_competence, report.mentoring_skills,
            report.delegation_skills, report.decision_making
        ]),
        'F. PLANNING & ORGANIZING EFFECTIVENESS': sum([
            report.work_prioritization, report.timely_completion,
            report.policy_compliance, report.behavior_consistency,
            report.pressure_handling
        ]),
        'G. ADAPTABILITY': sum([
            report.change_adaptability, report.learning_attitude,
            report.emotional_intelligence
        ]),
        'H. RESULT ORIENTATION': sum([
            report.commitment_drive, report.timely_decisions,
            report.obstacle_handling
        ]),
        'I. CLARITY OF VISION': sum([
            report.hospital_vision, report.department_vision
        ]),
        'J. PROBLEM SOLVING': sum([
            report.problem_identification, report.solution_approach,
            report.pressure_case_handling
        ])
    }

@login_required
def superintendent_list(request):
    # For admin users - show all department heads
    if request.user.is_staff:
        superintendents = DepartmentHead.objects.all()
        departments = Department.objects.all()
        
        # Calculate staff counts based on department and subdepartment matching
        for superintendent in superintendents:
            # Get the base query for staff in this superintendent's department
            staff_query = Staff.objects.filter(department=superintendent.department)
            
            # If the superintendent has a subdepartment assigned, filter by that as well
            if superintendent.subdepartment:
                staff_count = staff_query.filter(subdepartment=superintendent.subdepartment).count()
            else:
                # If no subdepartment is assigned, count all staff in the department
                staff_count = staff_query.count()
            
            # Attach the count to the superintendent object
            superintendent.staff_count = staff_count
        
        return render(request, 'staff_monitor/superintendent_list.html', {
            'superintendents': superintendents,
            'departments': departments,
            'is_admin': True
        })
    else:
        try:
            # Check if user is a department head
            department_head = DepartmentHead.objects.get(user=request.user)
            
            # Special case for HR department heads
            if department_head.is_hr_head or department_head.department.name.lower() == "hr":
                # Ensure the department head is marked as HR head if from HR department
                if not department_head.is_hr_head and department_head.department.name.lower() == "hr":
                    department_head.is_hr_head = True
                    department_head.save()
                
                # Get all departments except HR
                departments = Department.objects.exclude(name__iexact='HR')
                
                # Get all department heads except HR department heads
                superintendents = DepartmentHead.objects.exclude(department__name__iexact='HR')
                
                # Group department heads by department for easier viewing
                superintendents_by_department = {}
                for dept in departments:
                    dept_heads = DepartmentHead.objects.filter(department=dept)
                    
                    # Calculate staff counts for each department head
                    for head in dept_heads:
                        # Get the base query for staff in this head's department
                        staff_query = Staff.objects.filter(department=head.department)
                        
                        # If the head has a subdepartment assigned, filter by that as well
                        if head.subdepartment:
                            staff_count = staff_query.filter(subdepartment=head.subdepartment).count()
                        else:
                            # If no subdepartment is assigned, count all staff in the department
                            staff_count = staff_query.count()
                        
                        # Attach the count to the head object
                        head.staff_count = staff_count
                    
                    if dept_heads.exists():
                        superintendents_by_department[dept.id] = {
                            'name': dept.name,
                            'department_heads': dept_heads
                        }
                
                return render(request, 'staff_monitor/superintendent_list.html', {
                    'superintendents': superintendents,
                    'departments': departments,
                    'is_hr_head': True,
                    'department_head': department_head,
                    'superintendents_by_department': superintendents_by_department,
                    'show_by_department': True  # Flag to enable department-wise view
                })
            else:
                # Regular department head doesn't see the department heads list
                messages.warning(request, "You don't have permission to view this page.")
                return redirect('dashboard')
                
        except DepartmentHead.DoesNotExist:
            # User is neither admin nor department head
            messages.warning(request, "You don't have permission to view this page.")
            return redirect('dashboard')

@login_required
def staff_list(request):
    # For admin users - show all staff
    if request.user.is_staff:
        staff_members = Staff.objects.all()
        departments = Department.objects.all()
        return render(request, 'staff_monitor/staff_list.html', {
            'staff_members': staff_members,
            'departments': departments,
            'is_admin': True
        })
    else:
        try:
            # Check if user is a department head
            department_head = DepartmentHead.objects.get(user=request.user)
            
            # Special case for HR department heads - they see all staff
            if department_head.is_hr_head or department_head.department.name.lower() == "hr":
                # Ensure the department head is marked as HR head if from HR department
                if not department_head.is_hr_head and department_head.department.name.lower() == "hr":
                    department_head.is_hr_head = True
                    department_head.save()
                
                # HR head sees all staff, get all departments for filtering
                staff_members = Staff.objects.all()
                departments = Department.objects.all()
                
                # Group staff by department for easier viewing
                staff_by_department = {}
                for dept in departments:
                    staff_by_department[dept.id] = {
                        'name': dept.name,
                        'staff': Staff.objects.filter(department=dept)
                    }
                
                return render(request, 'staff_monitor/staff_list.html', {
                    'staff_members': staff_members,
                    'departments': departments,
                    'is_hr_head': True,
                    'department_head': department_head,
                    'staff_by_department': staff_by_department,
                    'show_by_department': True  # Flag to enable department-wise view
                })
            
            # Determine if this is a main department head or a subdepartment head
            is_main_department_head = department_head.subdepartment is None
            
            if is_main_department_head:
                # Main department head sees all staff in their department
                staff_members = Staff.objects.filter(department=department_head.department)
                subdepartment_heads = DepartmentHead.objects.filter(
                    department=department_head.department,
                    subdepartment__isnull=False
                )
                departments = [department_head.department]
                
                return render(request, 'staff_monitor/staff_list.html', {
                    'staff_members': staff_members,
                    'departments': departments,
                    'is_main_department_head': True,
                    'department_head': department_head,
                    'subdepartment_heads': subdepartment_heads
                })
            else:
                # Subdepartment head sees only their assigned staff
                staff_members = department_head.managed_staff.all()
                return render(request, 'staff_monitor/staff_list.html', {
                    'staff_members': staff_members,
                    'is_main_department_head': False,
                    'department_head': department_head
                })
                
        except DepartmentHead.DoesNotExist:
            # User is neither admin nor department head
            return redirect('dashboard')

@login_required
def get_subdepartments(request, department_id):
    """Get all subdepartments for a specific department"""
    try:
        department = Department.objects.get(pk=department_id)
        subdepartments = SubDepartment.objects.filter(department=department)
        
        return JsonResponse({
            'subdepartments': list(subdepartments.values('id', 'name'))
        })
    except Department.DoesNotExist:
        return JsonResponse({'error': 'Department not found'}, status=404)
    except Exception as e:
        print(f"Error in get_subdepartments: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# New view for the feedback form
@login_required
def feedback_form(request, staff_id):
    staff = get_object_or_404(Staff, id=staff_id)
    
    # Check if user has permission to evaluate this staff member
    if not request.user.is_staff:  # If not admin
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            
            # HR heads can evaluate any staff
            if department_head.is_hr_head or department_head.department.name.lower() == "hr":
                # Continue with feedback
                pass
            # Regular department heads can only evaluate staff in their department
            elif staff.department != department_head.department:
                messages.error(request, 'You do not have permission to evaluate staff from other departments.')
                return redirect('dashboard')
        except DepartmentHead.DoesNotExist:
            messages.error(request, 'You do not have permission to evaluate staff.')
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
                incident_report.staff = staff
                incident_report.reporter = request.user
                incident_report.incident_description = incident_description
                
                # Set reporter position based on user role
                if request.user.is_staff:
                    reporter_position = "HR Director"
                else:
                    try:
                        department_head = DepartmentHead.objects.get(user=request.user)
                        if department_head.is_hr_head:
                            reporter_position = f"HR Head - {department_head.department.name}"
                        else:
                            reporter_position = f"Department Head - {department_head.department.name}"
                    except DepartmentHead.DoesNotExist:
                        reporter_position = staff.position
                
                incident_report.reporter_position = reporter_position
                
                # Generate a report number if not provided
                if not incident_report.report_number:
                    # Format: IR-YYYYMMDD-StaffID-Count
                    date_str = incident_report.incident_date.strftime('%Y%m%d')
                    
                    # Get the count of reports for this staff member on this date
                    existing_count = IncidentReport.objects.filter(
                        staff=staff,
                        incident_date=incident_report.incident_date
                    ).count()
                    
                    # Create the report number
                    incident_report.report_number = f"IR-{date_str}-{staff.id}-{existing_count + 1:03d}"
                
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
        'staff': staff,
        'today': date.today(),
        'form': form,
    }
    
    # Add department head to context if applicable
    if not request.user.is_staff:
        try:
            department_head = DepartmentHead.objects.get(user=request.user)
            context['department_head'] = department_head
        except DepartmentHead.DoesNotExist:
            pass

    return render(request, 'staff_monitor/feedback_form.html', context)

@login_required
def feedback_form_department_head(request, department_head_id):
    department_head = get_object_or_404(DepartmentHead, id=department_head_id)
    
    # Check if user has permission to evaluate this department head
    if not request.user.is_staff:  # If not admin
        try:
            main_department_head = DepartmentHead.objects.get(user=request.user)
            
            # HR heads can evaluate any department head
            if main_department_head.is_hr_head or main_department_head.department.name.lower() == "hr":
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
    
    # Mark department heads from HR department as HR heads if they're not already
    for head in hr_department_heads:
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
    all_other_heads = DepartmentHead.objects.filter(is_hr_head=False).exclude(department__name__iexact="HR")
    
    return render(request, 'staff_monitor/hr_privileges_list.html', {
        'hr_heads': hr_heads,
        'all_other_heads': all_other_heads
    })

@login_required
@user_passes_test(is_admin)
def toggle_hr_status(request, head_id):
    department_head = get_object_or_404(DepartmentHead, id=head_id)
    
    # Check if this is an HR department member
    is_hr_department = department_head.department.name.lower() == "hr"
    
    if is_hr_department:
        # HR department members should always have HR head status
        if not department_head.is_hr_head:
            department_head.is_hr_head = True
            department_head.save()
            messages.success(request, f'{department_head.user.get_full_name()} is from HR department and has been granted HR privileges automatically')
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
        report_info = f"Incident report #{report.report_number} for {report.staff.user.get_full_name()}"
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
            
            # HR heads can view any report
            if department_head.is_hr_head or department_head.department.name.lower() == "hr":
                # Continue with viewing the report
                pass
            # Regular department heads can only view reports from their department
            elif report.staff.department != department_head.department:
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
            
            # HR heads can view any report
            if department_head.is_hr_head or department_head.department.name.lower() == "hr":
                # Continue with viewing the report
                pass
            # Regular department heads can only view reports from their department
            elif report.staff.department != department_head.department:
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
    # Initialize variables for both GET and POST requests
    success_details = []
    success_count = 0
    error_count = 0
    errors = []
    
    # Get all departments for displaying as reference (used in both GET and POST)
    departments = Department.objects.all().order_by('name')
    
    if request.method == 'POST':
        form = StaffBulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']
            
            try:
                # Read Excel file
                df = pd.read_excel(excel_file)
                
                # Print summary of departments and subdepartments for debugging
                print(f"Available departments: {', '.join([d.name for d in Department.objects.all()])}")
                subdept_info = []
                for dept in Department.objects.all():
                    subdepts = SubDepartment.objects.filter(department=dept)
                    if subdepts.exists():
                        subdept_names = [sd.name for sd in subdepts]
                        subdept_info.append(f"{dept.name}: {', '.join(subdept_names)}")
                    else:
                        subdept_info.append(f"{dept.name}: No subdepartments")
                print("Department/Subdepartment structure:")
                for info in subdept_info:
                    print(f"  - {info}")
                
                # Get all departments for mapping
                departments = {dept.name.lower(): dept for dept in Department.objects.all()}
                
                # Get all subdepartments for mapping - create two dictionaries for different lookup methods
                all_subdepartments = SubDepartment.objects.all()
                
                # Dictionary for looking up by subdepartment name
                subdepartments_by_name = {}
                for subdept in all_subdepartments:
                    subdept_key = subdept.name.lower()
                    if subdept_key not in subdepartments_by_name:
                        subdepartments_by_name[subdept_key] = []
                    subdepartments_by_name[subdept_key].append(subdept)
                
                # Dictionary for looking up by department
                subdepartments_by_dept = {}
                for subdept in all_subdepartments:
                    dept_key = subdept.department.id
                    if dept_key not in subdepartments_by_dept:
                        subdepartments_by_dept[dept_key] = []
                    subdepartments_by_dept[dept_key].append(subdept)
                
                # Process each row in the Excel file
                for index, row in df.iterrows():
                    try:
                        # Extract data from row
                        first_name = str(row['First name']).strip()
                        last_name = str(row['Last name']).strip()
                        
                        # Email is now optional
                        email = None
                        if 'Email' in row and pd.notna(row['Email']):
                            email = str(row['Email']).strip()
                            # Check if email is 'nil', 'none', 'na', etc. and treat as None
                            if email.lower() in ['nil', 'none', 'na', 'n/a', '-', '']:
                                email = None
                            # Validate email uniqueness only if provided
                            elif User.objects.filter(email=email).exists():
                                raise ValueError(f"Email '{email}' is already registered")
                        
                        employee_id = str(row['Employee ID']).strip()
                        position = str(row['Designation']).strip()
                        department_name = str(row['Department']).strip()
                        department_name_lower = department_name.lower()
                        
                        # Parse dates - handle various formats
                        try:
                            joining_date = pd.to_datetime(row['Joining date']).date()
                        except:
                            joining_date = datetime.now().date()
                            
                        # Parse appointment date if available
                        appointment_date = None
                        if 'Date of appointment' in row and pd.notna(row['Date of appointment']):
                            try:
                                appointment_date = pd.to_datetime(row['Date of appointment']).date()
                            except:
                                pass
                        
                        # Validate employee ID (must be unique)
                        if Staff.objects.filter(employee_id=employee_id).exists():
                            raise ValueError(f"Employee ID '{employee_id}' is already in use")
                        
                        # Initialize subdepartment to None
                        subdepartment = None
                        
                        # First, check if the department name is actually a subdepartment
                        if department_name_lower in subdepartments_by_name:
                            possible_subdepts = subdepartments_by_name[department_name_lower]
                            if len(possible_subdepts) == 1:
                                # Only one subdepartment with this name exists
                                subdepartment = possible_subdepts[0]
                                department = subdepartment.department
                            elif len(possible_subdepts) > 1:
                                # Multiple subdepartments with the same name exist in different departments
                                subdept_list = ", ".join([f"{sd.name} ({sd.department.name})" for sd in possible_subdepts])
                                raise ValueError(f"Multiple subdepartments named '{department_name}' found: {subdept_list}. Please specify the department clearly.")
                        
                        # If no subdepartment found, proceed with department search
                        if subdepartment is None:
                            # Find department or raise error
                            if department_name_lower not in departments:
                                # Try partial match with departments
                                matched_dept = None
                                for dept_name, dept in departments.items():
                                    if dept_name in department_name_lower or department_name_lower in dept_name:
                                        matched_dept = dept
                                        break
                                
                                # If still no match, check if it's a subdepartment format like "NURSERY - MATERNITY"
                                if not matched_dept and '-' in department_name:
                                    parts = [p.strip().lower() for p in department_name.split('-')]
                                    if len(parts) == 2:
                                        # Format is "SUBDEPT - DEPT"
                                        subdept_name, parent_dept_name = parts[0], parts[1]
                                        
                                        # Find parent department by name
                                        parent_dept = None
                                        for dept_name, dept in departments.items():
                                            if dept_name.lower() == parent_dept_name or dept_name.lower() in parent_dept_name or parent_dept_name in dept_name.lower():
                                                parent_dept = dept
                                                break
                                        
                                        if parent_dept:
                                            # Look for subdepartment by name within this department
                                            subdept_query = SubDepartment.objects.filter(
                                                department=parent_dept,
                                                name__icontains=subdept_name
                                            )
                                            
                                            if subdept_query.exists():
                                                subdepartment = subdept_query.first()
                                                department = parent_dept
                                                matched_dept = parent_dept
                                                print(f"Found subdepartment {subdepartment.name} in department {department.name}")
                                            else:
                                                # If subdepartment doesn't exist, create it (optional)
                                                try:
                                                    subdepartment = SubDepartment.objects.create(
                                                        name=subdept_name.upper(),
                                                        department=parent_dept
                                                    )
                                                    department = parent_dept
                                                    matched_dept = parent_dept
                                                    print(f"Created new subdepartment {subdepartment.name} in department {department.name}")
                                                except Exception as e:
                                                    print(f"Failed to create subdepartment: {str(e)}")
                                
                                # If still no match, try to find the subdepartment in any department
                                if not matched_dept:
                                    # Final attempt: check if it's a known subdepartment
                                    for subdept_name, subdepts in subdepartments_by_name.items():
                                        if subdept_name in department_name_lower:
                                            # Found a potential subdepartment match
                                            for sd in subdepts:
                                                department = sd.department
                                                subdepartment = sd
                                                matched_dept = department
                                                print(f"Found subdepartment {subdepartment.name} in department {department.name} via lookup")
                                                break
                                            if matched_dept:
                                                break
                                
                                if not matched_dept:
                                    # Prepare list of available departments and subdepartments for error message
                                    available_depts = list(departments.values())
                                    available_depts_str = ", ".join([dept.name for dept in available_depts])
                                    
                                    # Get list of all subdepartments
                                    subdept_list = []
                                    for subdept_name, subdepts in subdepartments_by_name.items():
                                        for sd in subdepts:
                                            subdept_list.append(f"{sd.name} ({sd.department.name})")
                                    
                                    if subdept_list:
                                        available_subdepts_str = ", ".join(subdept_list)
                                        raise ValueError(f"Department '{department_name}' not found in the system. Available departments: {available_depts_str}. Available subdepartments: {available_subdepts_str}. If this is a subdepartment, try format: 'Subdepartment - Department'.")
                                    else:
                                        raise ValueError(f"Department '{department_name}' not found in the system. Available departments: {available_depts_str}. If this is a subdepartment, try format: 'Subdepartment - Department'.")
                                
                                department = matched_dept
                            else:
                                department = departments[department_name_lower]
                        
                        # Create User with or without email
                        if email:
                            user = User.objects.create_user(
                                username=email,
                                email=email,
                                password=None,  # No password set
                                first_name=first_name,
                                last_name=last_name,
                                is_active=False  # Account inactive
                            )
                        else:
                            # Generate a unique username if no email
                            username = f"staff_{uuid.uuid4().hex[:8]}"
                            user = User.objects.create_user(
                                username=username,
                                email=None,  # No email
                                password=None,  # No password set
                                first_name=first_name,
                                last_name=last_name,
                                is_active=False  # Account inactive
                            )
                        
                        # Create Staff with department and subdepartment
                        staff = Staff.objects.create(
                            user=user,
                            employee_id=employee_id,
                            department=department,
                            subdepartment=subdepartment,
                            position=position,
                            joining_date=joining_date,
                            appointment_date=appointment_date
                        )
                        
                        # Create success message with department/subdepartment info
                        success_info = f"Added {first_name} {last_name} to department: {department.name}"
                        if subdepartment:
                            success_info += f", subdepartment: {subdepartment.name}"
                        print(success_info)
                        
                        success_count += 1
                        success_details.append(success_info)
                        
                    except Exception as e:
                        error_count += 1
                        errors.append(f"Row {index+2}: {str(e)}")
                
                # Prepare result message
                if success_count > 0:
                    # Build a detailed success message
                    success_message = f"Successfully added {success_count} staff members."
                    
                    # Show details if there are not too many
                    if len(success_details) <= 5:
                        success_message += "<ul class='mt-2 mb-0'>"
                        for detail in success_details:
                            success_message += f"<li>{detail}</li>"
                        success_message += "</ul>"
                    else:
                        # Just show the first few
                        success_message += "<ul class='mt-2 mb-0'>"
                        for detail in success_details[:3]:
                            success_message += f"<li>{detail}</li>"
                        success_message += f"<li>...and {len(success_details) - 3} more staff members.</li>"
                        success_message += "</ul>"
                    
                    messages.success(request, success_message)
                    
                if error_count > 0:
                    error_message = f"Failed to add {error_count} staff members. Errors: "
                    for i, error in enumerate(errors[:5]):  # Show only first 5 errors
                        error_message += f"<br>{error}"
                    
                    if len(errors) > 5:
                        error_message += f"<br>...and {len(errors) - 5} more errors."
                        
                    messages.error(request, error_message)
                    
                return redirect('staff_list')
                
            except Exception as e:
                messages.error(request, f"Error processing the file: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = StaffBulkUploadForm()
        
    return render(request, 'staff_monitor/bulk_upload_staff.html', {
        'form': form,
        'departments': departments,
        'success_details': success_details,
        'success_count': success_count,
        'error_count': error_count,
        'errors': errors
    })

@login_required
def heartbeat(request):
    """
    Simple view to handle heartbeat requests for keeping the session alive.
    More efficient than hitting dashboard or other complex views.
    """
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

# Added by script to support department head evaluation

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


# Added by script to support department head performance evaluation

@login_required
def performance_form_department_head(request, department_head_id):
    department_head = get_object_or_404(DepartmentHead, id=department_head_id)
    
    # Check if user has permission to evaluate this department head
    if not request.user.is_staff:  # If not admin
        try:
            main_department_head = DepartmentHead.objects.get(user=request.user)
            
            # HR heads can evaluate any department head
            if main_department_head.is_hr_head or main_department_head.department.name.lower() == "hr":
                # Continue with evaluation
                pass
            # Regular department heads can only evaluate subdepartment heads in their department
            elif department_head.department != main_department_head.department or main_department_head.subdepartment is not None:
                messages.error(request, 'You do not have permission to evaluate department heads from other departments.')
                return redirect('dashboard')
        except DepartmentHead.DoesNotExist:
            messages.error(request, 'You do not have permission to evaluate department heads.')
            return redirect('dashboard')

    if request.method == 'POST':
        try:
            # Check if report exists for the date
            evaluation_date = request.POST.get('date')
            if PerformanceReport.objects.filter(department_head=department_head, date=evaluation_date).exists():
                messages.error(request, 'A performance report already exists for this date.')
                return redirect('performance_form_department_head', department_head_id=department_head_id)

            # Function to safely convert string to integer
            def get_rating(key):
                try:
                    return int(request.POST.get(key, 0))
                except (ValueError, TypeError):
                    return 0

            # Create new performance report
            report = PerformanceReport(
                department_head=department_head,
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
            return redirect('performance_form_department_head', department_head_id=department_head_id)

    return render(request, 'staff_monitor/performance_form.html', {
        'department_head': department_head,
        'today': date.today(),
        'is_department_head_evaluation': True
    })


# Added by script to support department head feedback

@login_required
def feedback_form_department_head(request, department_head_id):
    department_head = get_object_or_404(DepartmentHead, id=department_head_id)
    
    # Check if user has permission to evaluate this department head
    if not request.user.is_staff:  # If not admin
        try:
            main_department_head = DepartmentHead.objects.get(user=request.user)
            
            # HR heads can evaluate any department head
            if main_department_head.is_hr_head or main_department_head.department.name.lower() == "hr":
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
