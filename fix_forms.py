from django.contrib.auth.models import User
import os, random, string

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
                    'login_url': login_url  # Use the dynamically determined URL
                }
                
                html_message = render_to_string('staff_monitor/email/welcome_department_head.html', context)
                plain_message = strip_tags(html_message)
                
                send_mail(
                    'Welcome to Mariampur Hospital Performance Monitoring System',
                    plain_message,
                    None,  # Use DEFAULT_FROM_EMAIL from settings
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