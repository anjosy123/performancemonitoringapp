from django.db import migrations

def transfer_contact_info(apps, schema_editor):
    Staff = apps.get_model('staff_monitor', 'Staff')
    for staff in Staff.objects.all():
        if hasattr(staff, 'contact_info') and staff.contact_info:
            staff.contact_number = staff.contact_info
            staff.save()

class Migration(migrations.Migration):

    dependencies = [
        ('staff_monitor', '0008_remove_departmenthead_status_notes_and_more'),
    ]

    operations = [
        migrations.RunPython(transfer_contact_info),
    ] 