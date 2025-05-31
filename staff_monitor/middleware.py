import datetime
from django.conf import settings
from django.contrib import auth
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone
from django.http import HttpResponse

class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip processing for HEAD requests (heartbeats) to avoid excessive DB operations
        if request.method == 'HEAD':
            if 'X-Requested-With' in request.headers and request.headers['X-Requested-With'] == 'XMLHttpRequest':
                # For AJAX heartbeats, just return a 200 OK without touching the session
                if request.user.is_authenticated:
                    return HttpResponse(status=200)
                else:
                    return HttpResponse(status=401)  # Unauthorized if not logged in
        
        # Process normal requests
        if request.user.is_authenticated:
            # Get the current timestamp
            current_time = timezone.now()
            
            # Get the last activity time from the session
            last_activity = request.session.get('last_activity')
            
            # If there's a last activity timestamp
            if last_activity:
                try:
                    # Convert from string format to datetime
                    last_activity_time = datetime.datetime.fromisoformat(last_activity)
                    
                    # Check if the time difference is greater than 1 hour (3600 seconds)
                    inactive_time = (current_time - last_activity_time).total_seconds()
                    if inactive_time > 3600:  # 1 hour in seconds
                        # Log the user out
                        auth.logout(request)
                        # Redirect to login page with a message
                        if 'X-Requested-With' in request.headers and request.headers['X-Requested-With'] == 'XMLHttpRequest':
                            return HttpResponse(status=401)  # Unauthorized for AJAX
                        else:
                            return redirect(settings.LOGIN_URL + '?timeout=1')
                except (ValueError, TypeError):
                    # In case of any parsing errors, just update the timestamp
                    pass
            
            # Update the last activity timestamp for non-HEAD requests
            if request.method != 'HEAD':
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
                try:
                    auth.logout(request)
                except Exception as e:
                    # Log but don't crash if there's an issue with logout
                    print(f"Error during logout: {str(e)}")
                
                # Handle AJAX logout requests
                if 'X-Requested-With' in request.headers and request.headers['X-Requested-With'] == 'XMLHttpRequest':
                    return HttpResponse(status=200)
                    
                return redirect(settings.LOGIN_URL)
            
        # For all other requests, continue with the next middleware
        return self.get_response(request) 