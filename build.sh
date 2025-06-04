#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate

# Create superuser if not exists
python manage.py shell << END
from django.contrib.auth.models import User
from django.db import IntegrityError
try:
    User.objects.create_superuser('admin', 'admin@example.com', '$ADMIN_PASSWORD')
except IntegrityError:
    print('Superuser already exists')
END 