from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from .models import CalificacionTributaria, Usuario, FactorCalificacion, LogAuditoria, ArchivoCarga
from .forms import (
    CalificacionTributariaForm, MontosForm, FactoresForm, FiltroCalificacionesForm
)
from decimal import Decimal
from django.contrib.auth.hashers import make_password
import json
from datetime import date, datetime

class DateTimeEncoder(json.JSONEncoder):
    """Encoder personalizado para manejar fechas en JSON"""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)

def convertir_fechas_para_sesion(datos):
    """Convierte objetos date/datetime a strings para la sesión"""
    datos_serializables = {}
    for key, value in datos.items():
        if isinstance(value, (date, datetime)):
            datos_serializables[key] = value.isoformat()
        elif isinstance(value, Decimal):
            datos_serializables[key] = str(value)
        else:
            datos_serializables[key] = value
    return datos_serializables

def convertir_fechas_desde_sesion(datos):
    """Convierte strings de fecha de vuelta a objetos date"""
    datos_convertidos = {}
    for key, value in datos.items():
        if key in ['fecha_pago', 'fecha_emision', 'fecha_vencimiento'] and isinstance(value, str):
            try:
                datos_convertidos[key] = date.fromisoformat(value)
            except ValueError:
                datos_convertidos[key] = value
        elif isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
            try:
                datos_convertidos[key] = Decimal(value)
            except:
                datos_convertidos[key] = value
        else:
            datos_convertidos[key] = value
    return datos_convertidos

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
            # Convertir datos para la sesión (fechas a strings)
            datos_serializables = convertir_fechas_para_sesion(form.cleaned_data)
            
            # Guardar en sesión para el siguiente paso
            request.session['calificacion_paso1'] = datos_serializables
            return redirect('crear_calificacion_paso2')
    else:
        form = CalificacionTributariaForm()
    
    context = {'form': form, 'paso_actual': 1}
    return render(request, 'calificaciones/crear_paso1.html', context)

