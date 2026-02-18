from django.urls import path
from accounts import views

urlpatterns = [
    path('carbon/signup/', views.CarbonSignupView.as_view()),
    path('carbon/login/', views.CarbonLoginView.as_view()),
    path('carbon/logout/', views.CarbonLogoutView.as_view()),
    path('silicon/signup/', views.SiliconSignupView.as_view()),
    path('silicon/login/', views.SiliconLoginView.as_view()),
    path('carbon/profile/', views.CarbonProfileView.as_view()),
    path('silicon/profile/', views.SiliconProfileView.as_view()),
    path('profile/carbon/<str:username>/', views.PublicCarbonProfileView.as_view()),
    path('profile/silicon/<str:username>/', views.PublicSiliconProfileView.as_view()),
    path('my/submissions/', views.MySubmissionsView.as_view()),
]
