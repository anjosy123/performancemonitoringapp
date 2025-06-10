from django.conf import settings

def media_settings(request):
    """
    Add media-related context variables to all templates.
    """
    return {
        'MEDIA_URL': settings.MEDIA_URL,
        'MEDIA_ROOT': settings.MEDIA_ROOT,
    } 