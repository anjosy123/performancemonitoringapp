import re

# Read the file
with open('staff_monitor/forms.py', 'r') as f:
    lines = f.readlines()

# Fix indentation issues
fixed_lines = []
in_save_method = False
in_else_block = False
in_try_block = False

for line in lines:
    # Track when we enter the save method
    if 'def save(self, commit=True):' in line:
        in_save_method = True
    
    # Check for else: statement in the save method
    if in_save_method and '        else:' in line:
        in_else_block = True
        fixed_lines.append(line)
        continue

    # Fix indentation for code right after "Create new user" comment
    if in_else_block and '# Create new user for a new department head' in line:
        fixed_lines.append(line)
        continue
    
    # Fix indentation for code after the else block started
    if in_else_block and line.strip() and not line.startswith('            ') and not line.startswith('        if commit:'):
        # This line needs to be indented more
        fixed_line = '            ' + line.lstrip()
        fixed_lines.append(fixed_line)
    elif 'try:' in line and in_save_method:
        in_try_block = True
        fixed_lines.append(line)
    elif in_try_block and 'from django.core.mail import send_mail' in line and not line.startswith('                    '):
        # Fix indentation for code in try block
        fixed_line = '                    ' + line.lstrip()
        fixed_lines.append(fixed_line)
    # Reset flags when we exit blocks
    elif in_else_block and '        if commit:' in line:
        in_else_block = False
        fixed_lines.append(line)
    else:
        fixed_lines.append(line)

# Write the fixed content back
with open('staff_monitor/forms.py', 'w') as f:
    f.writelines(fixed_lines)

print('Indentation fixed successfully!') 