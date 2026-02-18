from django.urls import path
from chat import views

urlpatterns = [
    path('send/', views.ChatSendView.as_view()),
    path('', views.ChatListView.as_view()),
]
