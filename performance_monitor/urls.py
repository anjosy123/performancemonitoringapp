# performance_monitor/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.urls import re_path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('staff_monitor.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='staff_monitor/login.html'), name='login'),
    # Fix the logout view to handle both GET and POST requests
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('accounts/logout/', RedirectView.as_view(url='/logout/'), name='logout_redirect'),
    
    # Always serve media files, regardless of DEBUG setting
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

# Serve media files during development (this is still useful for static files)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)