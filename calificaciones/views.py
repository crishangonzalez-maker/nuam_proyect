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
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .decorators import administrador_required, corredor_required, auditor_required, analista_required
from .forms import LoginForm, UsuarioForm
from django.views.decorators.csrf import csrf_protect

@login_required
@administrador_required
def eliminar_usuario(request, usuario_id):
    """Eliminar usuario existente"""
    if request.method == 'POST':
        try:
            usuario = get_object_or_404(Usuario, id=usuario_id)
            
            # Prevenir que el usuario se elimine a sí mismo
            if request.user.id == usuario.id:
                messages.error(request, 'No puedes eliminar tu propio usuario.')
                return redirect('gestion_usuarios')
            
            nombre_usuario = usuario.nombre
            usuario.delete()
            messages.success(request, f'Usuario "{nombre_usuario}" eliminado correctamente.')
            
        except Exception as e:
            messages.error(request, f'Error al eliminar el usuario: {str(e)}')

        
        return redirect('gestion_usuarios')
    
    # Si no es POST, redirigir a la gestión de usuarios
    return redirect('gestion_usuarios')

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

# 🔐 AQUÍ FALTABAN LOS DECORADORES - AHORA CORREGIDO:

@login_required
def lista_calificaciones(request):
    """Vista principal del mantenedor con filtros"""
    usuario_rol = request.user.rol
    if usuario_rol == "Administrador":
        calificaciones = CalificacionTributaria.objects.filter(estado=True)
    if usuario_rol == "Auditor":
        calificaciones = CalificacionTributaria.objects.filter(estado=True,usuario_creador_id=request.user.id)

    form_filtro = FiltroCalificacionesForm(request.GET or None)
    print(request.user.rol)
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

@login_required
@analista_required
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

@login_required
@analista_required
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

@login_required
@analista_required
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
                    usuario_creador=request.user.id,
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

@login_required
@administrador_required
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

@login_required
@analista_required
def editar_calificacion_paso1(request, id_calificacion):
    """Editar primer paso: Datos básicos"""
    calificacion = get_object_or_404(CalificacionTributaria, id_calificacion=id_calificacion)
    
    if request.method == 'POST':
        form = CalificacionTributariaForm(request.POST, instance=calificacion)
        if form.is_valid():
            # Guardar datos en sesión para el flujo de edición
            datos_serializables = convertir_fechas_para_sesion(form.cleaned_data)
            request.session['edicion_calificacion'] = id_calificacion
            request.session['calificacion_paso1'] = datos_serializables
            return redirect('editar_calificacion_paso2', id_calificacion=id_calificacion)
    else:
        form = CalificacionTributariaForm(instance=calificacion)
    
    context = {
        'form': form, 
        'paso_actual': 1,
        'calificacion': calificacion,
        'modo_edicion': True
    }
    return render(request, 'calificaciones/editar_paso1.html', context)

@login_required
@analista_required
def editar_calificacion_paso2(request, id_calificacion):
    """Editar segundo paso: Montos"""
    calificacion = get_object_or_404(CalificacionTributaria, id_calificacion=id_calificacion)
    
    # Verificar que estamos en flujo de edición
    if request.session.get('edicion_calificacion') != id_calificacion:
        messages.warning(request, 'Por favor complete primero los datos básicos.')
        return redirect('editar_calificacion_paso1', id_calificacion=id_calificacion)
    
    datos_paso1_serializados = request.session.get('calificacion_paso1')
    if not datos_paso1_serializados:
        messages.warning(request, 'Por favor complete primero los datos básicos.')
        return redirect('editar_calificacion_paso1', id_calificacion=id_calificacion)
    
    datos_paso1 = convertir_fechas_desde_sesion(datos_paso1_serializados)
    
    # En edición, normalmente los montos no se editan directamente, 
    # pero mostramos el form para consistencia
    if request.method == 'POST':
        form = MontosForm(request.POST)
        if form.is_valid():
            # Calcular factores (similar a creación)
            try:
                factores = form.calcular_factores()
            except AttributeError:
                montos_data = form.cleaned_data
                factores = {}
                for key, value in montos_data.items():
                    if key.startswith('monto') and not key.startswith('monto_base'):
                        base_key = f'monto_base{key[5:]}'
                        base_value = montos_data.get(base_key, Decimal('1'))
                        if base_value and base_value != Decimal('0'):
                            factor_key = f'factor{key[5:]}'
                            factores[factor_key] = value / base_value
            
            montos_serializables = convertir_fechas_para_sesion(form.cleaned_data)
            factores_serializables = convertir_fechas_para_sesion(factores)
            
            request.session['montos_paso2'] = montos_serializables
            request.session['factores_calculados'] = factores_serializables
            return redirect('editar_calificacion_paso3', id_calificacion=id_calificacion)
    else:
        # Podrías cargar montos existentes si los tienes
        form = MontosForm()
    
    context = {
        'form': form,
        'paso_actual': 2,
        'datos_paso1': datos_paso1,
        'calificacion': calificacion,
        'modo_edicion': True
    }
    return render(request, 'calificaciones/editar_paso2.html', context)

