from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.IntegerChoices):
        USER = 1, 'User'
        ARBITRATOR = 2, 'Arbitrator'
        ADMIN = 3, 'Admin'

    role = models.IntegerField(choices=Role.choices, default=Role.USER)
    is_banned = models.BooleanField(default=False)

    def __str__(self):
        return self.username


class ArbitratorApplication(models.Model):
    class Status(models.IntegerChoices):
        PENDING = 1, 'Pending'
        ACCEPTED = 2, 'Accepted'
        REJECTED = 3, 'Rejected'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='arbitrator_application')
    cv = models.FileField(upload_to='cvs/')
    status = models.IntegerField(choices=Status.choices, default=Status.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.user.username} ({self.get_status_display()})'
