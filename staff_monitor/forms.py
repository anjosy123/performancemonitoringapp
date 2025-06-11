from django import forms
from django.contrib.auth.models import User
from .models import DepartmentHead, Staff, PerformanceReport, Department, SubDepartment, IncidentReport
from django.forms import inlineformset_factory
import random
import string
from datetime import date

# Add required imports for bulk upload functionality
import pandas as pd
from django.core.exceptions import ValidationError
import uuid
import os

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
            'punctuality': 'Punctuality',
            'appearance': 'Professional Appearance',
            'patient_attitude': 'Attitude towards Patients',
            'teamwork': 'Teamwork',
            'policy_adherence': 'Adherence to Policies',
            'communication': 'Communication Skills',
            'emergency_handling': 'Emergency Handling',
            'initiative': 'Initiative and Proactivity',
            'integrity': 'Integrity and Ethics',
            'overall_performance': 'Overall Performance',
            'notes': 'Additional Notes'
        }

    def clean_date(self):
        date_value = self.cleaned_data.get('date')
        staff_id = self.initial.get('staff_id')
        
        if staff_id and date_value:
            if PerformanceReport.objects.filter(staff_id=staff_id, date=date_value).exists():
                raise forms.ValidationError('A performance report already exists for this date.')
        
        return date_value

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
    # Hidden field to store additional subdepartments
    additional_subdepartments = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
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
        else:
            self.fields['subdepartment'].queryset = SubDepartment.objects.none()
        
        # If we have form data and 'department' in it
        if 'department' in self.data:
            try:
                department_id = int(self.data.get('department'))
                self.fields['subdepartment'].queryset = SubDepartment.objects.filter(department_id=department_id)
            except (ValueError, TypeError):
                pass
                
        # If this is an edit form (instance_user exists), populate first_name, last_name, and email
        if self.instance_user:
            self.fields['first_name'].initial = self.instance_user.first_name
            self.fields['last_name'].initial = self.instance_user.last_name
            self.fields['email'].initial = self.instance_user.email
            self.fields['email'].widget.attrs['readonly'] = True
            self.fields['email'].widget.attrs['disabled'] = True
            self.fields['email'].help_text = "Email cannot be changed once account is created."

    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get('department')
        subdepartment = cleaned_data.get('subdepartment')
        
        # Get additional subdepartments from POST data
        additional_subdepartments = self.data.getlist('additional_subdepartments')
        
        # Store for later use in save method
        self.additional_subdepartments_ids = additional_subdepartments
        
        # If subdepartment is selected, make sure it belongs to the selected department
        if subdepartment and department and subdepartment.department != department:
            # If there's a mismatch, raise validation error
            self.add_error('subdepartment', 'The selected subdepartment does not belong to the selected department.')
            
            # Reset subdepartment queryset to show valid choices
            self.fields['subdepartment'].queryset = SubDepartment.objects.filter(department=department)
        
        # Validate additional subdepartments if any
        if additional_subdepartments:
            for subdept_id in additional_subdepartments:
                try:
                    subdept = SubDepartment.objects.get(id=subdept_id)
                    if subdept.department != department:
                        self.add_error(None, f'Subdepartment {subdept.name} does not belong to the selected department.')
                except SubDepartment.DoesNotExist:
                    self.add_error(None, f'Subdepartment with ID {subdept_id} does not exist.')
        
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        # If no email is provided, that's okay since it's optional now
        if not email:
            return email
        
        # If we're editing an existing user with the same email
        if self.instance_user and self.instance_user.email == email:
            return email
            
        # Check if email exists as either username or email (more thorough check)
        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered in the system.")
            
        return email

    def clean_contact_number(self):
        contact_number = self.cleaned_data.get('contact_number')
        # Add validation for contact number format if needed
        return contact_number

    def save(self, commit=True):
        # Check if we're updating an existing user
        if self.instance and self.instance.pk and hasattr(self.instance, 'user'):
            # Update existing user
            user = self.instance.user
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            
            # Update email if changed
            email = self.cleaned_data.get('email')
            if email and email != user.email:
                user.email = email
                user.username = email  # Update username to match email
                
            user.save()
            
            # Update DepartmentHead instance
            head = super().save(commit)
            
            # Process additional subdepartments if any
            if hasattr(self, 'additional_subdepartments_ids') and self.additional_subdepartments_ids and commit:
                # Store the primary subdepartment in managed_subdepartments as well
                primary_subdept = self.cleaned_data.get('subdepartment')
                subdepartments = []
                
                if primary_subdept:
                    subdepartments.append(primary_subdept)
                
                # Add additional subdepartments
                for subdept_id in self.additional_subdepartments_ids:
                    try:
                        subdept = SubDepartment.objects.get(id=subdept_id)
                        subdepartments.append(subdept)
                    except SubDepartment.DoesNotExist:
                        pass
                
                # Clear existing and add new
                head.managed_subdepartments.clear()
                for subdept in subdepartments:
                    head.managed_subdepartments.add(subdept)
            
            return head
        else:
            # Create new user for a new department head
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            
            # Create User instance
            user = User.objects.create_user(
                username=self.cleaned_data['email'],
                email=self.cleaned_data['email'],
                password=password,
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                is_active=True
            )
            
            # Create DepartmentHead instance
            head = super().save(commit=False)
            head.user = user
            
            if commit:
                head.save()
                
                # Process additional subdepartments if any
                if hasattr(self, 'additional_subdepartments_ids') and self.additional_subdepartments_ids:
                    # Store the primary subdepartment in managed_subdepartments as well
                    primary_subdept = self.cleaned_data.get('subdepartment')
                    subdepartments = []
                    
                    if primary_subdept:
                        subdepartments.append(primary_subdept)
                    
                    # Add additional subdepartments
                    for subdept_id in self.additional_subdepartments_ids:
                        try:
                            subdept = SubDepartment.objects.get(id=subdept_id)
                            subdepartments.append(subdept)
                        except SubDepartment.DoesNotExist:
                            pass
                    
                    # Add all subdepartments
                    for subdept in subdepartments:
                        head.managed_subdepartments.add(subdept)
                
                # Store the generated password to inform the user
                head.user_password = password
                
                # Try to send email with login credentials
                try:
                    from django.core.mail import send_mail
                    from django.template.loader import render_to_string
                    from django.utils.html import strip_tags
                    from django.conf import settings
                    
                    # Determine the login URL based on environment
                    from django.contrib.sites.shortcuts import get_current_site
                    from django.urls import reverse
                    
                    # Get base URL - use RENDER_EXTERNAL_URL if on Render, otherwise use a default
                    if 'RENDER' in os.environ and os.environ.get('RENDER_EXTERNAL_URL'):
                        base_url = os.environ.get('RENDER_EXTERNAL_URL')
                    else:
                        base_url = "http://localhost:8000"
                        
                    login_url = f"{base_url}{reverse('login')}"
                    
                    context = {
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'email': user.email,
                        'password': password,
                        'login_url': login_url 
                    }
                    
                    html_message = render_to_string('staff_monitor/email/welcome_department_head.html', context)
                    plain_message = strip_tags(html_message)
                    
                    send_mail(
                        'Welcome to Mariampur Hospital Performance Monitoring System',
                        plain_message,
                        None,  
                        [user.email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    
                    # Flag to indicate email was sent
                    head.email_sent = True
                except Exception as e:
                    # Flag to indicate email failed
                    head.email_sent = False
                    print(f"Email sending failed: {str(e)}")
                
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
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address (or leave blank if not available)'
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
        
        # If editing an existing staff member, disable employee_id field
        if self.instance and self.instance.pk:
            self.fields['employee_id'].widget.attrs['readonly'] = True
            self.fields['employee_id'].widget.attrs['disabled'] = True
            self.fields['employee_id'].required = False
            # Store the original employee_id to use in save method
            self.initial['employee_id'] = self.instance.employee_id
        
        # If we have form data and 'department' in it
        if 'department' in self.data:
            try:
                department_id = int(self.data.get('department'))
                self.fields['subdepartment'].queryset = SubDepartment.objects.filter(department_id=department_id)
            except (ValueError, TypeError):
                pass

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
        
        # If no email is provided, that's okay since it's optional now
        if not email:
            return email
        
        # If we're editing an existing user with the same email
        if self.instance_user and self.instance_user.email == email:
            return email
            
        # Check if email exists as either username or email (more thorough check)
        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered in the system.")
            
        return email

    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        
        # Skip validation if editing an existing staff member
        if self.instance and self.instance.pk:
            # Return the original employee_id since the field might be disabled in the form
            return self.instance.employee_id
            
        # For new staff members, check if employee_id is unique
        if Staff.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError("This Employee ID is already in use.")
            
        return employee_id

    def save(self, commit=True):
        # Check if we're updating an existing user
        if self.instance_user:
            # Update existing user information
            self.instance_user.first_name = self.cleaned_data['first_name']
            self.instance_user.last_name = self.cleaned_data['last_name']
            
            # Update email if provided and different from current
            new_email = self.cleaned_data.get('email')
            if new_email and new_email != self.instance_user.email:
                self.instance_user.email = new_email
                self.instance_user.username = new_email  # Also update username as it's based on email
            
            if commit:
                self.instance_user.save()
                
            # Update Staff instance
            staff = super().save(commit=False)
            
            # Ensure employee_id remains unchanged when editing
            if self.instance and self.instance.pk:
                staff.employee_id = self.instance.employee_id
                
            if commit:
                staff.save()
                
            return staff
        else:
            # Create new user with or without login credentials based on email availability
            email = self.cleaned_data.get('email')
            
            # Create a User instance
            if email:
                # Create user with email and username (email is available)
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=None,  # No password set, user cannot login until password reset
                    first_name=self.cleaned_data['first_name'],
                    last_name=self.cleaned_data['last_name'],
                    is_active=False  # User account is inactive
                )
            else:
                # Create user with generated username (no email available)
                username = f"staff_{uuid.uuid4().hex[:8]}"  # Generate a unique username
                user = User.objects.create_user(
                    username=username,
                    email=None,  # No email
                    password=None,  # No password
                    first_name=self.cleaned_data['first_name'],
                    last_name=self.cleaned_data['last_name'],
                    is_active=False  # User account is inactive
                )
            
            # Create Staff instance
            staff = super().save(commit=False)
            staff.user = user
            
            if commit:
                staff.save()
            
            return staff

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
        # Check if a department with this name already exists
        if Department.objects.filter(name__iexact=name).exclude(id=self.instance.id if self.instance else None).exists():
            raise forms.ValidationError("A department with this name already exists.")
        return name

# Inline formset for subdepartments
SubDepartmentFormSet = inlineformset_factory(
    Department, 
    SubDepartment, 
    fields=('name',),
    extra=1,
    can_delete=True,
    widgets={
        'name': forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter subdepartment name'
        }),
    }
)

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

