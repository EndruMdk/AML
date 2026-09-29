from django.conf import settings
from django.db import models


class Wallet(models.Model):
    STARTING_BALANCE = 1000

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.IntegerField(default=STARTING_BALANCE)
    last_bonus_date = models.DateField(null=True, blank=True)
    bonus_streak = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username}'s wallet"


class Transaction(models.Model):
    class Type(models.IntegerChoices):
        STAKE = 1, 'Stake'
        PAYOUT = 2, 'Payout'
        BONUS = 3, 'Daily bonus'
        ADMIN_CORRECTION = 4, 'Administrator correction'

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.IntegerField()
    type = models.IntegerField(choices=Type.choices)
    description = models.CharField(max_length=45, blank=True)
    new_balance = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.wallet.user.username} - {self.get_type_display()} ({self.amount})'
