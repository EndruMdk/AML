# Andrija Trnavcevic 2023/0242
# =====================================================================
# Autor: Mihailo Mandić 2023/0613
# =====================================================================
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import AuditLog
from wallet.services import apply_daily_login_bonus
from .models import ArbitratorApplication, User

def login(request):
    """Kontroler za logovanje korisnika.

    Na GET prikazuje formu za prijavu. Na POST proverava kredencijale i status
    naloga (banovan/neodobren) i, ako je sve ispravno, prijavljuje korisnika.
    Vraća: redirect na feed (običan korisnik) ili profil (arbitrator/admin) posle
    uspešne prijave; u suprotnom render login forme sa porukom o grešci.
    """
    error_message = None

    if request.user.is_authenticated:
        if request.user.role == User.Role.USER:
            return redirect('events:feed')
        return redirect('accounts:profile')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            error_message = 'Sva polja su obavezna.'
        else:
            user = User.objects.filter(username=username).first()
            if user is None:
                error_message = 'Ne postoji korisnik.'
            elif not user.check_password(password):
                error_message = 'Neispravna lozinka.'
            elif user.is_banned:
                error_message = 'Vaš nalog je deaktiviran.'
            elif not user.is_active:
                error_message = 'Vaš nalog još nije odobren od strane administratora.'
            else:
                auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                if user.role == User.Role.USER:
                    bonus = apply_daily_login_bonus(user)
                    if bonus is not None:
                        messages.success(
                            request,
                            f'Dobili ste daily bonus od {bonus["amount"]} AC.\n'
                            f'Streak: {bonus["streak"]} dana.',
                        )
                    return redirect('events:feed')
                return redirect('accounts:profile')

    return render(request, 'accounts/login.html', {
        'error_message': error_message,
    })


def logout(request):
    """Kontroler za odjavu korisnika.

    Poništava trenutnu sesiju korisnika.
    Vraća: redirect na login stranicu.
    """
    auth_logout(request)
    return redirect('accounts:login')


def password_reset(request):
    """Kontroler za promenu (reset) lozinke.

    Na GET prikazuje formu. Na POST proverava da uneti username i email pripadaju
    istom nalogu i, ako pripadaju, postavlja novu lozinku.
    Vraća: redirect na login posle uspešne promene; u suprotnom render forme sa
    porukom o grešci.
    """
    error_message = None

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        user = User.objects.filter(username=username).first()
        if user is None or user.email != email:
            error_message = 'Kredencijali su neispravni. Promena lozinke nije uspela.'
        else:
            user.set_password(password)
            user.save()
            messages.success(request, 'Lozinka je uspešno promenjena. Možete se prijaviti.')
            return redirect('accounts:login')

    return render(request, 'accounts/password_reset.html', {
        'error_message': error_message,
    })


# Opis: Prikazuje registracionu formu i kreira korisnicki ili arbitratorski nalog iz unetih podataka.
# Povratna vrednost: HttpResponse sa registracionom stranicom ili HttpResponseRedirect na login.
def register(request):
    error_message = None

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role')
        cv = request.FILES.get('cv')

        if User.objects.filter(username=username).exists():
            error_message = 'Korisnicko ime je vec zauzeto.'
        elif User.objects.filter(email=email).exists():
            error_message = 'Email je vec zauzet.'
        else:
            is_arbitrator = role == 'arbitrator'

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=User.Role.USER,
                is_active=not is_arbitrator,
            )

            if is_arbitrator:
                ArbitratorApplication.objects.create(
                    user=user,
                    cv=cv,
                    status=ArbitratorApplication.Status.PENDING,
                )
                messages.success(request, 'Nalog je kreiran i ceka odobrenje administratora.')
                return redirect('accounts:login')

            messages.success(request, 'Nalog je uspesno kreiran. Mozete se prijaviti.')
            return redirect('accounts:login')

    return render(request, 'accounts/register.html', {
        'error_message': error_message,
    })


