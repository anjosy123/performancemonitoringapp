# staff_monitor/forms.py

from django import forms
from django.contrib.auth.models import User
from .models import DepartmentHead, Staff, PerformanceReport, Department, SubDepartment
from django.forms import inlineformset_factory
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

class DepartmentHeadForm(forms.ModelForm):
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
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'department-select'
        })
    )
    subdepartment = forms.ModelChoiceField(
        queryset=SubDepartment.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'subdepartment-select'
        })
    )
    designation = forms.CharField(
        required=True,
        initial="Department Head",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter designation'
        })
    )
    joining_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    appointment_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    contact_number = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter contact number'
        })
    )
    
    class Meta:
        model = DepartmentHead
        fields = ['department', 'subdepartment', 'designation', 'joining_date', 'appointment_date', 'contact_number']
    
    def __init__(self, *args, **kwargs):
        self.instance_user = None
        if 'instance' in kwargs and kwargs['instance']:
            self.instance_user = kwargs['instance'].user
            
        super().__init__(*args, **kwargs)
        
        # If we have a department in the instance, filter subdepartments
        if self.instance and hasattr(self.instance, 'department') and self.instance.department:
            self.fields['subdepartment'].queryset = SubDepartment.objects.filter(department=self.instance.department)
            # Set initial value for department to ensure it's available for subdepartment filtering
            self.initial['department'] = self.instance.department.id
        
        # If we have form data and 'department' in it
        if 'department' in self.data:
            try:
                department_id = int(self.data.get('department'))
                self.fields['subdepartment'].queryset = SubDepartment.objects.filter(department_id=department_id)
            except (ValueError, TypeError):
                pass
                
        # If this is an edit form (instance_user exists), disable the email field
        if self.instance_user:
            self.fields['email'].widget.attrs['readonly'] = True
            self.fields['email'].widget.attrs['disabled'] = True
            self.fields['email'].help_text = "Email cannot be changed once account is created."

    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get('department')
        subdepartment = cleaned_data.get('subdepartment')
        
        # If subdepartment is selected, make sure it belongs to the selected department
        if subdepartment and department and subdepartment.department != department:
            # If there's a mismatch, raise validation error
            self.add_error('subdepartment', 'The selected subdepartment does not belong to the selected department.')
            
            # Reset subdepartment queryset to show valid choices
            self.fields['subdepartment'].queryset = SubDepartment.objects.filter(department=department)
        
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        # If we're editing an existing user
        if self.instance_user and self.instance_user.email == email:
            return email
            
        # Check if email exists for a new user
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
            
        return email

    def clean_contact_number(self):
        contact = self.cleaned_data.get('contact_number')
        if not contact.isdigit() or len(contact) != 10:
            raise forms.ValidationError("Please enter a valid 10-digit phone number.")
        return contact

    def save(self, commit=True):
        # Check if we're updating an existing user
        if self.instance_user:
            # Update existing user information
            self.instance_user.first_name = self.cleaned_data['first_name']
            self.instance_user.last_name = self.cleaned_data['last_name']
            
            if commit:
                self.instance_user.save()
                
            # Update DepartmentHead instance
            department_head = super().save(commit=False)
            
            if commit:
                department_head.save()
                
            return department_head
        else:
            # Create new user for a new department head
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            
            # Create User instance
            user = User.objects.create_user(
                username=self.cleaned_data['email'],
                email=self.cleaned_data['email'],
                password=password,
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name']
            )
            
            # Create DepartmentHead instance
            head = super().save(commit=False)
            head.user = user
            
            if commit:
                head.save()
                
                # Store the password as an attribute so the view can access it
                head.user_password = password
                
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
                        fail_silently=True,  # Changed to True to prevent exceptions
                    )
                    # Mark successful email sending
                    head.email_sent = True
                except Exception:
                    # Just mark that email wasn't sent, but don't raise an exception
                    head.email_sent = False
            
            return head

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
        fields = ['employee_id', 'department', 'subdepartment', 'position', 'joining_date', 'appointment_date']
        widgets = {
            'employee_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter employee ID'
            }),
            'department': forms.Select(attrs={
                'class': 'form-control',
                'required': True,
                'id': 'department-select'
            }),
            'subdepartment': forms.Select(attrs={
                'class': 'form-control',
                'required': False,
                'id': 'subdepartment-select'
            }),
            'position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter position'
            }),
            'joining_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'appointment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.instance_user = None
        if 'instance' in kwargs and kwargs['instance']:
            self.instance_user = kwargs['instance'].user
            
        super().__init__(*args, **kwargs)
        
        # If we have a department in the instance, filter subdepartments
        if self.instance and hasattr(self.instance, 'department') and self.instance.department:
            self.fields['subdepartment'].queryset = SubDepartment.objects.filter(department=self.instance.department)
            # Set initial value for department to ensure it's available for subdepartment filtering
            self.initial['department'] = self.instance.department.id
        else:
            self.fields['subdepartment'].queryset = SubDepartment.objects.none()
        
        # If we have form data and 'department' in it
        if 'department' in self.data:
            try:
                department_id = int(self.data.get('department'))
                self.fields['subdepartment'].queryset = SubDepartment.objects.filter(department_id=department_id)
            except (ValueError, TypeError):
                pass
                
        # If this is an edit form (instance_user exists), disable the email field
        if self.instance_user:
            self.fields['email'].widget.attrs['readonly'] = True
            self.fields['email'].widget.attrs['disabled'] = True
            self.fields['email'].help_text = "Email cannot be changed once account is created."

    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get('department')
        subdepartment = cleaned_data.get('subdepartment')
        
        # If subdepartment is selected, make sure it belongs to the selected department
        if subdepartment and department and subdepartment.department != department:
            # If there's a mismatch, raise validation error
            self.add_error('subdepartment', 'The selected subdepartment does not belong to the selected department.')
            
            # Reset subdepartment queryset to show valid choices
            self.fields['subdepartment'].queryset = SubDepartment.objects.filter(department=department)
        
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        # If we're editing an existing user
        if self.instance_user and self.instance_user.email == email:
            return email
            
        # Check if email exists as either username or email (more thorough check)
        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered in the system.")
            
        return email

    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        if Staff.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError("This Employee ID is already in use.")
        return employee_id

    def save(self, commit=True):
        # Check if we're updating an existing user
        if self.instance_user:
            # Update existing user information
            self.instance_user.first_name = self.cleaned_data['first_name']
            self.instance_user.last_name = self.cleaned_data['last_name']
            
            if commit:
                self.instance_user.save()
                
            # Update Staff instance
            staff = super().save(commit=False)
            
            if commit:
                staff.save()
                
            return staff
        else:
            # Create new user for a new staff
            try:
                # Check again if the username/email already exists to avoid race conditions
                email = self.cleaned_data['email']
                if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
                    raise forms.ValidationError("This email is already registered in the system.")
                    
                # Create Staff instance first without saving to DB
                staff = super().save(commit=False)
                
                # Generate random password
                password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                
                # Create User instance with transaction
                from django.db import transaction
                with transaction.atomic():
                    # Create User instance
                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=password,
                        first_name=self.cleaned_data['first_name'],
                        last_name=self.cleaned_data['last_name']
                    )
                    
                    # Attach user to staff
                    staff.user = user
                    
                    if commit:
                        staff.save()
                        
                        # Store the password as an attribute so the view can access it
                        staff.user_password = password
                        
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
                                fail_silently=True,  # Set to True to prevent exceptions
                            )
                            # Mark successful email sending
                            staff.email_sent = True
                        except Exception:
                            # Just mark that email wasn't sent, but don't raise an exception
                            staff.email_sent = False
                
                return staff
                
            except IntegrityError as e:
                # Provide more specific error message based on the exception
                if 'UNIQUE constraint' in str(e):
                    raise forms.ValidationError("This email is already in use. Please use a different email address.")
                else:
                    raise forms.ValidationError(f"Database error: {str(e)}")
            except forms.ValidationError as e:
                # Propagate validation errors
                raise e
            except Exception as e:
                # Handle any other unexpected errors
                raise forms.ValidationError(f"An unexpected error occurred: {str(e)}")
                
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
        
        # Exclude current instance when checking for duplicates
        queryset = Department.objects.filter(name__iexact=name)
        
        # If this is an update (instance exists), exclude the current instance from the check
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
            
        if queryset.exists():
            raise forms.ValidationError("A department with this name already exists.")
            
        return name

class SubDepartmentForm(forms.ModelForm):
    name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter subdepartment name'
        })
    )
    
    class Meta:
        model = SubDepartment
        fields = ['name']

# Create a formset for adding multiple subdepartments at once
SubDepartmentFormSet = inlineformset_factory(
    Department, 
    SubDepartment,
    form=SubDepartmentForm,
    extra=1,  # Start with one empty form
    can_delete=True
)