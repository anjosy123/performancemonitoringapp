# staff_monitor/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import Staff, PerformanceReport, MedicalSuperintendent, Department
from .forms import PerformanceReportForm, MedicalSuperintendentForm, StaffForm, DepartmentForm
import random
import string
from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.http import JsonResponse
from datetime import date
from django.db.models import ProtectedError

@login_required
def dashboard(request):
    if request.user.is_staff:
        # Admin sees all staff and superintendents
        staff_list = Staff.objects.all()
        superintendents = MedicalSuperintendent.objects.all()
        departments = Department.objects.all()
        
        # Calculate staff count for each superintendent
        for superintendent in superintendents:
            # Count staff members in the superintendent's department
            superintendent.staff_count = Staff.objects.filter(department=superintendent.department).count()
            
    else:
        try:
            # Medical superintendent sees only staff from their department
            superintendent = MedicalSuperintendent.objects.get(user=request.user)
            staff_list = Staff.objects.filter(department=superintendent.department)
            superintendents = []
            departments = [superintendent.department]
        except MedicalSuperintendent.DoesNotExist:
            # If the user is neither admin nor superintendent, show empty list
            staff_list = Staff.objects.none()
            superintendents = []
            departments = []

    return render(request, 'staff_monitor/dashboard.html', {
        'staff_list': staff_list,
        'superintendents': superintendents,
        'departments': departments
    })

@login_required
def performance_form(request, staff_id):
    staff = get_object_or_404(Staff, id=staff_id)
    
    # Check if user has permission to evaluate this staff member
    if not request.user.is_staff:  # If not admin
        try:
            superintendent = MedicalSuperintendent.objects.get(user=request.user)
            if staff.department != superintendent.department:
                messages.error(request, 'You do not have permission to evaluate staff from other departments.')
                return redirect('dashboard')
        except MedicalSuperintendent.DoesNotExist:
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
def report_list(request):
    try:
        if request.user.is_staff:
            # Admin sees all reports
            reports = PerformanceReport.objects.all().order_by('-date')
        else:
            try:
                # Superintendent sees only reports from their department
                superintendent = MedicalSuperintendent.objects.get(user=request.user)
                reports = PerformanceReport.objects.filter(
                    staff__department=superintendent.department
                ).order_by('-date')
            except MedicalSuperintendent.DoesNotExist:
                reports = PerformanceReport.objects.none()
        
        return render(request, 'staff_monitor/report_list.html', {
            'reports': reports,
            'rating_choices': PerformanceReport.RATING_CHOICES
        })
    except Exception as e:
        messages.error(request, f"Error loading reports: {str(e)}")
        return redirect('dashboard')

def is_admin(user):
    return user.is_staff

