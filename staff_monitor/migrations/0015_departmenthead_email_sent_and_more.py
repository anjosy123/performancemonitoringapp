# Generated by Django 5.2.1 on 2025-06-25 04:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('staff_monitor', '0014_departmenthead_managed_subdepartment_heads'),
    ]

    operations = [
        migrations.AddField(
            model_name='departmenthead',
            name='email_sent',
            field=models.BooleanField(default=False, help_text='Whether welcome email was sent successfully'),
        ),
        migrations.AddField(
            model_name='departmenthead',
            name='user_password',
            field=models.CharField(blank=True, help_text='Temporary password for new users', max_length=128, null=True),
        ),
    ]
