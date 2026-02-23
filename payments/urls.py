from django.urls import path
from payments import views

urlpatterns = [
    path('dodo/create/', views.DodoCreateView.as_view()),
    path('dodo/webhook/', views.DodoWebhookView.as_view()),
    path('crypto/submit/', views.CryptoSubmitView.as_view()),
    path('crypto/verify/<str:tx_hash>/', views.CryptoVerifyView.as_view()),
    path('status/', views.PaymentStatusView.as_view()),
]
