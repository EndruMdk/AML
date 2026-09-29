from django.conf import settings
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=45, unique=True)
    followers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='interests', blank=True)

    def __str__(self):
        return self.name


class Event(models.Model):
    class Status(models.IntegerChoices):
        ACTIVE = 1, 'Active'
        CLOSED = 2, 'Closed for voting'
        RESOLVED = 3, 'Resolved'

    class Outcome(models.IntegerChoices):
        YES = 1, 'Yes'
        NO = 2, 'No'

    title = models.CharField(max_length=45)
    description = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='events')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_events')

    date_beg = models.DateTimeField()
    date_end = models.DateTimeField()

    odd_yes = models.DecimalField(max_digits=5, decimal_places=2)
    odd_no = models.DecimalField(max_digits=5, decimal_places=2)
    total_yes = models.IntegerField(default=0)
    total_no = models.IntegerField(default=0)

    status = models.IntegerField(choices=Status.choices, default=Status.ACTIVE)
    outcome = models.IntegerField(choices=Outcome.choices, null=True, blank=True)

    external_source_id = models.CharField(max_length=80, blank=True, null=True, unique=True)

    def __str__(self):
        return self.title


class OddsHistory(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='odds_history')
    odd_yes = models.DecimalField(max_digits=5, decimal_places=2)
    odd_no = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.event.title} @ {self.created_at:%Y-%m-%d %H:%M}'


class SuggestedEvent(models.Model):
    external_id = models.CharField(max_length=80, unique=True)
    source = models.CharField(max_length=45, default='Polymarket')
    url = models.URLField(blank=True)

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    suggested_category = models.CharField(max_length=45, blank=True)

    odd_yes = models.DecimalField(max_digits=5, decimal_places=2)
    odd_no = models.DecimalField(max_digits=5, decimal_places=2)
    suggested_deadline = models.DateTimeField(null=True, blank=True)

    fetched_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.title} ({self.source})'