class IncidentReportForm(forms.ModelForm):
    # Basic Information
    incident_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control form-input',
            'type': 'date',
            'required': True,
            'id': 'incident_date'
        })
    )
    
    incident_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'class': 'form-control form-input',
            'type': 'time',
            'required': True
        })
    )
    
    incident_location = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control form-input',
            'required': True
        })
    )
    
    report_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-input bg-light',
            'readonly': True,
            'id': 'report_number'
        })
    )
    
    # Incident Photo
    incident_photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control form-input',
            'accept': 'image/*',
            'id': 'incident_photo',
            'capture': 'environment'
        })
    )
    
    # Actions
    immediate_action = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control form-input',
            'rows': 3,
            'placeholder': 'Describe immediate action taken'
        })
    )
    
    follow_up_actions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control form-input',
            'rows': 3,
            'placeholder': 'Describe follow-up action taken'
        })
    )
    
    prepared_by = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-input bg-light',
            'readonly': True
        })
    )
    
    reporter_position = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-input bg-light',
            'readonly': True
        })
    )
    
    class Meta:
        model = IncidentReport
        fields = [
            'incident_date', 'incident_time', 'incident_location', 'report_number',
            'incident_photo', 'immediate_action', 'follow_up_actions', 'prepared_by', 
            'reporter_position'
        ]
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the initial value for prepared_by if user is available
        if 'initial' in kwargs and 'user' in kwargs['initial']:
            self.fields['prepared_by'].initial = kwargs['initial']['user'].get_full_name() 

