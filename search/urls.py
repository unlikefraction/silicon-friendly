from django.urls import path
from search import views

urlpatterns = [
    path('semantic/', views.SemanticSearchView.as_view()),
    path('keyword/', views.KeywordSearchView.as_view()),
]
