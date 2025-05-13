#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt
 
python manage.py collectstatic --no-input
python manage.py migrate

# Create superuser using environment variables
echo "from django.contrib.auth.models import User; User.objects.create_superuser('${DJANGO_SUPERUSER_USERNAME}', '${DJANGO_SUPERUSER_EMAIL}', '${DJANGO_SUPERUSER_PASSWORD}') if not User.objects.filter(username='${DJANGO_SUPERUSER_USERNAME}').exists() else print('Admin exists')" | python manage.py shell 