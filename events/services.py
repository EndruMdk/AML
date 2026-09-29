# Autor: Vuk Bojović 2023/0283
import json
import urllib.request
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.utils import timezone

from .models import Event, SuggestedEvent

POLYMARKET_EVENTS_URL = (
    'https://gamma-api.polymarket.com/events'
    '?limit={limit}&closed=false&active=true&order=volume24hr&ascending=false'
)

MAX_ODD = Decimal('999.99')


# skida nove Da/Ne dogadjaje sa Polymarket-a i cuva nove kao predlge
def fetch_suggested_events(limit=100):

    url = POLYMARKET_EVENTS_URL.format(limit=limit)
    request = urllib.request.Request(url, headers={'User-Agent': 'AML-VAMP/1.0'})
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode())

    now = timezone.now()
    SuggestedEvent.objects.filter(suggested_deadline__lte=now).delete()

    known_external_ids = set(SuggestedEvent.objects.values_list('external_id', flat=True))
    published_external_ids = set(
        Event.objects.exclude(external_source_id__isnull=True).values_list('external_source_id', flat=True)
    )

    created = 0

    for polymarket_event in payload:
        markets = polymarket_event.get('markets') or []
        if len(markets) != 1:
            continue
        market = markets[0]

        external_id = market.get('conditionId') or market.get('id')
        if not external_id or external_id in known_external_ids or external_id in published_external_ids:
            continue

        try:
            outcomes = json.loads(market.get('outcomes', '[]'))
            prices = json.loads(market.get('outcomePrices', '[]'))
        except (TypeError, ValueError):
            continue

        if outcomes != ['Yes', 'No'] or len(prices) != 2:
            continue

        try:
            price_yes = Decimal(prices[0])
            price_no = Decimal(prices[1])
        except (InvalidOperation, TypeError):
            continue

        deadline = _parse_datetime(market.get('endDate'))
        if deadline is not None and deadline <= now:
            continue

        title = (market.get('question') or polymarket_event.get('title') or '').strip()
        if not title:
            continue

        tags = [tag.get('label') for tag in polymarket_event.get('tags', []) if tag.get('label')]
        slug = market.get('slug') or polymarket_event.get('slug') or ''

        SuggestedEvent.objects.create(
            external_id=external_id,
            source='Polymarket',
            url=f'https://polymarket.com/event/{slug}' if slug else '',
            title=title[:255],
            description=(market.get('description') or '').strip(),
            suggested_category=(tags[0] if tags else '')[:45],
            odd_yes=_price_to_odd(price_yes),
            odd_no=_price_to_odd(price_no),
            suggested_deadline=deadline,
        )
        known_external_ids.add(external_id)
        created += 1

    return created


# pretvara Polymarket kvote Americke u nase
def _price_to_odd(price):
    if price <= 0:
        return MAX_ODD
    odd = (Decimal('1') / price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return min(odd, MAX_ODD)


# cita datum iz sa dogadjaja
def _parse_datetime(raw):
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.utc)
    return parsed
