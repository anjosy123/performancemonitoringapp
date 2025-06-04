import subprocess
import sys
import os

def run_command(command):
    """Run a command and return the output."""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            encoding='utf-8'
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

# Find PostgreSQL installation
potential_paths = [
    r'C:\Program Files\PostgreSQL',
    r'C:\Program Files (x86)\PostgreSQL',
]

# Try to find the psql executable
psql_path = None
for base_path in potential_paths:
    if os.path.exists(base_path):
        # Check for version folders
        for item in os.listdir(base_path):
            version_path = os.path.join(base_path, item)
            if os.path.isdir(version_path):
                possible_psql = os.path.join(version_path, 'bin', 'psql.exe')
                if os.path.exists(possible_psql):
                    psql_path = possible_psql
                    break
        if psql_path:
            break

if not psql_path:
    print("Could not find PostgreSQL installation. Please install PostgreSQL or make sure it's in the standard location.")
    sys.exit(1)

print(f"Found PostgreSQL at: {psql_path}")

# Path to store SQL commands
sql_file = os.path.join(os.getcwd(), 'setup_postgres.sql')

# Create SQL commands
with open(sql_file, 'w') as f:
    f.write("""
-- Create user if it doesn't exist
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'Admin') THEN
      CREATE ROLE "Admin" LOGIN PASSWORD 'Admin@123';
   END IF;
END
$do$;

-- Grant privileges to the user
ALTER ROLE "Admin" CREATEDB;

-- Create database if it doesn't exist
SELECT 'CREATE DATABASE hospital_performance OWNER "Admin"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'hospital_performance');

-- Connect to the new database and grant privileges
\\c hospital_performance
GRANT ALL PRIVILEGES ON DATABASE hospital_performance TO "Admin";
GRANT ALL PRIVILEGES ON SCHEMA public TO "Admin";
""")

# Run the SQL file
print("Creating PostgreSQL user and database...")
postgres_command = f'"{psql_path}" -U postgres -f "{sql_file}"'
print(f"Running command: {postgres_command}")
print("You may be prompted for the 'postgres' user password.")

success, output = run_command(postgres_command)
if success:
    print("PostgreSQL user and database created successfully!")
    print("Now you can run 'python manage.py migrate' to set up the tables.")
else:
    print("Error creating PostgreSQL user and database:")
    print(output)
    print("\nPlease check your PostgreSQL installation and try again.")
    print("Alternatively, you can create the user and database manually using pgAdmin 4.")

# Clean up
os.remove(sql_file) 