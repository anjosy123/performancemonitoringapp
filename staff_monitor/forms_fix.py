import random
import string
from django import forms
from django.contrib.auth.models import User

class DepartmentHeadForm(forms.ModelForm):
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