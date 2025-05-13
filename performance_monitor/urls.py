# performance_monitor/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('staff_monitor.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='staff_monitor/login.html'), name='login'),
    # Fix the logout view to handle both GET and POST requests
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('accounts/logout/', RedirectView.as_view(url='/logout/'), name='logout_redirect'),
]