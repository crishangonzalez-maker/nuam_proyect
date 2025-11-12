from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_calificaciones, name='lista_calificaciones'),
    path('crear/paso1/', views.crear_calificacion_paso1, name='crear_calificacion_paso1'),
    path('crear/paso2/', views.crear_calificacion_paso2, name='crear_calificacion_paso2'),
    path('crear/paso3/', views.crear_calificacion_paso3, name='crear_calificacion_paso3'),
    path('eliminar/<int:id_calificacion>/', views.eliminar_calificacion, name='eliminar_calificacion'),
]