@login_required
# Opis: Prikazuje profil trenutno ulogovanog korisnika sa menijem koji odgovara njegovoj ulozi.
# Povratna vrednost: HttpResponse sa profil stranicom.
def profile(request):
    if request.user.role == User.Role.ADMIN:
        role_label = 'Administrator'
        menu_items = [
            {'label': 'Statistika platforme', 'url': '/stats/'},
            {'label': 'Banovanje korisnika', 'url': '/ban/'},
            {'label': 'Upravljanje prijavama', 'url': '/accounts/arbitrator-applications/'},
            {'label': 'Promena balansa', 'url': '/balance/'},
            {'label': 'Logout', 'url': '/accounts/logout/'},
        ]
    elif request.user.role == User.Role.ARBITRATOR:
        role_label = 'Arbitrator'
        menu_items = [
            {'label': 'Kreiranje dogadjaja', 'url': '/events/create/'},
            {'label': 'Zatvaranje dogadjaja', 'url': '/events/close/'},
            {'label': 'Logout', 'url': '/accounts/logout/'},
        ]
    else:
        role_label = 'Korisnik'
        menu_items = [
            {'label': 'Feed', 'url': '/events/feed/'},
            {'label': 'Moja statistika', 'url': '/user-stats/'},
            {'label': 'Istorija glasanja', 'url': '/betting/history/'},
            {'label': 'Novcanik', 'url': '/wallet/'},
            {'label': 'Promena interesnih tema', 'url': '/events/interests/'},
            {'label': 'Logout', 'url': '/accounts/logout/'},
        ]

    return render(request, 'accounts/profile.html', {
        'role_label': role_label,
        'menu_items': menu_items,
    })


@login_required
# Opis: Prikazuje administratoru listu neobradjenih prijava za arbitratora.
# Povratna vrednost: HttpResponse sa stranicom prijava ili HttpResponseRedirect ako korisnik nije admin.
def arbitrator_applications(request):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, 'Nemate administratorska prava za pristup ovoj stranici.')
        return redirect('accounts:profile')

    applications = ArbitratorApplication.objects.filter(
        status=ArbitratorApplication.Status.PENDING,
    ).order_by('submitted_at')

    return render(request, 'accounts/arbitrator_applications.html', {
        'applications': applications,
    })


@login_required
@require_POST
# Opis: Odobrava izabranu prijavu za arbitratora i aktivira korisnikov arbitrator nalog.
# Povratna vrednost: JsonResponse sa rezultatom odobravanja prijave.
def approve_arbitrator_application(request, application_id):
    if request.user.role != User.Role.ADMIN:
        return JsonResponse({
            'ok': False,
            'error': 'Nemate administratorska prava za ovu akciju.',
        }, status=403)

    application = ArbitratorApplication.objects.filter(
        id=application_id,
        status=ArbitratorApplication.Status.PENDING,
    ).first()

    if application is None:
        return JsonResponse({
            'ok': False,
            'error': 'Prijava nije pronadjena ili je vec obradjena.',
        }, status=404)

    applicant = application.user
    applicant.role = User.Role.ARBITRATOR
    applicant.is_active = True
    applicant.save(update_fields=['role', 'is_active'])

    application.status = ArbitratorApplication.Status.ACCEPTED
    application.reviewed_by = request.user
    application.reviewed_at = timezone.now()
    application.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    AuditLog.objects.create(
        actor=request.user,
        action=AuditLog.Action.APPROVE_ARBITRATOR,
        target_user=applicant,
        description=f'Odobrena prijava za arbitratora: {applicant.username}',
    )

    return JsonResponse({
        'ok': True,
        'message': 'Prijava je odobrena.',
    })


@login_required
@require_POST
# Opis: Odbija izabranu prijavu za arbitratora i ostavlja korisnika bez arbitrator prava.
# Povratna vrednost: JsonResponse sa rezultatom odbijanja prijave.
def reject_arbitrator_application(request, application_id):
    if request.user.role != User.Role.ADMIN:
        return JsonResponse({
            'ok': False,
            'error': 'Nemate administratorska prava za ovu akciju.',
        }, status=403)

    application = ArbitratorApplication.objects.filter(
        id=application_id,
        status=ArbitratorApplication.Status.PENDING,
    ).first()

    if application is None:
        return JsonResponse({
            'ok': False,
            'error': 'Prijava nije pronadjena ili je vec obradjena.',
        }, status=404)

    applicant = application.user
    applicant.role = User.Role.USER
    applicant.is_active = False
    applicant.save(update_fields=['role', 'is_active'])

    application.status = ArbitratorApplication.Status.REJECTED
    application.reviewed_by = request.user
    application.reviewed_at = timezone.now()
    application.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    AuditLog.objects.create(
        actor=request.user,
        action=AuditLog.Action.REJECT_ARBITRATOR,
        target_user=applicant,
        description=f'Odbijena prijava za arbitratora: {applicant.username}',
    )

    return JsonResponse({
        'ok': True,
        'message': 'Prijava je odbijena.',
    })
