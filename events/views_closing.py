# Autor: Vuk Bojović 2023/0283
from decimal import ROUND_HALF_UP, Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import User
from betting.models import Bet
from core.models import AuditLog
from wallet.models import Transaction

from .models import Event


@login_required
# prikazuje arbitratoru dogadjaje koji cekaju zatvaranje i automacki zatvara one kojima je isteklo vreme
def close_queue(request):
    if request.user.role != User.Role.ARBITRATOR:
        messages.error(request, 'Nemate prava za pristup ovoj stranici.')
        return redirect('accounts:profile')

    Event.objects.filter(
        status=Event.Status.ACTIVE, date_end__lte=timezone.now(),
    ).update(status=Event.Status.CLOSED)

    context = {
        'pending_events': Event.objects.filter(status=Event.Status.CLOSED).order_by('date_end'),
        'active_events': Event.objects.filter(status=Event.Status.ACTIVE).order_by('date_end'),
    }
    return render(request, 'events/close_queue.html', context)


@login_required
# prikazuje formu za zatvaranje jednog dogadjaja
def resolve_event(request, event_id):
    if request.user.role != User.Role.ARBITRATOR:
        messages.error(request, 'Nemate prava za pristup ovoj stranici.')
        return redirect('accounts:profile')

    event = Event.objects.filter(pk=event_id).exclude(status=Event.Status.RESOLVED).first()
    if event is None:
        messages.error(request, 'Događaj ne postoji ili je već zatvoren.')
        return redirect('events:close_queue')

    if request.method == 'POST':
        return _confirm_resolution(request, event)

    stats = Bet.objects.filter(event=event).aggregate(
        yes_count=Count('id', filter=Q(side=Bet.Side.YES)),
        no_count=Count('id', filter=Q(side=Bet.Side.NO)),
        yes_amount=Sum('amount', filter=Q(side=Bet.Side.YES)),
        no_amount=Sum('amount', filter=Q(side=Bet.Side.NO)),
    )
    yes_count = stats['yes_count'] or 0
    no_count = stats['no_count'] or 0

    context = {
        'event': event,
        'yes_count': yes_count,
        'no_count': no_count,
        'yes_amount': stats['yes_amount'] or 0,
        'no_amount': stats['no_amount'] or 0,
        'has_votes': bool(yes_count + no_count),
        'is_early_close': event.status == Event.Status.ACTIVE,
    }
    return render(request, 'events/resolve_event.html', context)


# zakljucava dogadjaj, bira pobednika i isplacuje sve koji su pogodili
def _confirm_resolution(request, event):
    outcome_param = request.POST.get('outcome')
    if outcome_param not in ('yes', 'no'):
        messages.error(request, 'Nevažeći izbor ishoda.')
        return redirect('events:resolve_event', event_id=event.id)

    outcome = Event.Outcome.YES if outcome_param == 'yes' else Event.Outcome.NO
    winning_side = Bet.Side.YES if outcome_param == 'yes' else Bet.Side.NO

    with db_transaction.atomic():
        locked_event = Event.objects.select_for_update().get(pk=event.id)
        if locked_event.status == Event.Status.RESOLVED:
            messages.error(request, 'Događaj je već zatvoren.')
            return redirect('events:close_queue')

        locked_event.status = Event.Status.RESOLVED
        locked_event.outcome = outcome
        locked_event.save(update_fields=['status', 'outcome'])

        pending_bets = Bet.objects.select_related('user__wallet').filter(
            event=locked_event, status=Bet.Status.PENDING,
        )

        for bet in pending_bets:
            if bet.side == winning_side:
                payout = int((Decimal(bet.amount) * bet.odd).to_integral_value(rounding=ROUND_HALF_UP))
                bet.status = Bet.Status.WON
                bet.save(update_fields=['status'])

                wallet = bet.user.wallet
                wallet.balance += payout
                wallet.save(update_fields=['balance'])

                Transaction.objects.create(
                    wallet=wallet,
                    amount=payout,
                    type=Transaction.Type.PAYOUT,
                    new_balance=wallet.balance,
                    description=f'Dobitak: {locked_event.title}'[:45],
                )
            else:
                bet.status = Bet.Status.LOST
                bet.save(update_fields=['status'])

        AuditLog.objects.create(
            actor=request.user,
            action=AuditLog.Action.CLOSE_EVENT,
            description=f'Zatvoren događaj: {locked_event.title}, ishod: {locked_event.get_outcome_display()}',
        )

    messages.success(request, 'Događaj je zatvoren i isplate su izvršene.')
    return redirect('events:close_queue')
