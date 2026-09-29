# =====================================================================
# Autor: Mihailo Mandić 2023/0613
# =====================================================================
"""Dinamičko formiranje kvota (SSU: Dinamičke kvote).

Kvote se računaju iz uloženih AuraCoins po strani, ali stabilizovano: inicijalne
kvote su prior, a konstanta likvidnosti LIQUIDITY je inercija, pa svaki novi ulog
pomera kvotu za iznos ukupnog uloga — kako pool raste, promene se
prirodno smiruju. Formula je deterministička i čuva ulog.

Ne uvode se nova polja na modelu: ukupan ulog se sabira iz Bet zapisa, a polazne
(inicijalne) kvote se čuvaju kao najstariji OddsHistory zapis događaja.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

# Konstanta likvidnosti (inercija). Veće => blaže promene kvota.
# 1600 daje "blagu" promenu: ulog +100 na prazan događaj pomeri kvotu ~1.80 -> 1.71.
LIQUIDITY = 1600

MIN_ODD = Decimal('1.05')
MAX_ODD = Decimal('50.00')
_CENT = Decimal('0.01')


def _clamp(odd):
    """Zaokruži kvotu na dve decimale i ograniči je na opseg [MIN_ODD, MAX_ODD].

    Vraća: Decimal kvotu unutar dozvoljenih granica.
    """
    odd = odd.quantize(_CENT, rounding=ROUND_HALF_UP)
    if odd < MIN_ODD:
        return MIN_ODD
    if odd > MAX_ODD:
        return MAX_ODD
    return odd


def compute_odds(init_odd_yes, init_odd_no, stake_yes, stake_no):
    """Vrati (odd_yes, odd_no) kao Decimal, na osnovu prior kvota i uloga po strani."""
    init_yes = float(init_odd_yes)
    init_no = float(init_odd_no)

    oh_yes = 1.0 / init_yes
    oh_no = 1.0 / init_no
    overround = oh_yes + oh_no          # ulog (čuva se)
    p0_yes = oh_yes / overround         # fer prior verovatnoća za YES

    total = stake_yes + stake_no
    p_yes = (LIQUIDITY * p0_yes + stake_yes) / (LIQUIDITY + total)
    p_no = 1.0 - p_yes

    odd_yes = _clamp(Decimal(1.0 / (p_yes * overround)))
    odd_no = _clamp(Decimal(1.0 / (p_no * overround)))
    return odd_yes, odd_no


def event_stakes(event):
    """(stake_yes, stake_no) — ukupno uloženih AuraCoins po strani, iz Bet zapisa."""
    from betting.models import Bet

    rows = (
        Bet.objects
        .filter(event=event)
        .values('side')
        .annotate(total=Sum('amount'))
    )
    totals = {row['side']: (row['total'] or 0) for row in rows}
    return totals.get(Bet.Side.YES, 0), totals.get(Bet.Side.NO, 0)


def _prior_odds(event):
    """Polazne kvote događaja = najstariji OddsHistory zapis.

    Ako istorija ne postoji (prvi glas), trenutne kvote su inicijalne, pa ih
    snimimo kao polaznu tačku i vratimo njih.
    """
    from .models import OddsHistory

    first = event.odds_history.order_by('created_at', 'id').first()
    if first is None:
        first = OddsHistory.objects.create(
            event=event, odd_yes=event.odd_yes, odd_no=event.odd_no,
        )
    return first.odd_yes, first.odd_no


def apply_dynamic_odds(event):
    """Preračunaj kvote iz aktuelnih uloga, upiši ih na event i loguj u OddsHistory."""
    from .models import OddsHistory

    prior_yes, prior_no = _prior_odds(event)
    stake_yes, stake_no = event_stakes(event)

    new_yes, new_no = compute_odds(prior_yes, prior_no, stake_yes, stake_no)
    event.odd_yes = new_yes
    event.odd_no = new_no
    event.save(update_fields=['odd_yes', 'odd_no'])

    OddsHistory.objects.create(event=event, odd_yes=new_yes, odd_no=new_no)
    return new_yes, new_no