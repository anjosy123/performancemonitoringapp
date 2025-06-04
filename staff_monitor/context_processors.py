from django.conf import settings
import os

def image_paths(request):
    """
    Context processor to provide image paths with fallbacks
    """
    # Get the DEFAULT_IMAGE_PATHS from settings
    default_paths = getattr(settings, 'DEFAULT_IMAGE_PATHS', {})
    
    # For each path, set up image paths with original as preference
    image_paths = {}
    for key, fallback_path in default_paths.items():
        # Always try to use the original path first
        image_paths[key] = f"images/{key}.JPG"
    
    return {'image_paths': image_paths} 