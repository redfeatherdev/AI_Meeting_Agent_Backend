from django.contrib.auth.models import AbstractUser
from django.db import models
from authentication.models import CustomUser

# Create your models here.
class GoogleCredentials(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    email = models.EmailField()
    token = models.CharField(max_length=500)
    refresh_token = models.CharField(max_length=500)
    token_uri = models.CharField(max_length=500)
    client_id = models.CharField(max_length=500)
    client_secret = models.CharField(max_length=500)
    scopes = models.TextField()

class CalendarEvent(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('finished', 'Finished'),
        ('deleted', 'Deleted'),
    ]

    google_credentials = models.ForeignKey(
        'GoogleCredentials', 
        on_delete=models.CASCADE, 
        related_name='events', 
        null=True,  # Make it optional
        blank=True  # Allow it to be blank when manually adding events
    )
    event_id = models.CharField(max_length=500, blank=True, null=True)  # Make it optional
    summary = models.CharField(max_length=500)
    description = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=500, null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    organizer_email = models.EmailField(blank=True, null=True)  # Make it optional
    creator_email = models.EmailField(blank=True, null=True)    # Make it optional
    hangout_link = models.URLField(null=True, blank=True)
    conference_id = models.CharField(max_length=100, null=True, blank=True)
    conference_solution_name = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    orderId = models.CharField(max_length=50, null=True, blank=True)
    duration = models.IntegerField(null=True)
    vectorStoreId = models.CharField(max_length=100, null=True, blank=True)

    # class Meta:
    #     unique_together = ('google_credentials', 'event_id')

    def __str__(self):
        return self.summary
