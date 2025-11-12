from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from .models import CalificacionTributaria, Usuario, FactorCalificacion, LogAuditoria, ArchivoCarga
from .forms import (
    CalificacionTributariaForm, MontosForm, FactoresForm, FiltroCalificacionesForm
)
from decimal import Decimal
from django.contrib.auth.hashers import make_password

def lista_calificaciones(request):
    """Vista principal del mantenedor con filtros"""
    calificaciones = CalificacionTributaria.objects.filter(estado=True)
    form_filtro = FiltroCalificacionesForm(request.GET or None)
    
    if form_filtro.is_valid():
        ejercicio = form_filtro.cleaned_data.get('ejercicio')
        mercado = form_filtro.cleaned_data.get('mercado')
        origen = form_filtro.cleaned_data.get('origen')
        instrumento = form_filtro.cleaned_data.get('instrumento')
        
        if ejercicio:
            calificaciones = calificaciones.filter(ejercicio=ejercicio)
        if mercado:
            calificaciones = calificaciones.filter(mercado=mercado)
        if origen:
            calificaciones = calificaciones.filter(origen=origen)
        if instrumento:
            calificaciones = calificaciones.filter(instrumento__icontains=instrumento)
    
    context = {
        'calificaciones': calificaciones,
        'form_filtro': form_filtro,
    }
    return render(request, 'calificaciones/lista.html', context)

def crear_calificacion_paso1(request):
    """Primer paso: Ingreso de datos básicos"""
    # Crear usuario por defecto si no existe
    if not Usuario.objects.exists():
        usuario_default = Usuario.objects.create(
            nombre="Usuario Sistema",
            correo="sistema@nuam.com",
            rol="Administrador",
            contraseña_hash=make_password("temp123"),
            estado=True
        )
    
    if request.method == 'POST':
        form = CalificacionTributariaForm(request.POST)
        if form.is_valid():
            # Guardar en sesión para el siguiente paso
            request.session['calificacion_paso1'] = form.cleaned_data
            return redirect('crear_calificacion_paso2')
    else:
        form = CalificacionTributariaForm()
    
    context = {'form': form, 'paso_actual': 1}
    return render(request, 'calificaciones/crear_paso1.html', context)

def crear_calificacion_paso2(request):
    """Segundo paso: Ingreso de montos"""
    # Verificar que vengamos del paso 1
    datos_paso1 = request.session.get('calificacion_paso1')
    if not datos_paso1:
        messages.warning(request, 'Por favor complete primero los datos básicos.')
        return redirect('crear_calificacion_paso1')
    
    if request.method == 'POST':
        form = MontosForm(request.POST)
        if form.is_valid():
            # Calcular factores automáticamente
            factores = form.calcular_factores()
            request.session['montos_paso2'] = form.cleaned_data
            request.session['factores_calculados'] = factores
            return redirect('crear_calificacion_paso3')
    else:
        form = MontosForm()
    
    context = {
        'form': form, 
        'paso_actual': 2,
        'datos_paso1': datos_paso1
    }
    return render(request, 'calificaciones/crear_paso2.html', context)

def crear_calificacion_paso3(request):
    """Tercer paso: Revisión y confirmación de factores"""
    datos_paso1 = request.session.get('calificacion_paso1')
    factores_calculados = request.session.get('factores_calculados', {})
    
    if not datos_paso1:
        messages.warning(request, 'Por favor complete los pasos anteriores.')
        return redirect('crear_calificacion_paso1')
    
    if request.method == 'POST':
        form = FactoresForm(request.POST)
        if form.is_valid():
            try:
                # Obtener usuario (usamos el primero por ahora)
                usuario = Usuario.objects.first()
                
                # Crear calificación tributaria
                calificacion = CalificacionTributaria(
                    usuario_creador=usuario,
                    **datos_paso1
                )
                calificacion.save()
                
                # Crear factores de calificación
                factores = form.save(commit=False)
                factores.id_calificacion = calificacion
                factores.save()
                
                # Crear log de auditoría
                LogAuditoria.objects.create(
                    accion='CREATE',
                    usuario_responsable=usuario,
                    id_calificacion=calificacion,
                    detalle='Creación manual de calificación tributaria',
                    ip_origen=request.META.get('REMOTE_ADDR', '127.0.0.1')
                )
                
                # Limpiar sesión
                request.session.pop('calificacion_paso1', None)
                request.session.pop('montos_paso2', None)
                request.session.pop('factores_calculados', None)
                
                messages.success(request, '¡Calificación tributaria creada exitosamente!')
                return redirect('lista_calificaciones')
                
            except Exception as e:
                messages.error(request, f'Error al guardar: {str(e)}')
    
    else:
        # Form inicial con factores calculados
        initial_data = factores_calculados
        form = FactoresForm(initial=initial_data)
    
    context = {
        'form': form,
        'paso_actual': 3,
        'datos_paso1': datos_paso1,
        'factores_calculados': factores_calculados
    }
    return render(request, 'calificaciones/crear_paso3.html', context)

def eliminar_calificacion(request, id_calificacion):
    """Eliminar calificación (marcar como inactiva)"""
    calificacion = get_object_or_404(CalificacionTributaria, id_calificacion=id_calificacion)
    
    if request.method == 'POST':
        try:
            usuario = Usuario.objects.first()
            calificacion.estado = False
            calificacion.save()
            
            # Log de eliminación
            LogAuditoria.objects.create(
                accion='DELETE',
                usuario_responsable=usuario,
                id_calificacion=calificacion,
                detalle='Eliminación de calificación tributaria',
                ip_origen=request.META.get('REMOTE_ADDR', '127.0.0.1')
            )
            
            messages.success(request, 'Calificación eliminada exitosamente.')
        except Exception as e:
            messages.error(request, f'Error al eliminar: {str(e)}')
    
    return redirect('lista_calificaciones')