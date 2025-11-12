from django.shortcuts import render
from django.http import HttpResponse

def lista_calificaciones(request):
    return HttpResponse("¡Hola! Esta es la página principal del mantenedor de calificaciones tributarias de NUAM")