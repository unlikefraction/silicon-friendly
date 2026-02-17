from django.urls import path
from websites import views

urlpatterns = [
    path('', views.WebsiteListView.as_view()),
    path('submit/', views.WebsiteSubmitView.as_view()),
    path('verify-queue/', views.VerifyQueueView.as_view()),
    path('<str:domain>/', views.WebsiteDetailView.as_view()),
    path('<str:domain>/verify/', views.WebsiteVerifyView.as_view()),
    path('<str:domain>/usage-report/', views.WebsiteUsageReportView.as_view()),
    path('<str:domain>/analytics/', views.WebsiteAnalyticsView.as_view()),
]
