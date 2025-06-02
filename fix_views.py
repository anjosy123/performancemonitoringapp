"""
This script adds the necessary view functions to staff_monitor/views.py 
to support department head evaluation features.
"""

import os
import re

# The functions we need to add
MANAGE_SUBDEPARTMENT_FUNCTION = """
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
"""

DEPARTMENT_HEAD_PERFORMANCE_FUNCTION = """
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
"""

FEEDBACK_DEPARTMENT_HEAD_FUNCTION = """
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
"""

# Path to the views.py file
VIEWS_FILE = 'staff_monitor/views.py'

# Read the current content of views.py
with open(VIEWS_FILE, 'r') as f:
    content = f.read()

# Append the new functions to the end of the file
with open(VIEWS_FILE, 'a') as f:
    f.write("\n\n# Added by script to support department head evaluation\n")
    f.write(MANAGE_SUBDEPARTMENT_FUNCTION)
    f.write("\n\n# Added by script to support department head performance evaluation\n")
    f.write(DEPARTMENT_HEAD_PERFORMANCE_FUNCTION)
    f.write("\n\n# Added by script to support department head feedback\n")
    f.write(FEEDBACK_DEPARTMENT_HEAD_FUNCTION)

print("Functions added successfully!")
print("Now you can run:")
print("python manage.py migrate")
print("python manage.py runserver") 