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

    today = date.today()
    
    # Check if there's an existing report for selected date
    existing_report = None
    selected_date = request.POST.get('date', today)
    try:
        existing_report = PerformanceReport.objects.get(
            staff=staff,
            date=selected_date
        )
        if existing_report:
            messages.warning(
                request, 
                f'A performance report already exists for {selected_date}, submitted by {existing_report.evaluator.get_full_name()}'
            )
    except PerformanceReport.DoesNotExist:
        pass

    if request.method == 'POST':
        form = PerformanceReportForm(request.POST, initial={'staff': staff})
        if form.is_valid():
            if existing_report:
                messages.error(
                    request, 
                    'Cannot submit: A performance report already exists for this date.'
                )
            else:
                report = form.save(commit=False)
                report.evaluator = request.user
                report.staff = staff
                try:
                    report.save()
                    messages.success(request, 'Performance evaluation submitted successfully.')
                    return redirect('dashboard')
                except IntegrityError:
                    messages.error(request, 'A report already exists for this date.')
        else:
            messages.error(request, 'Please complete all evaluation criteria.')
    else:
        form = PerformanceReportForm(initial={
            'staff': staff,
            'date': today
        })

    return render(request, 'staff_monitor/performance_form.html', {
        'form': form,
        'staff': staff,
        'rating_choices': PerformanceReport.RATING_CHOICES,
        'today': today,
        'existing_report': existing_report
    })

@login_required
def report_list(request):
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