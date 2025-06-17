# staff_monitor/models.py

from django.db import models
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class SubDepartment(models.Model):
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, related_name='subdepartments', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.department.name})"
    
    class Meta:
        ordering = ['name']
        unique_together = ['name', 'department']  # Prevent duplicate subdepartment names within a department

class DepartmentHead(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('left_service', 'Left Service'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    subdepartment = models.ForeignKey(SubDepartment, on_delete=models.SET_NULL, null=True, blank=True)
    designation = models.CharField(max_length=100, default="Department Head")
    contact_number = models.CharField(max_length=15)
    joining_date = models.DateField(null=True, blank=True)
    appointment_date = models.DateField(null=True, blank=True)
    managed_staff = models.ManyToManyField('Staff', related_name='supervisors', blank=True)
    is_hr_head = models.BooleanField(default=False)
    managed_subdepartments = models.ManyToManyField(SubDepartment, related_name='department_heads', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.department}"

class HRPrivileges(models.Model):
    hr_head = models.OneToOneField(DepartmentHead, on_delete=models.CASCADE, related_name='privileges')
    can_add_staff = models.BooleanField(default=False)
    can_edit_staff = models.BooleanField(default=False)
    can_delete_staff = models.BooleanField(default=False)
    can_add_department_head = models.BooleanField(default=False)
    can_edit_department_head = models.BooleanField(default=False)
    can_delete_department_head = models.BooleanField(default=False)
    can_manage_departments = models.BooleanField(default=False)
    can_view_all_reports = models.BooleanField(default=False)
    can_delete_reports = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Privileges for {self.hr_head.user.get_full_name()}"

    class Meta:
        verbose_name = "HR Privileges"
        verbose_name_plural = "HR Privileges"

class Staff(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('left_service', 'Left Service'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=50, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    subdepartment = models.ForeignKey(SubDepartment, on_delete=models.CASCADE, null=True, blank=True)
    position = models.CharField(max_length=100)
    joining_date = models.DateField(null=True, blank=True)
    appointment_date = models.DateField(null=True, blank=True)
    qualification = models.CharField(max_length=200, null=True, blank=True, help_text="Staff member's educational qualification")
    contact_number = models.CharField(max_length=15, null=True, blank=True, help_text="Staff member's contact number")
    managed_by = models.ManyToManyField(DepartmentHead, related_name='assigned_staff', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.position}"

class PerformanceReport(models.Model):
    RATING_CHOICES = [
        (1, 'Poor'),
        (2, 'Fair'),
        (3, 'Good'),
        (4, 'Very Good'),
        (5, 'Excellent')
    ]

    # Basic Information
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, null=True, blank=True)
    department_head = models.ForeignKey(DepartmentHead, on_delete=models.CASCADE, null=True, blank=True, related_name='performance_reports')
    evaluator = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()

    # A. Job Knowledge/Professionalism (8 parameters)
    job_responsibility = models.IntegerField(choices=RATING_CHOICES)
    communication_skills = models.IntegerField(choices=RATING_CHOICES)
    patient_requirements = models.IntegerField(choices=RATING_CHOICES)
    negotiation_skills = models.IntegerField(choices=RATING_CHOICES)
    management_relationship = models.IntegerField(choices=RATING_CHOICES)
    policy_adherence = models.IntegerField(choices=RATING_CHOICES)
    ethical_behavior = models.IntegerField(choices=RATING_CHOICES)
    honesty_transparency = models.IntegerField(choices=RATING_CHOICES)

    # B. Productivity (3 parameters)
    workload_management = models.IntegerField(choices=RATING_CHOICES)
    additional_responsibilities = models.IntegerField(choices=RATING_CHOICES)
    work_procedure = models.IntegerField(choices=RATING_CHOICES)

    # C. Quality of Work (4 parameters)
    accuracy_reliability = models.IntegerField(choices=RATING_CHOICES)
    clear_communication = models.IntegerField(choices=RATING_CHOICES)
    attendance_punctuality = models.IntegerField(choices=RATING_CHOICES)
    responsibility_accountability = models.IntegerField(choices=RATING_CHOICES)

    # D. Interpersonal & Working Relationships (5 parameters)
    interaction_effectiveness = models.IntegerField(choices=RATING_CHOICES)
    interpersonal_skills = models.IntegerField(choices=RATING_CHOICES)
    team_cooperation = models.IntegerField(choices=RATING_CHOICES)
    sensitivity = models.IntegerField(choices=RATING_CHOICES)
    cross_functional_collaboration = models.IntegerField(choices=RATING_CHOICES)

    # E. Leadership, Initiatives & Resourcefulness (6 parameters)
    proactive_behavior = models.IntegerField(choices=RATING_CHOICES)
    work_ideas = models.IntegerField(choices=RATING_CHOICES)
    resource_competence = models.IntegerField(choices=RATING_CHOICES)
    mentoring_skills = models.IntegerField(choices=RATING_CHOICES)
    delegation_skills = models.IntegerField(choices=RATING_CHOICES)
    decision_making = models.IntegerField(choices=RATING_CHOICES)

    # F. Planning & Organizing Effectiveness (5 parameters)
    work_prioritization = models.IntegerField(choices=RATING_CHOICES)
    timely_completion = models.IntegerField(choices=RATING_CHOICES)
    policy_compliance = models.IntegerField(choices=RATING_CHOICES)
    behavior_consistency = models.IntegerField(choices=RATING_CHOICES)
    pressure_handling = models.IntegerField(choices=RATING_CHOICES)

    # G. Adaptability (3 parameters)
    change_adaptability = models.IntegerField(choices=RATING_CHOICES)
    learning_attitude = models.IntegerField(choices=RATING_CHOICES)
    emotional_intelligence = models.IntegerField(choices=RATING_CHOICES)

    # H. Result Orientation (3 parameters)
    commitment_drive = models.IntegerField(choices=RATING_CHOICES)
    timely_decisions = models.IntegerField(choices=RATING_CHOICES)
    obstacle_handling = models.IntegerField(choices=RATING_CHOICES)

    # I. Clarity of Vision (2 parameters)
    hospital_vision = models.IntegerField(choices=RATING_CHOICES)
    department_vision = models.IntegerField(choices=RATING_CHOICES)

    # J. Problem Solving (3 parameters)
    problem_identification = models.IntegerField(choices=RATING_CHOICES)
    solution_approach = models.IntegerField(choices=RATING_CHOICES)
    pressure_case_handling = models.IntegerField(choices=RATING_CHOICES)

    # Additional Fields
    special_remarks = models.TextField(blank=True)
    total_score = models.IntegerField(default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['staff', 'date'],
                condition=models.Q(staff__isnull=False),
                name='unique_staff_date'
            ),
            models.UniqueConstraint(
                fields=['department_head', 'date'],
                condition=models.Q(department_head__isnull=False),
                name='unique_department_head_date'
            ),
            models.CheckConstraint(
                check=(
                    models.Q(staff__isnull=False, department_head__isnull=True) | 
                    models.Q(staff__isnull=True, department_head__isnull=False)
                ),
                name='only_staff_or_department_head'
            )
        ]
        ordering = ['-date']

    def calculate_total_score(self):
        """Calculate total score from all parameters"""
        score = 0
        
        # Section A: Job Knowledge/Professionalism (8 parameters)
        score += sum(filter(None, [
            self.job_responsibility,
            self.communication_skills,
            self.patient_requirements,
            self.negotiation_skills,
            self.management_relationship,
            self.policy_adherence,
            self.ethical_behavior,
            self.honesty_transparency
        ]))

        # Section B: Productivity (3 parameters)
        score += sum(filter(None, [
            self.workload_management,
            self.additional_responsibilities,
            self.work_procedure
        ]))

        # Section C: Quality of Work (4 parameters)
        score += sum(filter(None, [
            self.accuracy_reliability,
            self.clear_communication,
            self.attendance_punctuality,
            self.responsibility_accountability
        ]))

        # Section D: Interpersonal & Working Relationships (5 parameters)
        score += sum(filter(None, [
            self.interaction_effectiveness,
            self.interpersonal_skills,
            self.team_cooperation,
            self.sensitivity,
            self.cross_functional_collaboration
        ]))

        # Section E: Leadership (6 parameters)
        score += sum(filter(None, [
            self.proactive_behavior,
            self.work_ideas,
            self.resource_competence,
            self.mentoring_skills,
            self.delegation_skills,
            self.decision_making
        ]))

        # Section F: Planning & Organizing (5 parameters)
        score += sum(filter(None, [
            self.work_prioritization,
            self.timely_completion,
            self.policy_compliance,
            self.behavior_consistency,
            self.pressure_handling
        ]))

        # Section G: Adaptability (3 parameters)
        score += sum(filter(None, [
            self.change_adaptability,
            self.learning_attitude,
            self.emotional_intelligence
        ]))

        # Section H: Result Orientation (3 parameters)
        score += sum(filter(None, [
            self.commitment_drive,
            self.timely_decisions,
            self.obstacle_handling
        ]))

        # Section I: Clarity of Vision (2 parameters)
        score += sum(filter(None, [
            self.hospital_vision,
            self.department_vision
        ]))

        # Section J: Problem Solving (3 parameters)
        score += sum(filter(None, [
            self.problem_identification,
            self.solution_approach,
            self.pressure_case_handling
        ]))

        return score

    def calculate_percentage(self):
        """Calculate percentage based on total score"""
        total_parameters = 42  # Total number of parameters across all sections
        max_possible_score = total_parameters * 5  # Each parameter has max score of 5
        actual_score = self.calculate_total_score()
        return (actual_score / max_possible_score) * 100

    def save(self, *args, **kwargs):
        self.total_score = self.calculate_total_score()
        self.percentage = self.calculate_percentage()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Performance Report - {self.staff.user.get_full_name()} - {self.date}"

    def get_performance_status(self):
        if self.percentage < 50:
            return "Needs improvement & reassessment after 3 months"
        elif 50 <= self.percentage <= 75:
            return "Satisfactory performance but under observation"
        else:
            return "Good performance"

class IncidentReport(models.Model):
    # Basic Information
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='incident_reports', null=True, blank=True)
    department_head = models.ForeignKey(DepartmentHead, on_delete=models.CASCADE, null=True, blank=True, related_name='incident_reports')
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reported_incidents')
    report_number = models.CharField(max_length=50, unique=True)
    
    # Incident Details
    incident_date = models.DateField()
    incident_time = models.TimeField()
    incident_location = models.CharField(max_length=255)
    
    # Nature of Incident (stored as JSON)
    incident_types = models.TextField(default="[]")  # JSON string of list
    other_incident_type = models.CharField(max_length=255, blank=True, null=True)
    incident_description = models.TextField(blank=True)  # New field for describing selected incidents
    
    # Related Parties (stored as JSON)
    related_parties = models.TextField(default="[]")  # JSON string of list
    
    # Individuals Involved (stored as JSON)
    individuals_involved = models.TextField(default="[]")  # JSON string containing individual names, departments, positions, roles
    
    # Incident Photo
    incident_photo = models.ImageField(upload_to='incident_photos/', blank=True, null=True)
    
    # Action Taken
    immediate_action = models.TextField(blank=True)
    follow_up_actions = models.TextField(blank=True)
    
    # Report Preparation
    prepared_by = models.CharField(max_length=255)
    reporter_position = models.CharField(max_length=255, blank=True)
    
    # Status
    STATUS_CHOICES = [
        ('reported', 'Reported'),
        ('under_investigation', 'Under Investigation'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='reported')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-incident_date', '-incident_time']
        
    def __str__(self):
        if self.staff:
            return f"Incident Report #{self.report_number} - {self.staff.user.get_full_name()} - {self.incident_date}"
        elif self.department_head:
            return f"Incident Report #{self.report_number} - {self.department_head.user.get_full_name()} - {self.incident_date}"
        else:
            return f"Incident Report #{self.report_number} - {self.incident_date}"
        
    def set_incident_types(self, types_list):
        import json
        self.incident_types = json.dumps(types_list)
        
    def get_incident_types(self):
        import json
        return json.loads(self.incident_types)
        
    def set_related_parties(self, parties_list):
        import json
        self.related_parties = json.dumps(parties_list)
        
    def get_related_parties(self):
        import json
        return json.loads(self.related_parties)
        
    def set_individuals_involved(self, individuals_list):
        import json
        self.individuals_involved = json.dumps(individuals_list)
        
    def get_individuals_involved(self):
        import json
        return json.loads(self.individuals_involved)
        
    @property
    def photo_url(self):
        """Safe way to get the incident photo URL"""
        from django.conf import settings
        import os
        
        if self.incident_photo:
            try:
                # First, try the direct path
                if os.path.exists(self.incident_photo.path):
                    return self.incident_photo.url
                
                # If direct path doesn't exist, try with normalized report number
                safe_report_number = self.report_number.replace('-', '_')
                potential_filename = f"incident_{safe_report_number}.jpg"
                potential_path = os.path.join(settings.MEDIA_ROOT, 'incident_photos', potential_filename)
                
                if os.path.exists(potential_path):
                    return f"{settings.MEDIA_URL}incident_photos/{potential_filename}"
                    
            except (ValueError, AttributeError, FileNotFoundError) as e:
                logger.error(f"Error retrieving photo URL: {str(e)}")
                pass
        
        # Return default image if original photo doesn't exist
        return f"{settings.STATIC_URL}images/image-not-found.png"