@login_required
@analista_required
def editar_calificacion_paso3(request, id_calificacion):
    """Editar tercer paso: Factores"""
    calificacion = get_object_or_404(CalificacionTributaria, id_calificacion=id_calificacion)
    factores_existentes = get_object_or_404(FactorCalificacion, id_calificacion=calificacion)
    
    # Verificar flujo de edición
    if request.session.get('edicion_calificacion') != id_calificacion:
        messages.warning(request, 'Por favor complete los pasos anteriores.')
        return redirect('editar_calificacion_paso1', id_calificacion=id_calificacion)
    
    datos_paso1_serializados = request.session.get('calificacion_paso1')
    factores_calculados_serializados = request.session.get('factores_calculados', {})
    
    if not datos_paso1_serializados:
        messages.warning(request, 'Por favor complete los pasos anteriores.')
        return redirect('editar_calificacion_paso1', id_calificacion=id_calificacion)
    
    datos_paso1 = convertir_fechas_desde_sesion(datos_paso1_serializados)
    factores_calculados = convertir_fechas_desde_sesion(factores_calculados_serializados)
    
    if request.method == 'POST':
        form = FactoresForm(request.POST, instance=factores_existentes)
        if form.is_valid():
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
                
                # Actualizar calificación tributaria
                for field, value in datos_paso1.items():
                    setattr(calificacion, field, value)
                calificacion.save()
                
                # Actualizar factores
                factores = form.save(commit=False)
                factores.id_calificacion = calificacion
                factores.save()
                
                # Log de auditoría
                LogAuditoria.objects.create(
                    accion='UPDATE',
                    usuario_responsable=usuario,
                    id_calificacion=calificacion,
                    detalle='Edición de calificación tributaria',
                    ip_origen=request.META.get('REMOTE_ADDR', '127.0.0.1')
                )
                
                # Limpiar sesión
                request.session.pop('edicion_calificacion', None)
                request.session.pop('calificacion_paso1', None)
                request.session.pop('montos_paso2', None)
                request.session.pop('factores_calculados', None)
                
                messages.success(request, '¡Calificación tributaria actualizada exitosamente!')
                return redirect('lista_calificaciones')
                
            except Exception as e:
                messages.error(request, f'Error al actualizar: {str(e)}')
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error en editar_calificacion_paso3: {str(e)}")
    
    else:
        # Usar factores existentes como initial data
        form = FactoresForm(instance=factores_existentes)
    
    context = {
        'form': form,
        'paso_actual': 3,
        'datos_paso1': datos_paso1,
        'calificacion': calificacion,
        'factores_calculados': factores_calculados,
        'modo_edicion': True
    }
    return render(request, 'calificaciones/editar_paso3.html', context)

@login_required
@auditor_required
def detalle_calificacion(request, id_calificacion):
    """Vista para mostrar todos los datos de una calificación"""
    calificacion = get_object_or_404(CalificacionTributaria, id_calificacion=id_calificacion)
    
    # Obtener factores
    try:
        factores = FactorCalificacion.objects.get(id_calificacion=calificacion)
    except FactorCalificacion.DoesNotExist:
        factores = None
        messages.warning(request, 'No se encontraron factores asociados a esta calificación.')
    
    # Obtener logs de auditoría relacionados - CORREGIDO: usar fecha_hora en lugar de fecha_accion
    logs = LogAuditoria.objects.filter(id_calificacion=calificacion).order_by('-fecha_hora')
    
    context = {
        'calificacion': calificacion,
        'factores': factores,
        'logs': logs,
    }
    return render(request, 'calificaciones/detalle.html', context)


def login_view(request):
    """Vista de login personalizada"""
    if request.user.is_authenticated:
        return redirect('lista_calificaciones')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            correo = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=correo, password=password)
            
            if user is not None and user.estado:
                login(request, user)
                messages.success(request, f'¡Bienvenido {user.nombre}!')
                
                # Redirección según rol
                next_url = request.GET.get('next', 'lista_calificaciones')
                return redirect(next_url)
            else:
                messages.error(request, 'Credenciales inválidas o usuario inactivo')
    else:
        form = LoginForm()
    
    return render(request, 'calificaciones/login.html', {'form': form})

@csrf_protect
def logout_view(request):
    """Vista de logout"""
    if request.method == 'POST':
        logout(request)
        messages.info(request, 'Has cerrado sesión exitosamente.')
        return redirect('login')
    else:
        # Si acceden por GET, también procesar el logout
        logout(request)
        messages.info(request, 'Has cerrado sesión exitosamente.')
        return redirect('login')

@login_required
def perfil_usuario(request):
    """Vista para que los usuarios vean y editen su perfil"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Tu contraseña fue actualizada exitosamente!')
            return redirect('perfil_usuario')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'calificaciones/perfil.html', {'form': form})

@login_required
@administrador_required
def gestion_usuarios(request):
    """Vista solo para administradores - gestión de usuarios"""
    usuarios = Usuario.objects.all()
    return render(request, 'calificaciones/gestion_usuarios.html', {'usuarios': usuarios})

@login_required
@administrador_required
def crear_usuario(request):
    """Crear nuevo usuario (solo administradores)"""
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            messages.success(request, f'Usuario {usuario.nombre} creado exitosamente')
            return redirect('gestion_usuarios')
    else:
        form = UsuarioForm()
    
    return render(request, 'calificaciones/crear_usuario.html', {'form': form})

@login_required
@auditor_required
def editar_usuario(request, user_id):
    """Editar usuario existente"""
    usuario = get_object_or_404(Usuario, id=user_id)
    
    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, f'Usuario {usuario.nombre} actualizado exitosamente')
            return redirect('gestion_usuarios')
    else:
        form = UsuarioForm(instance=usuario)
    
    return render(request, 'calificaciones/editar_usuario.html', {'form': form, 'usuario': usuario})