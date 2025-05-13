#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt
 
python manage.py collectstatic --no-input
python manage.py migrate

# Create superuser if not exists
echo "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.com', 'your-password') if not User.objects.filter(username='admin').exists() else print('Admin exists')" | python manage.py shell 