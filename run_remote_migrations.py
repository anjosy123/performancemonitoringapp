#!/usr/bin/env python
"""
Script to run migrations against a remote Render database without modifying settings.py
"""
import os
import sys
import getpass
import django
from django.core.management import call_command

# Configuration - replace these values
RENDER_DB_NAME = "hospital_performance"
RENDER_DB_USER = "hospital_performance_user"
RENDER_DB_PASSWORD = "Hit6aAqUjWrCBjSyzqV6LbaG3xAaf8Ri"
RENDER_DB_HOST = "dpg-d0vudkmmcj7s7380i2i0-a.oregon-postgres.render.com"
RENDER_DB_PORT = "5432"

# Set up the environment variables for Django to use
os.environ['DJANGO_SETTINGS_MODULE'] = 'performance_monitor.settings'
os.environ['DATABASE_URL'] = f"postgres://{RENDER_DB_USER}:{RENDER_DB_PASSWORD}@{RENDER_DB_HOST}:{RENDER_DB_PORT}/{RENDER_DB_NAME}"
os.environ['RENDER'] = 'True'
os.environ['DEBUG'] = 'False'

print("\nSetting up Django with remote database connection...")
django.setup()

# Print connection info (without password)
print(f"\nConnecting to: postgres://{RENDER_DB_USER}:*****@{RENDER_DB_HOST}:{RENDER_DB_PORT}/{RENDER_DB_NAME}")

# Check database connection
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    print("✓ Database connection successful!")
except Exception as e:
    print(f"✗ Database connection failed: {str(e)}")
    sys.exit(1)

# Run migrations
print("\nRunning migrations...")
try:
    call_command('showmigrations')
    proceed = input("\nProceed with migrations? (y/n): ")
    if proceed.lower() != 'y':
        print("Migration cancelled.")
        sys.exit(0)

    print("\nApplying migrations...")
    call_command('migrate')
    
    # Check auth tables
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='auth_user'")
        row = cursor.fetchone()
        if row[0] > 0:
            print("✓ auth_user table exists")
        else:
            print("✗ auth_user table DOES NOT exist - migrations may have failed")
    
    # Create superuser if needed
    create_admin = input("\nCreate admin user? (y/n): ")
    if create_admin.lower() == 'y':
        from django.contrib.auth.models import User
        admin_username = input("Admin username (default: Admin): ") or 'Admin'
        admin_email = input("Admin email (default: mhitdepts@gmail.com): ") or 'mhitdepts@gmail.com'
        admin_password = getpass.getpass("Admin password: ")
        
        if User.objects.filter(username=admin_username).exists():
            print(f"User '{admin_username}' already exists. Updating password...")
            user = User.objects.get(username=admin_username)
            user.set_password(admin_password)
            user.email = admin_email
            user.is_superuser = True
            user.is_staff = True
            user.save()
            print(f"Updated user '{admin_username}'")
        else:
            User.objects.create_superuser(
                username="Admin",
                email="mhitdepts@gmail.com",
                password="Admin@123"
            )
            print(f"Created superuser '{admin_username}'")

    print("\n✓ Migration completed successfully!")
    
except Exception as e:
    print(f"✗ Migration failed: {str(e)}")
    sys.exit(1) 