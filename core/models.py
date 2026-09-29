from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.IntegerChoices):
        BAN_USER = 1, 'Banned user'
        UNBAN_USER = 2, 'Unbanned user'
        APPROVE_ARBITRATOR = 3, 'Approved arbitrator application'
        REJECT_ARBITRATOR = 4, 'Rejected arbitrator application'
        BALANCE_CORRECTION = 5, 'Manual balance correction'
        PUBLISH_EVENT = 6, 'Published event'
        CLOSE_EVENT = 7, 'Closed event'

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    action = models.IntegerField(choices=Action.choices)
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.get_action_display()} by {self.actor} @ {self.created_at:%Y-%m-%d %H:%M}'
