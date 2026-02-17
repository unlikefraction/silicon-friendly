from django.contrib import admin
from accounts.models import Carbon, Silicon


@admin.register(Carbon)
class CarbonAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "is_active", "created_at")
    search_fields = ("username", "email")


@admin.register(Silicon)
class SiliconAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "is_active", "search_queries_remaining", "token_last_used", "created_at")
    search_fields = ("username", "email")
