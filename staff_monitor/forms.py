# staff_monitor/forms.py

from django import forms
from django.contrib.auth.models import User
from .models import MedicalSuperintendent, Staff, PerformanceReport, Department
import random
import string
from datetime import date
from django.db.utils import IntegrityError

class PerformanceReportForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'min': date.today().isoformat(),
        }),
        initial=date.today
    )

    class Meta:
        model = PerformanceReport
        exclude = ['evaluator', 'staff']
        widgets = {
            'punctuality': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'appearance': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'patient_attitude': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'teamwork': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'policy_adherence': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'communication': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'emergency_handling': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'initiative': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'integrity': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'overall_performance': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {
            'punctuality': 'Punctuality in Duty',
            'appearance': 'Professional Appearance',
            'patient_attitude': 'Attitude Towards Patients',
            'teamwork': 'Teamwork and Cooperation',
            'policy_adherence': 'Adherence to Hospital Policies',
            'communication': 'Communication Skills',
            'emergency_handling': 'Handling of Emergency Situations',
            'initiative': 'Initiative and Responsibility',
            'integrity': 'Integrity and Ethics',
            'overall_performance': 'Overall Performance',
            'notes': 'Additional Notes'
        }

    def clean_date(self):
        selected_date = self.cleaned_data.get('date')
        staff = self.initial.get('staff')
        
        # Check if date is not in past
        if selected_date < date.today():
            raise forms.ValidationError("Cannot select past dates.")
            
        # Check if report already exists for this date
        if staff and PerformanceReport.objects.filter(staff=staff, date=selected_date).exists():
            raise forms.ValidationError("A performance report already exists for this date.")
            
        return selected_date

# staff_monitor/forms.py

class MedicalSuperintendentForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address'
        })
    )
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter first name'
        })
    )
    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter last name'
        })
    )
    
    class Meta:
        model = MedicalSuperintendent
        fields = ['department', 'contact_number']
        widgets = {
            'department': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'contact_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter contact number',
                'pattern': '[0-9]{10}',
                'title': 'Please enter a valid 10-digit phone number'
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean_contact_number(self):
        contact = self.cleaned_data.get('contact_number')
        if not contact.isdigit() or len(contact) != 10:
            raise forms.ValidationError("Please enter a valid 10-digit phone number.")
        return contact

    def save(self, commit=True):
        # Generate random password
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        # Create User instance
        user = User.objects.create_user(
            username=self.cleaned_data['email'],
            email=self.cleaned_data['email'],
            password=password,
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name']
        )
        
        # Create MedicalSuperintendent instance
        superintendent = super().save(commit=False)
        superintendent.user = user
        
        if commit:
            superintendent.save()
            
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
                # If email fails, delete the created user and raise error
                user.delete()
                raise forms.ValidationError(
                    "Failed to send login credentials email. Please try again or contact support."
                )
        
        return superintendent

class StaffForm(forms.ModelForm):
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter first name'
        })
    )
    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter last name'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address'
        })
    )
    
    class Meta:
        model = Staff
        fields = ['employee_id', 'department', 'position', 'joining_date']
        widgets = {
            'employee_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter employee ID'
            }),
            'department': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter position'
            }),
            'joining_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Check if email exists
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        # Check if username exists (since we use email as username)
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("This email is already in use as a username.")
        return email

    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        if Staff.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError("This Employee ID is already in use.")
        return employee_id

    def save(self, commit=True):
        if commit:
            try:
                # Generate random password
                password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                
                # Create User instance
                user = User.objects.create_user(
                    username=self.cleaned_data['email'],
                    email=self.cleaned_data['email'],
                    password=password,
                    first_name=self.cleaned_data['first_name'],
                    last_name=self.cleaned_data['last_name']
                )
                
                # Create Staff instance
                staff = super().save(commit=False)
                staff.user = user
                staff.save()
                
                return staff
                
            except IntegrityError:
                if 'user' in locals():
                    user.delete()
                raise forms.ValidationError("Error creating user account. Please try again.")
        return super().save(commit=False)

class DepartmentForm(forms.ModelForm):
    name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter department name'
        })
    )
    
    class Meta:
        model = Department
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if Department.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("A department with this name already exists.")
        return name