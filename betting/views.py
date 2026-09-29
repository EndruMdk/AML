# Andrija Trnavcevic 2023/0242

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.models import User
from .models import Bet

@login_required
# Opis: Prikazuje istoriju glasanja korisnika, razdvojenu na glasove u toku i zavrsene glasove.
# Povratna vrednost: HttpResponse sa stranicom istorije glasanja ili HttpResponseRedirect ako korisnik nema prava pristupa.
def vote_history(request):
    if request.user.role != User.Role.USER:
        messages.error(request, 'Nemate prava za pristup ovoj stranici.')
        return redirect('accounts:profile')

    pending_bets = Bet.objects.filter(
        user=request.user,
        status=Bet.Status.PENDING,
    ).order_by('-placed_at')

    finished_bets = Bet.objects.filter(
        user=request.user,
    ).exclude(
        status=Bet.Status.PENDING,
    ).order_by('-placed_at')

    bets = list(pending_bets) + list(finished_bets)
    history_items = []

    for bet in bets:
        if bet.status == Bet.Status.PENDING:
            status_label = 'U toku'
            status_class = 'history-badge--pending'
        elif bet.status == Bet.Status.WON:
            status_label = 'Gotov - tacno'
            status_class = 'history-badge--won'
        else:
            status_label = 'Gotov - netacno'
            status_class = 'history-badge--lost'

        history_items.append({
            'event_title': bet.event.title,
            'event_description': bet.event.description,
            'category_name': bet.event.category.name,
            'side': bet.get_side_display(),
            'amount': bet.amount,
            'odd': bet.odd,
            'placed_at': bet.placed_at,
            'status_label': status_label,
            'status_class': status_class,
        })

    return render(request, 'betting/vote_history.html', {
        'history_items': history_items,
    })
