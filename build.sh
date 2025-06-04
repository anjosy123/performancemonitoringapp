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
python manage.py makemigrations --noinput || echo "Warning: makemigrations command failed, continuing anyway"
python manage.py showmigrations  # Show migration status for debugging
python manage.py migrate --noinput || { echo "Error: Database migration failed"; exit 1; }

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

# Check if auth_user table exists
echo "Checking for auth_user table..."
python manage.py shell << END
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='auth_user'")
        row = cursor.fetchone()
        if row[0] > 0:
            print("✓ auth_user table exists")
        else:
            print("✗ auth_user table DOES NOT exist - migrations may have failed")
            # Try a more direct approach
            print("Attempting to create auth tables directly...")
            from django.core.management import call_command
            call_command('migrate', 'auth', interactive=False)
            call_command('migrate', 'contenttypes', interactive=False)
            print("Auth migrations completed directly")
except Exception as e:
    print(f"✗ Error checking auth_user table: {e}")
    raise e
END

# Create superuser if not exists
echo "Setting up admin user..."
python manage.py shell << END
import os
import sys
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

ADMIN_USERNAME = 'Admin'
ADMIN_EMAIL = 'mhitdepts@gmail.com'
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

if not ADMIN_PASSWORD:
    print("Warning: ADMIN_PASSWORD environment variable not set. Using default password.")
    ADMIN_PASSWORD = 'Admin@123'  # Fallback password if env var not set

print(f"Attempting to create/update superuser: {ADMIN_USERNAME} / {ADMIN_EMAIL}")

try:
    with transaction.atomic():
        if User.objects.filter(username=ADMIN_USERNAME).exists():
            print(f"Superuser {ADMIN_USERNAME} already exists - updating password")
            user = User.objects.get(username=ADMIN_USERNAME)
            user.set_password(ADMIN_PASSWORD)
            user.email = ADMIN_EMAIL
            user.is_superuser = True
            user.is_staff = True
            user.save()
            print(f"Updated password for superuser {ADMIN_USERNAME}")
        else:
            print(f"Creating new superuser {ADMIN_USERNAME}")
            User.objects.create_superuser(
                username=ADMIN_USERNAME,
                email=ADMIN_EMAIL,
                password=ADMIN_PASSWORD
            )
            print(f"Superuser {ADMIN_USERNAME} created successfully")
except Exception as e:
    print(f"Error creating/updating superuser: {str(e)}")
    # Don't exit on error - this shouldn't halt deployment
    
# Verify all superuser accounts
print("\nAll superuser accounts:")
for user in User.objects.filter(is_superuser=True):
    print(f"- Username: {user.username}, Email: {user.email}, Active: {user.is_active}, Staff: {user.is_staff}")

# Also create a backup admin account just to be safe
try:
    backup_username = "admin"
    if not User.objects.filter(username=backup_username).exists():
        User.objects.create_superuser(
            username=backup_username,
            email="mhitdeptsw@mail.com",
            password=ADMIN_PASSWORD
        )
        print(f"Created backup admin user: {backup_username}")
except Exception as e:
    print(f"Error creating backup admin: {str(e)}")
END

# Final message
echo "Build completed successfully!" 