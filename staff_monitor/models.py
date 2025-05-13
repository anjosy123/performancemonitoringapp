# staff_monitor/models.py

from django.db import models
from django.contrib.auth.models import User

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class MedicalSuperintendent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    contact_number = models.CharField(max_length=15)
    # Add a relationship to manage staff
    managed_staff = models.ManyToManyField('Staff', related_name='supervisors', blank=True)

    def __str__(self):
        return self.user.username

class Staff(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    position = models.CharField(max_length=100)
    joining_date = models.DateField()

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"

class PerformanceReport(models.Model):
    RATING_CHOICES = [
        ('4', 'Excellent/Outstanding'),
        ('3', 'Good/Satisfactory'),
        ('2', 'Average/Needs Improvement'),
        ('1', 'Poor/Unsatisfactory'),
    ]

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    evaluator = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    
    punctuality = models.CharField(max_length=1, choices=RATING_CHOICES)
    appearance = models.CharField(max_length=1, choices=RATING_CHOICES)
    patient_attitude = models.CharField(max_length=1, choices=RATING_CHOICES)
    teamwork = models.CharField(max_length=1, choices=RATING_CHOICES)
    policy_adherence = models.CharField(max_length=1, choices=RATING_CHOICES)
    communication = models.CharField(max_length=1, choices=RATING_CHOICES)
    emergency_handling = models.CharField(max_length=1, choices=RATING_CHOICES)
    initiative = models.CharField(max_length=1, choices=RATING_CHOICES)
    integrity = models.CharField(max_length=1, choices=RATING_CHOICES)
    overall_performance = models.CharField(max_length=1, choices=RATING_CHOICES)
    
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Performance Report - {self.staff.user.get_full_name()} - {self.date}"

    class Meta:
        # Add unique constraint to prevent multiple reports for same staff on same date
        unique_together = ['staff', 'date']