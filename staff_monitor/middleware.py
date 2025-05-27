import datetime
from django.conf import settings
from django.contrib import auth
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone

class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Get the current timestamp
            current_time = timezone.now()
            
            # Get the last activity time from the session
            last_activity = request.session.get('last_activity')
            
            # If there's a last activity timestamp
            if last_activity:
                # Convert from string format to datetime
                last_activity_time = datetime.datetime.fromisoformat(last_activity)
                
                # Check if the time difference is greater than 1 hour (3600 seconds)
                inactive_time = (current_time - last_activity_time).total_seconds()
                if inactive_time > 3600:  # 1 hour in seconds
                    # Log the user out
                    auth.logout(request)
                    # Redirect to login page with a message
                    return redirect(settings.LOGIN_URL + '?timeout=1')
            
            # Update the last activity timestamp
            request.session['last_activity'] = current_time.isoformat()

        response = self.get_response(request)
        return response

class AllowLogoutViaGetMiddleware:
    """
    Middleware to allow logout via GET requests.
    This overrides Django's default behavior which only allows POST for logout.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'GET' and request.path == '/logout/':
            # Perform logout if this is a GET request to the logout URL
            if request.user.is_authenticated:
                auth.logout(request)
                return redirect(settings.LOGIN_URL)
            
        return self.get_response(request) 