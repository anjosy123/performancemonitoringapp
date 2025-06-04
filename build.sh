#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Starting build process..."

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --no-input

# Run migrations
echo "Running database migrations..."
python manage.py migrate

# Check database connection
echo "Verifying database connection..."
python manage.py shell << END
try:
    from django.db import connections
    connections['default'].ensure_connection()
    print("✓ Database connection successful")
except Exception as e:
    print(f"✗ Database connection failed: {e}")
    raise e
END

# Create superuser if not exists
echo "Setting up admin user..."
python manage.py shell << END
import os
from django.contrib.auth.models import User
from django.db import IntegrityError

ADMIN_USERNAME = 'Admin'
ADMIN_EMAIL = 'mhitdepts@gmail.com'
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

if not ADMIN_PASSWORD:
    print("Warning: ADMIN_PASSWORD environment variable not set. Using default password.")
    ADMIN_PASSWORD = 'Admin@123'  # Fallback password if env var not set

print(f"Attempting to create superuser: {ADMIN_USERNAME} / {ADMIN_EMAIL}")

try:
    if not User.objects.filter(username=ADMIN_USERNAME).exists():
        User.objects.create_superuser(
            username=ADMIN_USERNAME,
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD
        )
        print(f"Superuser {ADMIN_USERNAME} created successfully")
    else:
        print(f"Superuser {ADMIN_USERNAME} already exists")
        
        # Update password for existing superuser (optional)
        user = User.objects.get(username=ADMIN_USERNAME)
        user.set_password(ADMIN_PASSWORD)
        user.save()
        print(f"Updated password for superuser {ADMIN_USERNAME}")
except Exception as e:
    print(f"Error creating/updating superuser: {e}")
    
# Verify superuser exists
print("Verifying superuser exists:")
for user in User.objects.filter(is_superuser=True):
    print(f"- {user.username} (superuser: {user.is_superuser}, staff: {user.is_staff})")
END

# Final message
echo "Build completed successfully!" 