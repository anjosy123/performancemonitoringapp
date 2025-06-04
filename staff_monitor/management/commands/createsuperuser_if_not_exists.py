import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superuser if none exists'

    def handle(self, *args, **options):
        if not User.objects.filter(is_superuser=True).exists():
            username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'Admin')
            email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'mhitdeptsw@gmail.com')
            password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Admin@123')
            
            if not password:
                self.stdout.write(self.style.WARNING('No superuser will be created. Set DJANGO_SUPERUSER_PASSWORD env var to create one.'))
                return
                
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS('Superuser created successfully!'))
        else:
            self.stdout.write(self.style.SUCCESS('Superuser already exists. No need to create one.')) 