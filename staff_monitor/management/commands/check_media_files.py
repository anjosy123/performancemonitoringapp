from django.core.management.base import BaseCommand
from django.conf import settings
from staff_monitor.models import IncidentReport
import os
import shutil

class Command(BaseCommand):
    help = 'Check for missing media files and create placeholders if needed'

    def handle(self, *args, **options):
        self.stdout.write('Checking for missing incident photos...')
        
        # Ensure media directories exist
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        incident_photos_dir = os.path.join(settings.MEDIA_ROOT, 'incident_photos')
        os.makedirs(incident_photos_dir, exist_ok=True)
        
        # Get all incident reports with photos
        reports_with_photos = IncidentReport.objects.exclude(incident_photo='')
        
        missing_count = 0
        for report in reports_with_photos:
            photo_path = os.path.join(settings.MEDIA_ROOT, str(report.incident_photo))
            
            if not os.path.exists(photo_path) or not os.path.isfile(photo_path):
                missing_count += 1
                self.stdout.write(self.style.WARNING(
                    f'Missing photo for incident report #{report.report_number}: {report.incident_photo}'
                ))
                
                # Option to create a placeholder
                placeholder_path = os.path.join(settings.STATIC_ROOT, 'images', 'placeholder-photo.svg')
                if os.path.exists(placeholder_path):
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(photo_path), exist_ok=True)
                    
                    # Copy the placeholder to the missing file location
                    try:
                        shutil.copy(placeholder_path, photo_path)
                        self.stdout.write(self.style.SUCCESS(
                            f'Created placeholder for {report.incident_photo}'
                        ))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f'Failed to create placeholder: {str(e)}'
                        ))
        
        if missing_count == 0:
            self.stdout.write(self.style.SUCCESS('All incident photos are present.'))
        else:
            self.stdout.write(self.style.WARNING(
                f'Found {missing_count} missing incident photos.'
            ))