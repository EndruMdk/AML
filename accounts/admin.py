from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import ArbitratorApplication, User


class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (None, {'fields': ('role', 'is_banned')}),
    )


admin.site.register(User, UserAdmin)
admin.site.register(ArbitratorApplication)
