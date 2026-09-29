# =====================================================================
# Autor: Luka Pantovic 2023/0257
# Mihailo Mandić 2023/0613
# =====================================================================
import logging
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from betting.models import Bet
from wallet.models import Transaction

from .models import Category, Event
from .odds import apply_dynamic_odds, event_stakes

logger = logging.getLogger(__name__)


def feed(request):
    """Kontroler za glavni feed događaja.

    Na GET prikazuje jedan događaj u swipe-stilu: ako je pretraga aktivna
    (parametri `q`/`category`), listu filtrira po naslovu/opisu i kategoriji;
    inače prijavljenom korisniku prikazuje događaje iz njegovih interesnih
    kategorija na kojima još nije glasao, a gostu sve aktivne događaje.
    Pozicija u listi se čuva kroz GET parametar `i`. Na POST prosleđuje
    zahtev na `_place_vote`.
    Vraća: HttpResponse sa feed stranicom.
    """
    if request.user.is_authenticated and request.user.role != User.Role.USER:
        messages.error(request, 'Nemate prava za pristup ovoj stranici.')
        return redirect('accounts:profile')

    if request.method == 'POST':
        return _place_vote(request)

    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    if category_id and not category_id.isdigit():
        category_id = ''
    search_active = 'q' in request.GET or bool(category_id)

    if search_active and not query and not category_id:
        messages.error(request, 'Niste uneli kriterijume pretrage.')
        search_active = False

    if search_active:
        events = Event.objects.filter(status=Event.Status.ACTIVE)
        if query:
            events = events.filter(Q(title__icontains=query) | Q(description__icontains=query))
        if category_id:
            events = events.filter(category_id=category_id)
        events = list(events.order_by('date_end'))
    elif request.user.is_authenticated:
        events = Event.objects.filter(status=Event.Status.ACTIVE)
        categories = request.user.interests.all()
        if categories.exists():
            events = events.filter(category__in=categories).order_by('date_end')
        else:
            events = events.order_by('date_end')
        events = list(events.exclude(bets__user=request.user))
    else:
        events = list(Event.objects.filter(status=Event.Status.ACTIVE).order_by('date_end'))

    total = len(events)

    try:
        index = int(request.GET.get('i', 0))
    except ValueError:
        index = 0
    index = max(index, 0)

    event = events[index] if 0 <= index < total else None
    extra_params = _search_query_string(query, category_id)

    context = {
        'categories': Category.objects.all(),
        'event': _event_context(event, index, total) if event else None,
        'query': query,
        'category_id': category_id,
        'no_results': search_active and total == 0,
        'extra_params': extra_params,
    }
    return render(request, 'events/feed.html', context)


def _search_query_string(query, category_id):
    """Gradi URL query string koji čuva aktivnu pretragu kroz navigaciju feed-a.

    Od zadatih vrednosti `query` i `category_id` pravi encoded parametre
    koji se dodaju na linkove za sledeći/prethodni događaj u feed-u.
    Vraća: string oblika '&q=...&category=...' ili prazan string ako
    pretraga nije aktivna.
    """
    params = {}
    if query:
        params['q'] = query
    if category_id:
        params['category'] = category_id
    return ('&' + urlencode(params)) if params else ''


@login_required
def interests(request):
    """Kontroler za promenu interesnih tema korisnika.

    Na GET prikazuje sve kategorije sa označenim temama koje korisnik već prati.
    Na POST čuva izabrane teme (menja `user.interests`), što utiče na feed događaja.
    Vraća: render forme sa temama (GET) ili redirect nazad na istu stranicu posle
    čuvanja (POST), uz poruku o uspehu/grešci. Dostupno samo običnom korisniku.
    """
    if request.user.role != User.Role.USER:
        messages.error(request, 'Nemate prava za pristup ovoj stranici.')
        return redirect('accounts:profile')

    if request.method == 'POST':
        selected = Category.objects.filter(id__in=request.POST.getlist('categories'))
        try:
            request.user.interests.set(selected)
        except Exception:
            messages.error(request, 'Došlo je do greške prilikom čuvanja. Pokušajte ponovo.')
        else:
            messages.success(request, 'Interesne teme su sačuvane.')
        return redirect('events:interests')

    categories = Category.objects.all().order_by('name')
    followed_ids = set(request.user.interests.values_list('id', flat=True))

    return render(request, 'events/interests.html', {
        'categories': categories,
        'followed_ids': followed_ids,
    })


