# =====================================================================
# Autor: Mihailo Mandić 2023/0613
# Vuk Bojović 2023/0283
# =====================================================================
import calendar
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import User

from .models import Transaction, Wallet

MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'Maj', 'Jun', 'Jul', 'Avg', 'Sep', 'Okt', 'Nov', 'Dec']


# pravi poadtke za poslednjih 6 meseci za grafik
def monthly_balance_history(wallet):
    today = timezone.localdate()
    year, month = today.year, today.month

    month_starts = []
    for _ in range(6):
        month_starts.append(date(year, month, 1))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    month_starts.reverse()

    history = []
    running_balance = Wallet.STARTING_BALANCE
    for index, month_start in enumerate(month_starts):
        if index + 1 < len(month_starts):
            month_end = month_starts[index + 1]
        else:
            last_day = calendar.monthrange(month_start.year, month_start.month)[1]
            month_end = date(month_start.year, month_start.month, last_day)

        last_tx = wallet.transactions.filter(created_at__date__lte=month_end).order_by('-created_at').first()
        if last_tx:
            running_balance = last_tx.new_balance

        history.append({'label': MONTH_LABELS[month_start.month - 1], 'balance': running_balance})

    max_balance = max((entry['balance'] for entry in history), default=0) or 1
    for entry in history:
        entry['percent'] = round(entry['balance'] / max_balance * 100)

    return history


@login_required
# prikazuje stranicu novcanika sa trenutinim stanjem i grafikom
def wallet_view(request):
    wallet = request.user.wallet

    context = {
        'wallet': wallet,
        'balance_history': monthly_balance_history(wallet),
    }
    return render(request, 'wallet/wallet.html', context)


@login_required
def transaction_history(request):
    """Kontroler za prikaz istorije svih transakcija korisnika.

    Dohvata transakcije novčanika prijavljenog korisnika i primenjuje opcione
    filtere iz GET parametara: tip transakcije, datum od i datum do.
    Vraća: render stranice sa listom transakcija (tip, opis, iznos, novo stanje,
    datum) i vrednostima filtera; pri grešci prikazuje poruku i praznu listu.
    Dostupno samo običnom korisniku.
    """
    if request.user.role != User.Role.USER:
        messages.error(request, 'Nemate prava za pristup ovoj stranici.')
        return redirect('accounts:profile')

    wallet = request.user.wallet
    transaction_items = []

    selected_type = request.GET.get('type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    try:
        transactions = wallet.transactions.order_by('-created_at')

        if selected_type.isdigit() and int(selected_type) in Transaction.Type.values:
            transactions = transactions.filter(type=int(selected_type))
        if date_from:
            transactions = transactions.filter(created_at__date__gte=date_from)
        if date_to:
            transactions = transactions.filter(created_at__date__lte=date_to)

        for transaction in transactions:
            transaction_items.append({
                'type_label': transaction.get_type_display(),
                'description': transaction.description,
                'amount': transaction.amount,
                'sign_class': 'positive' if transaction.amount >= 0 else 'negative',
                'created_at': transaction.created_at,
                'new_balance': transaction.new_balance,
            })
    except Exception:
        messages.error(request, 'Došlo je do greške prilikom učitavanja istorije transakcija.')
        transaction_items = []

    return render(request, 'wallet/transaction_history.html', {
        'balance': wallet.balance,
        'transaction_items': transaction_items,
        'type_choices': Transaction.Type.choices,
        'selected_type': selected_type,
        'date_from': date_from,
        'date_to': date_to,
    })
