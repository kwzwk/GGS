from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Page, Upload


@receiver(post_delete, sender=Upload)
@receiver(post_delete, sender=Page)
def delete_files(sender, instance, **kwargs):
    """Remove the stored file when its row goes (also on cascades from child or account)."""
    field = instance.file if sender is Upload else instance.image
    if field:
        field.delete(save=False)