# New form for bulk staff upload
class StaffBulkUploadForm(forms.Form):
    excel_file = forms.FileField(
        label='Excel File',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx, .xls',
        }),
        help_text='Upload Excel file with staff details (First name, Last name, Email, Employee ID, Designation, Department, Joining date, Date of appointment)'
    )
    
    def clean_excel_file(self):
        excel_file = self.cleaned_data.get('excel_file')
        if not excel_file:
            raise ValidationError('Please upload an Excel file.')
            
        # Check file extension
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            raise ValidationError('Only Excel files (.xlsx, .xls) are supported.')
            
        # Validate file structure and content
        try:
            # Read the Excel file
            df = pd.read_excel(excel_file)
            
            # Check if required columns are present
            required_columns = [
                'First name', 'Last name', 'Employee ID', 
                'Designation', 'Department', 'Joining date'
            ]
            
            # Email is now optional
            recommended_columns = ['Email']
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValidationError(f"Missing required columns: {', '.join(missing_columns)}")
                
            # Warn about missing optional columns
            missing_recommended = [col for col in recommended_columns if col not in df.columns]
            if missing_recommended:
                # This doesn't raise an error, just logs a warning
                print(f"Warning: Missing recommended columns: {', '.join(missing_recommended)}")
                
            # Reset file pointer for further processing
            excel_file.seek(0)
            
            return excel_file
            
        except Exception as e:
            raise ValidationError(f"Error processing Excel file: {str(e)}") 