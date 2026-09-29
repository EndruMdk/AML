from django.conf import settings
from django.db import models

from events.models import Event


class Bet(models.Model):
    class Side(models.IntegerChoices):
        YES = 1, 'Yes'
        NO = 2, 'No'

    class Status(models.IntegerChoices):
        PENDING = 1, 'Pending'
        WON = 2, 'Won'
        LOST = 3, 'Lost'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bets')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='bets')
    amount = models.IntegerField()
    side = models.IntegerField(choices=Side.choices)
    odd = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.IntegerField(choices=Status.choices, default=Status.PENDING)
    placed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} - {self.event.title} ({self.get_side_display()})'
