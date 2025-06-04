#!/bin/bash

echo "Running migrations for Render PostgreSQL database"
echo "----------------------------------------------"
echo -n "Enter your full DATABASE_URL from Render (postgres://user:pass@host:port/dbname): "
read DB_URL

export DATABASE_URL=$DB_URL
export RENDER=True
export DEBUG=False

echo ""
echo "Setting up environment..."
echo ""
echo "Running migrations..."
python manage.py migrate

echo ""
echo "Creating superuser..."
export DJANGO_SUPERUSER_USERNAME=Admin
export DJANGO_SUPERUSER_EMAIL=mhitdepts@gmail.com
echo -n "Enter password for superuser: "
read -s DJANGO_SUPERUSER_PASSWORD
export DJANGO_SUPERUSER_PASSWORD

echo ""
python manage.py createsuperuser_if_not_exists

echo ""
echo "Migration completed!" 