def crear_calificacion_paso2(request):
    """Segundo paso: Ingreso de montos"""
    # Verificar que vengamos del paso 1
    datos_paso1_serializados = request.session.get('calificacion_paso1')
    if not datos_paso1_serializados:
        messages.warning(request, 'Por favor complete primero los datos básicos.')
        return redirect('crear_calificacion_paso1')
    
    # Convertir datos de la sesión (strings a fechas)
    datos_paso1 = convertir_fechas_desde_sesion(datos_paso1_serializados)
    
    if request.method == 'POST':
        form = MontosForm(request.POST)
        if form.is_valid():
            # Calcular factores automáticamente
            try:
                factores = form.calcular_factores()
            except AttributeError:
                # Si el método calcular_factores no existe en el form, calcular manualmente
                montos_data = form.cleaned_data
                factores = {}
                # Calcular factores básicos basados en los montos
                for key, value in montos_data.items():
                    if key.startswith('monto') and not key.startswith('monto_base'):
                        base_key = f'monto_base{key[5:]}'  # Extraer número del monto
                        base_value = montos_data.get(base_key, Decimal('1'))
                        if base_value and base_value != Decimal('0'):
                            factor_key = f'factor{key[5:]}'  # factor1, factor2, etc.
                            factores[factor_key] = value / base_value
            
            # CORRECCIÓN: Asegurar que todos los valores en factores sean serializables
            factores_serializables = {}
            for key, value in factores.items():
                if isinstance(value, Decimal):
                    factores_serializables[key] = str(value)
                else:
                    factores_serializables[key] = value
            
            # Convertir montos para sesión
            montos_serializables = convertir_fechas_para_sesion(form.cleaned_data)
            
            request.session['montos_paso2'] = montos_serializables
            request.session['factores_calculados'] = factores_serializables
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
    datos_paso1_serializados = request.session.get('calificacion_paso1')
    montos_paso2_serializados = request.session.get('montos_paso2', {})
    factores_calculados_serializados = request.session.get('factores_calculados', {})
    
    if not datos_paso1_serializados:
        messages.warning(request, 'Por favor complete los pasos anteriores.')
        return redirect('crear_calificacion_paso1')
    
    # Convertir datos de la sesión
    datos_paso1 = convertir_fechas_desde_sesion(datos_paso1_serializados)
    montos_paso2 = convertir_fechas_desde_sesion(montos_paso2_serializados)
    factores_calculados = convertir_fechas_desde_sesion(factores_calculados_serializados)
    
    if request.method == 'POST':
        form = FactoresForm(request.POST)
        if form.is_valid():
            try:
                # Verificar si ya existe una calificación con los mismos datos únicos
                existe_calificacion = CalificacionTributaria.objects.filter(
                    ejercicio=datos_paso1['ejercicio'],
                    mercado=datos_paso1['mercado'],
                    instrumento=datos_paso1['instrumento'],
                    secuencia_evento=datos_paso1['secuencia_evento'],
                    estado=True
                ).exists()
                
                if existe_calificacion:
                    messages.error(
                        request, 
                        f'Ya existe una calificación con los mismos datos: '
                        f'Ejercicio {datos_paso1["ejercicio"]}, '
                        f'Mercado {datos_paso1["mercado"]}, '
                        f'Instrumento {datos_paso1["instrumento"]}, '
                        f'Secuencia {datos_paso1["secuencia_evento"]}. '
                        f'Por favor modifique los datos básicos.'
                    )
                    return redirect('crear_calificacion_paso1')
                
                # Obtener usuario
                usuario = Usuario.objects.first()
                if not usuario:
                    usuario = Usuario.objects.create(
                        nombre="Usuario Sistema",
                        correo="sistema@nuam.com",
                        rol="Administrador",
                        contraseña_hash=make_password("temp123"),
                        estado=True
                    )
                
                # Crear calificación tributaria
                calificacion = CalificacionTributaria(
                    usuario_creador=usuario,
                    **datos_paso1
                )
                calificacion.save()
                
                # Crear factores de calificación - solo los campos del modelo
                factores_data = form.cleaned_data
                # Asegurarse de que no hay campos extra
                campos_modelo = [f.name for f in FactorCalificacion._meta.get_fields()]
                factores_filtrados = {k: v for k, v in factores_data.items() if k in campos_modelo}
                
                factores = FactorCalificacion(
                    id_calificacion=calificacion,
                    **factores_filtrados
                )
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
                if 'calificacion_paso1' in request.session:
                    del request.session['calificacion_paso1']
                if 'montos_paso2' in request.session:
                    del request.session['montos_paso2']
                if 'factores_calculados' in request.session:
                    del request.session['factores_calculados']
                
                messages.success(request, '¡Calificación tributaria creada exitosamente!')
                return redirect('lista_calificaciones')
                
            except Exception as e:
                messages.error(request, f'Error al guardar: {str(e)}')
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error en crear_calificacion_paso3: {str(e)}")
    
    else:
        # Form inicial con factores calculados
        form = FactoresForm(initial=factores_calculados)
    
    context = {
        'form': form,
        'paso_actual': 3,
        'datos_paso1': datos_paso1,
        'montos_paso2': montos_paso2,
        'factores_calculados': factores_calculados
    }
    return render(request, 'calificaciones/crear_paso3.html', context)

def eliminar_calificacion(request, id_calificacion):
    """Eliminar calificación (marcar como inactiva)"""
    calificacion = get_object_or_404(CalificacionTributaria, id_calificacion=id_calificacion)
    
    if request.method == 'POST':
        try:
            usuario = Usuario.objects.first()
            if not usuario:
                usuario = Usuario.objects.create(
                    nombre="Usuario Sistema",
                    correo="sistema@nuam.com",
                    rol="Administrador",
                    contraseña_hash=make_password("temp123"),
                    estado=True
                )
                
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