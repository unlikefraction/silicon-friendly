from django.contrib import admin
from websites.models import Website, WebsiteVerification, Keyword


@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ("url", "name", "level", "verified", "is_my_website", "created_at")
    list_filter = ("verified", "is_my_website")
    search_fields = ("url", "name")


@admin.register(WebsiteVerification)
class WebsiteVerificationAdmin(admin.ModelAdmin):
    list_display = ("website", "verified_by_silicon", "verified_by_carbon", "is_trusted", "counted", "created_at")
    list_filter = ("is_trusted", "counted")


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("token",)
    search_fields = ("token",)
