# Andrija Trnavcevic 2023/0242
# Autor: Luka Pantovic 2023/0257
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.db import transaction as db_transaction
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import ArbitratorApplication, User
from betting.models import Bet
from events.models import Category, Event
from wallet.models import Transaction, Wallet

from .models import AuditLog


def _invalidate_sessions_for(user):
    """Briše sve aktivne sesije datog korisnika.

    Prolazi kroz sve sesije u bazi i uklanja one koje pripadaju datom
    korisniku, čime se on odmah izloguje sa svih uređaja. Koristi se
    prilikom banovanja korisnika.
    """
    for session in Session.objects.all():
        if session.get_decoded().get('_auth_user_id') == str(user.id):
            session.delete()


def _initials(user):
    """Vraća dva slova koja se prikazuju kao avatar korisnika.

    Ako korisnik ima uneto ime i prezime, koristi njihova prva slova.
    U suprotnom se oslanja na prva dva slova korisničkog imena.
    Vraća: string od dva velika slova.
    """
    if user.first_name and user.last_name:
        return (user.first_name[0] + user.last_name[0]).upper()
    return user.username[:2].upper()


@login_required
def stats(request):
    """Kontroler za prikaz administratorske statistike platforme.

    Prikuplja agregatne podatke o korisnicima, arbitratorima, događajima,
    glasovima i AuraCoins-ima, kao i raspodelu glasova po kategorijama.
    Vraća: HttpResponse sa stranicom statistike ili HttpResponseRedirect
    ako korisnik nema administratorska prava.
    """
    if request.user.role != User.Role.ADMIN:
        messages.error(request, 'Nemate administratorska prava za pristup ovoj stranici.')
        return redirect('events:feed')

    total_users = User.objects.count()
    banned_users = User.objects.filter(is_banned=True).count()

    total_arbitrators = ArbitratorApplication.objects.filter(
        status=ArbitratorApplication.Status.ACCEPTED).count()
    pending_arbitrators = ArbitratorApplication.objects.filter(
        status=ArbitratorApplication.Status.PENDING).count()

    total_events = Event.objects.count()
    active_events = Event.objects.filter(status=Event.Status.ACTIVE).count()

    total_votes = Bet.objects.count()
    total_auracoins = Wallet.objects.aggregate(total=Sum('balance'))['total'] or 0

    category_breakdown = []
    for category in Category.objects.annotate(vote_count=Count('events__bets')).filter(vote_count__gt=0):
        percent = round(category.vote_count / total_votes * 100) if total_votes else 0
        category_breakdown.append({'name': category.name, 'percent': percent})
    category_breakdown.sort(key=lambda c: c['percent'], reverse=True)

    context = {
        'total_users': total_users,
        'banned_users': banned_users,
        'total_arbitrators': total_arbitrators,
        'pending_arbitrators': pending_arbitrators,
        'total_events': total_events,
        'active_events': active_events,
        'total_votes': total_votes,
        'total_auracoins': total_auracoins,
        'category_breakdown': category_breakdown,
    }
    return render(request, 'core/stats.html', context)


@login_required
def ban(request):
    """Kontroler za prikaz liste korisnika i arbitratora za banovanje.

    Razdvaja arbitratore od običnih korisnika i omogućava pretragu po
    korisničkom imenu preko GET parametra `q`. Svakom prikazanom korisniku
    dodaje inicijale za avatar.
    Vraća: HttpResponse sa stranicom za banovanje ili HttpResponseRedirect
    ako korisnik nema administratorska prava.
    """
    if request.user.role != User.Role.ADMIN:
        messages.error(request, 'Nemate administratorska prava za pristup ovoj stranici.')
        return redirect('events:feed')

    query = request.GET.get('q', '').strip()

    arbitrator_ids = ArbitratorApplication.objects.filter(
        status=ArbitratorApplication.Status.ACCEPTED).values_list('user_id', flat=True)

    arbitrators = User.objects.filter(id__in=arbitrator_ids)
    regular_users = User.objects.filter(role=User.Role.USER)

    if query:
        arbitrators = arbitrators.filter(username__icontains=query)
        regular_users = regular_users.filter(username__icontains=query)

    for member in arbitrators:
        member.initials = _initials(member)
    for member in regular_users:
        member.initials = _initials(member)

    context = {
        'arbitrators': arbitrators,
        'regular_users': regular_users,
        'query': query,
    }
    return render(request, 'core/ban.html', context)


