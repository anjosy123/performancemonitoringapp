@echo off
echo Running migrations for Render PostgreSQL database
echo ----------------------------------------------
set /p DB_URL=Enter your full DATABASE_URL from Render (postgres://user:pass@host:port/dbname): 

SET DATABASE_URL=%DB_URL%
SET RENDER=True
SET DEBUG=False

echo.
echo Setting up environment...
echo.
echo Running migrations...
python manage.py migrate

echo.
echo Creating superuser...
SET DJANGO_SUPERUSER_USERNAME=Admin
SET DJANGO_SUPERUSER_EMAIL=mhitdepts@gmail.com
set /p DJANGO_SUPERUSER_PASSWORD=Enter password for superuser: 

python manage.py createsuperuser_if_not_exists

echo.
echo Migration completed!
pause 