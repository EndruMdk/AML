# Autor: Vuk Bojović 2023/0283
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from core.models import AuditLog

from .models import Category, Event, OddsHistory, SuggestedEvent
from .services import fetch_suggested_events


@login_required
# prikazuje arbitratoru listu predlozenih dogadjaja koje moze da obajvi
def create_event(request):
    if request.user.role != User.Role.ARBITRATOR:
        messages.error(request, 'Nemate prava za pristup ovoj stranici.')
        return redirect('accounts:profile')

    suggestions = SuggestedEvent.objects.all()
    return render(request, 'events/create_event.html', {'suggestions': suggestions})


@login_required
@require_POST
# povlaci nove predlgoe dogadjaja sa Polymarket-a
def refresh_suggestions(request):
    if request.user.role != User.Role.ARBITRATOR:
        messages.error(request, 'Nemate prava za pristup ovoj stranici.')
        return redirect('accounts:profile')

    try:
        created = fetch_suggested_events()
    except Exception:
        messages.error(request, 'Preuzimanje predloga nije uspelo. Pokušajte ponovo.')
    else:
        messages.success(request, f'Preuzeto je {created} novih predloga.')
    return redirect('events:create_event')


@login_required
# forma za kreiranje dogadjaja (proveri sve pre)
def event_form(request, suggested_id=None):
    if request.user.role != User.Role.ARBITRATOR:
        messages.error(request, 'Nemate prava za pristup ovoj stranici.')
        return redirect('accounts:profile')

    suggestion = None
    if suggested_id is not None:
        suggestion = SuggestedEvent.objects.filter(pk=suggested_id).first()
        if suggestion is None:
            messages.error(request, 'Predlog nije pronađen ili je već objavljen.')
            return redirect('events:create_event')

    categories = Category.objects.all().order_by('name')
    error_message = None
    form_data = {
        'title': suggestion.title[:45] if suggestion else '',
        'description': suggestion.description[:255] if suggestion else '',
        'category': '',
        'date_end': _format_local_datetime(suggestion.suggested_deadline) if suggestion else '',
        'odd_yes': suggestion.odd_yes if suggestion else '',
        'odd_no': suggestion.odd_no if suggestion else '',
    }

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        date_end_raw = request.POST.get('date_end', '').strip()
        odd_yes_raw = request.POST.get('odd_yes', '').strip()
        odd_no_raw = request.POST.get('odd_no', '').strip()

        form_data = {
            'title': title,
            'description': description,
            'category': category_id or '',
            'date_end': date_end_raw,
            'odd_yes': odd_yes_raw,
            'odd_no': odd_no_raw,
        }

        category = Category.objects.filter(pk=category_id).first() if category_id else None
        date_end = _parse_local_datetime(date_end_raw)
        odd_yes = _parse_decimal(odd_yes_raw)
        odd_no = _parse_decimal(odd_no_raw)

        if not all([title, description, category, date_end_raw, odd_yes_raw, odd_no_raw]):
            error_message = 'Nisu uneta sva obavezna polja.'
        elif len(title) > 45:
            error_message = 'Naziv događaja može imati najviše 45 karaktera.'
        elif date_end is None:
            error_message = 'Nevažeći format datuma i vremena.'
        elif odd_yes is None or odd_no is None or odd_yes <= 0 or odd_no <= 0:
            error_message = 'Kvote moraju biti pozitivni brojevi.'
        elif date_end <= timezone.now():
            error_message = 'Krajnji rok mora biti u budućnosti. Molimo unesite važeći datum i vreme.'
        else:
            with db_transaction.atomic():
                event = Event.objects.create(
                    title=title[:45],
                    description=description[:255],
                    category=category,
                    creator=request.user,
                    date_beg=timezone.now(),
                    date_end=date_end,
                    odd_yes=odd_yes,
                    odd_no=odd_no,
                    status=Event.Status.ACTIVE,
                    external_source_id=suggestion.external_id if suggestion else None,
                )
                OddsHistory.objects.create(event=event, odd_yes=odd_yes, odd_no=odd_no)
                AuditLog.objects.create(
                    actor=request.user,
                    action=AuditLog.Action.PUBLISH_EVENT,
                    description=f'Objavljen događaj: {event.title}',
                )
                if suggestion is not None:
                    suggestion.delete()

            messages.success(request, 'Događaj je uspešno objavljen.')
            return redirect('events:create_event')

    return render(request, 'events/event_form.html', {
        'suggestion': suggestion,
        'categories': categories,
        'error_message': error_message,
        'form_data': form_data,
    })


# konvertuje datum u datum format
def _parse_local_datetime(raw):
    if not raw:
        return None
    try:
        parsed = datetime.strptime(raw, '%Y-%m-%dT%H:%M')
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


# vraca datum nazad u tekst format
def _format_local_datetime(value):
    if not value:
        return ''
    local_value = timezone.localtime(value)
    return local_value.strftime('%Y-%m-%dT%H:%M')


# sigurno pretvara tekst u decimalni ako mzoe
def _parse_decimal(raw):
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None
