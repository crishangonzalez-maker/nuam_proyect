from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_calificaciones, name='lista_calificaciones'),
]