@login_required
@require_POST
def toggle_ban(request, user_id):
    """Kontroler za banovanje ili odbanovanje korisnika.

    Menja status `is_banned` ciljanog korisnika, invalidira mu sve aktivne
    sesije ako je banovan i beleži akciju u AuditLog. Administratorski
    nalozi ne mogu biti banovani.
    Vraća: HttpResponseRedirect nazad na stranicu za banovanje.
    """
    if request.user.role != User.Role.ADMIN:
        messages.error(request, 'Nemate administratorska prava za pristup ovoj stranici.')
        return redirect('events:feed')

    target = get_object_or_404(User, id=user_id)
    if target.role == User.Role.ADMIN:
        messages.error(request, 'Administratorski nalozi ne mogu biti banovani.')
        return redirect('core:ban')

    target.is_banned = not target.is_banned
    target.save(update_fields=['is_banned'])

    if target.is_banned:
        _invalidate_sessions_for(target)

    AuditLog.objects.create(
        actor=request.user,
        action=AuditLog.Action.BAN_USER if target.is_banned else AuditLog.Action.UNBAN_USER,
        target_user=target,
        description=f'{"Banovan" if target.is_banned else "Odbanovan"} korisnik {target.username}',
    )

    return redirect('core:ban')


@login_required
def balance_change(request):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, 'Nemate administratorska prava za pristup ovoj stranici.')
        return redirect('events:feed')

    query = request.GET.get('q', '').strip()

    members = User.objects.exclude(role=User.Role.ADMIN).select_related('wallet')
    if query:
        members = members.filter(username__icontains=query)

    for member in members:
        member.initials = _initials(member)

    context = {
        'members': members,
        'query': query,
    }
    return render(request, 'core/balance_change.html', context)


@login_required
def balance_change_form(request, user_id):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, 'Nemate administratorska prava za pristup ovoj stranici.')
        return redirect('events:feed')

    target = get_object_or_404(User, id=user_id)
    if target.role == User.Role.ADMIN:
        messages.error(request, 'Balans administratorskih naloga ne moze biti menjan.')
        return redirect('core:balance_change')

    error_message = None

    if request.method == 'POST':
        action = request.POST.get('action')
        reason = request.POST.get('reason', '').strip()

        try:
            amount = int(request.POST.get('amount', ''))
        except ValueError:
            amount = None

        if amount is None or amount <= 0:
            error_message = 'Unesite ispravnu kolicinu (ceo broj veci od 0).'
        elif action not in ('add', 'remove'):
            error_message = 'Nevazeca akcija.'
        elif not reason:
            error_message = 'Razlog korekcije je obavezan.'
        else:
            signed_amount = amount if action == 'add' else -amount

            with db_transaction.atomic():
                wallet = Wallet.objects.select_for_update().get(user=target)

                if action == 'remove' and amount > wallet.balance:
                    error_message = 'Korisnik nema dovoljno AuraCoins-a za oduzimanje.'
                else:
                    wallet.balance += signed_amount
                    wallet.save(update_fields=['balance'])

                    Transaction.objects.create(
                        wallet=wallet,
                        amount=signed_amount,
                        type=Transaction.Type.ADMIN_CORRECTION,
                        new_balance=wallet.balance,
                        description=f'Admin. korekcija: {reason}'[:45],
                    )

                    AuditLog.objects.create(
                        actor=request.user,
                        action=AuditLog.Action.BALANCE_CORRECTION,
                        target_user=target,
                        description=(
                            f'Promenjen balans korisnika {target.username} za {signed_amount:+d} AC. '
                            f'Razlog: {reason}'
                        ),
                    )

            if error_message is None:
                messages.success(request, 'Balans je uspesno promenjen.')
                return redirect('core:balance_change')

    return render(request, 'core/balance_change_form.html', {
        'target': target,
        'error_message': error_message,
    })


@login_required
# Opis: Racuna i prikazuje statistiku glasanja trenutno ulogovanog korisnika.
# Povratna vrednost: HttpResponse sa stranicom korisnicke statistike ili HttpResponseRedirect ako korisnik nema prava pristupa.
def user_stats(request):
    if request.user.role != User.Role.USER:
        messages.error(request, 'Nemate prava za pristup ovoj stranici.')
        return redirect('accounts:profile')

    finished_bets = Bet.objects.filter(
        user=request.user,
    ).exclude(
        status=Bet.Status.PENDING,
    )

    total_votes = 0
    hits = 0
    net_profit = 0.0

    for bet in finished_bets:
        total_votes += 1

        if bet.status == Bet.Status.WON:
            hits += 1
            net_profit += bet.amount * float(bet.odd) - bet.amount
        else:
            net_profit -= bet.amount

    misses = total_votes - hits
    success_rate = round(hits / total_votes * 100, 1) if total_votes else 0
    net_profit = round(net_profit, 2)
    is_profit = net_profit > 0
    is_loss = net_profit < 0

    context = {
        'total_votes': total_votes,
        'hits': hits,
        'misses': misses,
        'success_rate': success_rate,
        'net_profit': net_profit,
        'net_profit_display': f'{net_profit:.2f}',
        'net_profit_prefix': '+' if is_profit else '',
        'is_profit': is_profit,
        'is_loss': is_loss,
        'has_activity': total_votes > 0,
    }
    return render(request, 'core/user_stats.html', context)