@login_required
@user_passes_test(is_admin)
def add_superintendent(request):
    if request.method == 'POST':
        form = MedicalSuperintendentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Medical Superintendent added successfully.')
            return redirect('dashboard')
    else:
        form = MedicalSuperintendentForm()
    return render(request, 'staff_monitor/add_superintendent.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def add_staff(request):
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            try:
                # Generate random password
                password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                
                # Create User instance
                user = User.objects.create_user(
                    username=form.cleaned_data['email'],
                    email=form.cleaned_data['email'],
                    password=password,
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name']
                )
                
                # Create Staff instance
                staff = form.save(commit=False)
                staff.user = user
                staff.save()
                
                # Assign staff to superintendent of the same department
                superintendent = MedicalSuperintendent.objects.filter(department=staff.department).first()
                if superintendent:
                    superintendent.managed_staff.add(staff)
                
                try:
                    # Send email with credentials
                    from django.core.mail import send_mail
                    from django.conf import settings
                    
                    email_subject = 'Your Performance Monitoring System Credentials'
                    email_message = f"""
                    Dear {user.get_full_name()},

                    Your account has been created in the Performance Monitoring System.

                    Login Details:
                    Username: {user.username}
                    Password: {password}

                    Please login at: http://127.0.0.1:8000/login/
                    We recommend changing your password after your first login.

                    Best regards,
                    Performance Monitoring System Team
                    """
                    
                    send_mail(
                        email_subject,
                        email_message,
                        settings.EMAIL_HOST_USER,
                        [user.email],
                        fail_silently=False,
                    )
                except Exception as e:
                    # If email fails, delete the created user and staff
                    if user:
                        user.delete()
                    messages.error(request, 'Failed to send login credentials email. Please try again.')
                    return redirect('add_staff')

                messages.success(request, 'Staff added successfully.')
                return redirect('dashboard')
                
            except IntegrityError:
                messages.error(request, 'This email address is already in use. Please use a different email.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StaffForm()
    return render(request, 'staff_monitor/add_staff.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.is_staff)
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
            superintendent = MedicalSuperintendent.objects.get(user=request.user)
            if staff.department != superintendent.department:
                return JsonResponse({'error': 'Permission denied'}, status=403)
        except MedicalSuperintendent.DoesNotExist:
            return JsonResponse({'error': 'Permission denied'}, status=403)

    exists = PerformanceReport.objects.filter(
        staff_id=staff_id,
        date=date
    ).exists()
    return JsonResponse({'exists': exists})

@login_required
@user_passes_test(is_admin)
def add_department(request):
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Department added successfully.')
            return redirect('department_list')
    else:
        form = DepartmentForm()
    return render(request, 'staff_monitor/add_department.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def department_list(request):
    departments = Department.objects.all().order_by('name')
    return render(request, 'staff_monitor/department_list.html', {
        'departments': departments
    })

@login_required
@user_passes_test(is_admin)
def edit_department(request, department_id):
    department = get_object_or_404(Department, id=department_id)
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, 'Department updated successfully.')
            return redirect('department_list')
    else:
        form = DepartmentForm(instance=department)
    return render(request, 'staff_monitor/add_department.html', {
        'form': form,
        'department': department
    })

@login_required
@user_passes_test(is_admin)
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
@user_passes_test(lambda u: u.is_staff)
def edit_superintendent(request, superintendent_id):
    superintendent = get_object_or_404(MedicalSuperintendent, id=superintendent_id)
    if request.method == 'POST':
        form = MedicalSuperintendentForm(request.POST, instance=superintendent)
        if form.is_valid():
            form.save()
            messages.success(request, 'Medical Superintendent updated successfully.')
            return redirect('dashboard')
    else:
        form = MedicalSuperintendentForm(instance=superintendent, initial={
            'first_name': superintendent.user.first_name,
            'last_name': superintendent.user.last_name,
            'email': superintendent.user.email,
        })
    return render(request, 'staff_monitor/add_superintendent.html', {
        'form': form,
        'edit_mode': True,
        'superintendent': superintendent
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def delete_superintendent(request, superintendent_id):
    superintendent = get_object_or_404(MedicalSuperintendent, id=superintendent_id)
    if request.method == 'POST':
        user = superintendent.user
        superintendent.delete()
        user.delete()
        messages.success(request, 'Medical Superintendent deleted successfully.')
    return redirect('dashboard')

@login_required
@user_passes_test(lambda u: u.is_staff)
def edit_staff(request, staff_id):
    staff = get_object_or_404(Staff, id=staff_id)
    if request.method == 'POST':
        form = StaffForm(request.POST, instance=staff)
        if form.is_valid():
            staff = form.save(commit=False)
            # Update user information
            staff.user.first_name = form.cleaned_data['first_name']
            staff.user.last_name = form.cleaned_data['last_name']
            staff.user.email = form.cleaned_data['email']
            staff.user.save()
            staff.save()
            messages.success(request, 'Staff member updated successfully.')
            return redirect('dashboard')
    else:
        form = StaffForm(instance=staff, initial={
            'first_name': staff.user.first_name,
            'last_name': staff.user.last_name,
            'email': staff.user.email,
        })
    return render(request, 'staff_monitor/add_staff.html', {
        'form': form,
        'edit_mode': True,
        'staff': staff
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def delete_staff(request, staff_id):
    staff = get_object_or_404(Staff, id=staff_id)
    if request.method == 'POST':
        user = staff.user
        staff.delete()
        user.delete()
        messages.success(request, 'Staff member deleted successfully.')
    return redirect('dashboard')

@login_required
def view_report(request, report_id):
    report = get_object_or_404(PerformanceReport, id=report_id)
    
    # Check permissions
    if not request.user.is_staff:
        try:
            superintendent = MedicalSuperintendent.objects.get(user=request.user)
            if report.staff.department != superintendent.department:
                messages.error(request, 'You do not have permission to view this report.')
                return redirect('report_list')
        except MedicalSuperintendent.DoesNotExist:
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
    superintendents = MedicalSuperintendent.objects.all()
    return render(request, 'staff_monitor/superintendent_list.html', {
        'superintendents': superintendents
    })

@login_required
def staff_list(request):
    staff_members = Staff.objects.all()
    departments = Department.objects.all()
    return render(request, 'staff_monitor/staff_list.html', {
        'staff_members': staff_members,
        'departments': departments
    })