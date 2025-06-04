from django.conf import settings
import os

def image_paths(request):
    """
    Context processor to provide image paths with fallbacks
    """
    # Get the DEFAULT_IMAGE_PATHS from settings
    default_paths = getattr(settings, 'DEFAULT_IMAGE_PATHS', {})
    
    # Check if we're on Render production environment
    is_render = os.environ.get('RENDER', 'False').lower() == 'true'
    
    # For each path, check if it exists or use fallback
    image_paths = {}
    for key, fallback_path in default_paths.items():
        # On Render, always use fallback to avoid 404s
        if is_render:
            image_paths[key] = fallback_path
        else:
            # For local development, try to use original path if it exists
            original_path = f"images/{key}.JPG"  
            static_dir = getattr(settings, 'STATICFILES_DIRS', [None])[0]
            
            if static_dir and os.path.exists(os.path.join(static_dir, original_path)):
                image_paths[key] = original_path
            else:
                image_paths[key] = fallback_path
    
    return {'image_paths': image_paths} 