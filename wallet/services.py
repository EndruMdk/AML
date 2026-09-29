# Andrija Trnavcevic 2023/0242

from datetime import timedelta

from django.db import transaction as db_transaction
from django.utils import timezone

from .models import Transaction, Wallet


DAILY_BONUS_BASE = 20
DAILY_BONUS_STEP = 10
DAILY_BONUS_MAX = 100


# Opis: Dodeljuje dnevni login bonus korisniku, azurira streak i kreira transakciju bonusa.
# Povratna vrednost: Recnik sa iznosom bonusa i streak-om ili None ako je bonus vec dodeljen za danas.
def apply_daily_login_bonus(user):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    with db_transaction.atomic():
        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)

        if wallet.last_bonus_date == today:
            return None

        if wallet.last_bonus_date == yesterday:
            wallet.bonus_streak += 1
        else:
            wallet.bonus_streak = 1

        bonus_amount = min(
            DAILY_BONUS_MAX,
            DAILY_BONUS_BASE + (wallet.bonus_streak - 1) * DAILY_BONUS_STEP,
        )

        wallet.balance += bonus_amount
        wallet.last_bonus_date = today
        wallet.save(update_fields=['balance', 'last_bonus_date', 'bonus_streak'])

        Transaction.objects.create(
            wallet=wallet,
            amount=bonus_amount,
            type=Transaction.Type.BONUS,
            new_balance=wallet.balance,
            description=f'Daily login bonus - streak {wallet.bonus_streak}',
        )

    return {
        'amount': bonus_amount,
        'streak': wallet.bonus_streak,
    }