def _place_vote(request):
    """Obrađuje glasanje korisnika na događaju sa feed-a.

    Validira prijavljenost korisnika, postojanje i status događaja, izbor
    strane i uneti iznos, kao i dovoljnost stanja u novčaniku. Ako je sve
    ispravno, u jednoj transakciji kreira opkladu, skida sredstva sa
    novčanika, evidentira transakciju, ažurira brojače glasova na događaju
    i preračunava dinamičke kvote.
    Vraća: HttpResponseRedirect nazad na feed, na poziciju sledećeg događaja.
    """
    next_index = request.POST.get('next_index', 0)
    side_param = request.POST.get('side')
    query = request.POST.get('q', '').strip()
    category_id = request.POST.get('category', '').strip()
    redirect_url = f"{reverse('events:feed')}?i={next_index}{_search_query_string(query, category_id)}"

    if not request.user.is_authenticated:
        messages.error(request, 'Morate biti prijavljeni da biste glasali.')
        return redirect(f"{reverse('accounts:login')}?next={reverse('events:feed')}")

    event = Event.objects.filter(pk=request.POST.get('event_id')).first()
    if event is None:
        messages.error(request, 'Događaj ne postoji.')
        return redirect(redirect_url)

    if event.status != Event.Status.ACTIVE or event.date_end <= timezone.now():
        messages.error(request, 'Glasanje za ovaj događaj je zatvoreno.')
        return redirect(redirect_url)

    if side_param not in ('yes', 'no'):
        messages.error(request, 'Nevažeći izbor.')
        return redirect(redirect_url)

    try:
        amount = int(request.POST.get('amount', ''))
    except ValueError:
        amount = 0
    if amount <= 0:
        messages.error(request, 'Unesite validan iznos.')
        return redirect(redirect_url)

    wallet = request.user.wallet
    if wallet.balance < amount:
        messages.error(request, 'Nemate dovoljno AuraCoins.')
        return redirect(redirect_url)

    side = Bet.Side.YES if side_param == 'yes' else Bet.Side.NO
    odd = event.odd_yes if side_param == 'yes' else event.odd_no

    with db_transaction.atomic():
        Bet.objects.create(user=request.user, event=event, amount=amount, side=side, odd=odd)

        wallet.balance -= amount
        wallet.save()
        Transaction.objects.create(
            wallet=wallet,
            amount=-amount,
            type=Transaction.Type.STAKE,
            new_balance=wallet.balance,
            description=f'Opklada: {event.title}'[:45],
        )

        if side == Bet.Side.YES:
            event.total_yes += 1
        else:
            event.total_no += 1
        event.save()

        try:
            apply_dynamic_odds(event)
        except Exception:
            logger.exception('Neuspešno ažuriranje kvota za događaj %s', event.pk)

    messages.success(request, 'Glas je zabeležen.')
    return redirect(redirect_url)


def _event_context(event, index, total):
    """Priprema podatke o jednom događaju za prikaz u feed-u.

    Računa procenat uloga na 'da'/'ne' stranu preko `event_stakes`, kao i
    preostalo vreme do kraja događaja formatirano u danima/satima/minutima.
    Vraća: rečnik sa podacima o događaju spremnim za template.
    """
    next_index = index + 1
    stake_yes, stake_no = event_stakes(event)
    stake_total = stake_yes + stake_no
    yes_percent = round(stake_yes / stake_total * 100) if stake_total else 50
    no_percent = 100 - yes_percent

    time_left = event.date_end - timezone.now()
    days, remainder = divmod(max(time_left.total_seconds(), 0), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60

    return {
        'id': event.id,
        'index': index + 1,
        'total': total,
        'dot_range': range(total),
        'next_index': next_index,
        'title': event.title,
        'description': event.description,
        'category': event.category,
        'time_left': f'{int(days)}d {int(hours)}h {int(minutes)}min',
        'yes_percent': yes_percent,
        'no_percent': no_percent,
        'yes_odds': event.odd_yes,
        'no_odds': event.odd_no,
    }
