from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import CalificacionTributaria, Usuario, FactorCalificacion, LogAuditoria, ArchivoCarga
from .forms import (
    CalificacionTributariaForm, MontosForm, FactoresForm, FiltroCalificacionesForm,
    LoginForm, UsuarioForm, MfaVerifyForm, MfaSetupForm  # AÑADIR LOS NUEVOS FORMULARIOS
)
from decimal import Decimal
from django.contrib.auth.hashers import make_password
import json
from datetime import date, datetime
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .decorators import administrador_required, analista_required, auditor_required, corredor_required, solo_lectura_required, editor_required
from django.db.models import Count
from django.views.decorators.csrf import csrf_protect

# MFA IMPORTS
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp import login as otp_login
from django.contrib.auth import login as auth_login
import base64
import pyotp
import qrcode
from io import BytesIO
import urllib.parse

import pandas as pd
import chardet
from datetime import datetime
from django.core.files.storage import FileSystemStorage
import os
from decimal import Decimal

# Asegúrate de que esta importación esté presente:
from .forms import (
    CalificacionTributariaForm, MontosForm, FactoresForm, FiltroCalificacionesForm,
    LoginForm, UsuarioForm, MfaVerifyForm, MfaSetupForm, CargaMasivaForm  # ← AÑADIR CargaMasivaForm aquí
)

# ... el resto de tu código de views.py ...
@login_required
@editor_required
def carga_masiva(request):
    """Vista para carga masiva de calificaciones desde archivo"""
    if request.method == 'POST':
        form = CargaMasivaForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']
            tipo_carga = form.cleaned_data['tipo_carga']
            sobrescribir = form.cleaned_data['sobrescribir']
            
            try:
                resultados = procesar_archivo_carga(archivo, tipo_carga, sobrescribir, request.user)
                
                # Crear registro en ArchivoCarga
                archivo_carga = ArchivoCarga.objects.create(
                    nombre_archivo=archivo.name,
                    tipo_archivo='CSV_FACTORES' if tipo_carga == 'factores' else 'DJ1948',
                    usuario_carga=request.user,
                    estado_proceso='PROCESADO',
                    registros_procesados=resultados['procesados'],
                    registros_error=resultados['errores'],
                    errores_detalle=resultados.get('errores_detalle', '')
                )
                
                # Log de auditoría
                LogAuditoria.objects.create(
                    accion='CARGA_MASIVA',
                    usuario_responsable=request.user,
                    detalle=f'Carga masiva: {resultados["procesados"]} procesados, {resultados["errores"]} errores',
                    ip_origen=request.META.get('REMOTE_ADDR', '127.0.0.1')
                )
                
                messages.success(
                    request, 
                    f'✅ Carga masiva completada: {resultados["procesados"]} registros procesados, {resultados["errores"]} errores'
                )
                
                if resultados.get('errores_detalle'):
                    messages.warning(request, f'Algunos registros tuvieron errores: {resultados["errores_detalle"]}')
                
                return redirect('lista_calificaciones')
                
            except Exception as e:
                messages.error(request, f'❌ Error al procesar archivo: {str(e)}')
                # Crear registro de error en ArchivoCarga
                ArchivoCarga.objects.create(
                    nombre_archivo=archivo.name,
                    tipo_archivo='CSV_FACTORES' if tipo_carga == 'factores' else 'DJ1948',
                    usuario_carga=request.user,
                    estado_proceso='ERROR',
                    errores_detalle=str(e)
                )
    else:
        form = CargaMasivaForm()
    
    context = {
        'form': form,
        'titulo': 'Carga Masiva de Calificaciones'
    }
    return render(request, 'calificaciones/carga_masiva.html', context)

# views.py - Reemplazar las funciones procesar_archivo_carga y procesar_fila_factores

def detectar_encoding(archivo):
    """Detecta el encoding del archivo de manera más robusta"""
    # Leer una muestra del archivo para detectar encoding
    raw_data = archivo.read(10000)
    archivo.seek(0)  # Reset file pointer
    
    # Intentar detectar encoding
    deteccion = chardet.detect(raw_data)
    encoding_detectado = deteccion['encoding']
    confianza = deteccion['confidence']
    
    print(f"Encoding detectado: {encoding_detectado} con confianza: {confianza}")
    
    # Si la confianza es baja o no se detecta, probar encodings comunes
    if not encoding_detectado or confianza < 0.7:
        encodings_a_probar = ['latin-1', 'cp1252', 'iso-8859-1', 'utf-8']
        for enc in encodings_a_probar:
            try:
                archivo.seek(0)
                raw_data.decode(enc)
                print(f"Encoding válido encontrado: {enc}")
                return enc
            except UnicodeDecodeError:
                continue
    
    return encoding_detectado or 'latin-1'

def procesar_archivo_carga(archivo, tipo_carga, sobrescribir, usuario):
    """Procesa el archivo de carga y crea/actualiza las calificaciones"""
    resultados = {
        'procesados': 0,
        'errores': 0,
        'errores_detalle': []
    }
    
    try:
        # Detectar encoding y leer archivo
        if archivo.name.endswith('.csv'):
            encoding = detectar_encoding(archivo)
            print(f"Usando encoding: {encoding} para el archivo CSV")
            
            # Leer CSV con encoding detectado
            try:
                df = pd.read_csv(archivo, encoding=encoding, dtype=str)
            except UnicodeDecodeError:
                # Si falla, intentar con otros encodings
                for enc in ['latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        archivo.seek(0)
                        df = pd.read_csv(archivo, encoding=enc, dtype=str)
                        print(f"CSV leído exitosamente con encoding: {enc}")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise Exception("No se pudo leer el archivo CSV con ningún encoding compatible")
        else:
            # Leer Excel
            df = pd.read_excel(archivo, dtype=str)
            print("Archivo Excel leído exitosamente")
        
        # Verificar que el DataFrame no esté vacío
        if df.empty:
            raise Exception("El archivo está vacío o no contiene datos")
        
        print(f"Archivo procesado: {len(df)} filas encontradas")
        
        # Reemplazar NaN con None y espacios en blanco
        df = df.replace({pd.NA: None, '': None})
        df = df.where(pd.notnull(df), None)
        
        # Normalizar nombres de columnas (eliminar espacios extras)
        df.columns = df.columns.str.strip()
        
        # Procesar cada fila
        for index, fila in df.iterrows():
            try:
                if tipo_carga == 'factores':
                    procesado = procesar_fila_factores(fila, sobrescribir, usuario)
                else:
                    procesado = procesar_fila_montos(fila, sobrescribir, usuario)
                
                if procesado:
                    resultados['procesados'] += 1
                else:
                    resultados['errores'] += 1
                    resultados['errores_detalle'].append(f"Fila {index + 2}: Registro existente omitido")
                    
            except Exception as e:
                resultados['errores'] += 1
                error_msg = f"Fila {index + 2}: {str(e)}"
                resultados['errores_detalle'].append(error_msg)
                print(f"Error en fila {index + 2}: {e}")
        
        # Limitar el detalle de errores para no sobrecargar
        if len(resultados['errores_detalle']) > 10:
            resultados['errores_detalle'] = resultados['errores_detalle'][:10] + ['... más errores']
        
        resultados['errores_detalle'] = '; '.join(resultados['errores_detalle'])
        
        print(f"Procesamiento completado: {resultados['procesados']} exitosos, {resultados['errores']} errores")
        
    except Exception as e:
        print(f"Error general al procesar archivo: {e}")
        raise Exception(f"Error al leer archivo: {str(e)}")
    
    return resultados

def procesar_fila_factores(fila, sobrescribir, usuario):
    """Procesa una fila con factores ya calculados"""
    print(f"Procesando fila: {fila.to_dict()}")
    
    # Normalizar nombres de campos (case insensitive)
    fila_dict = {str(k).strip().lower(): v for k, v in fila.items() if v is not None}
    
    # Mapear nombres de campos
    mapeo_campos = {
        'ejercicio': 'ejercicio',
        'mercado': 'mercado', 
        'instrumento': 'instrumento',
        'fecha': 'fecha',
        'secuencia': 'secuencia',
        'numero_dividendo': 'numero_dividendo',
        'numero de dividendo': 'numero_dividendo',
        'descripcion': 'descripcion_dividendo',
        'descripción': 'descripcion_dividendo',
        'tipo_sociedad': 'tipo_sociedad',
        'tipo sociedad': 'tipo_sociedad',
        'valor_historico': 'valor_historico',
        'valor histórico': 'valor_historico',
        'acogido_isfut': 'acogido_isfut',
        'acogido isfut': 'acogido_isfut',
        'factor_actualizacion': 'factor_actualizacion',
        'factor actualizacion': 'factor_actualizacion'
    }
    
    # Crear diccionario normalizado
    fila_normalizada = {}
    for campo_orig, campo_dest in mapeo_campos.items():
        if campo_orig in fila_dict and fila_dict[campo_orig]:
            fila_normalizada[campo_dest] = fila_dict[campo_orig]
    
    # Agregar factores
    for i in range(8, 38):
        factor_key = f'factor_{i}'
        factor_key_alt = f'factor {i}'
        if factor_key in fila_dict and fila_dict[factor_key]:
            fila_normalizada[factor_key] = fila_dict[factor_key]
        elif factor_key_alt in fila_dict and fila_dict[factor_key_alt]:
            fila_normalizada[factor_key] = fila_dict[factor_key_alt]
    
    # Validar campos obligatorios
    campos_obligatorios = ['ejercicio', 'mercado', 'instrumento', 'fecha', 'secuencia']
    for campo in campos_obligatorios:
        if campo not in fila_normalizada or not fila_normalizada[campo]:
            raise ValueError(f"Campo obligatorio faltante: {campo}")
    
    # Convertir y validar tipos de datos
    try:
        ejercicio = int(fila_normalizada['ejercicio'])
        secuencia = int(fila_normalizada['secuencia'])
        
        # Convertir fecha (aceptar múltiples formatos)
        fecha_str = fila_normalizada['fecha']
        try:
            fecha_pago = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            try:
                fecha_pago = datetime.strptime(fecha_str, '%d/%m/%Y').date()
            except ValueError:
                try:
                    fecha_pago = datetime.strptime(fecha_str, '%d-%m-%Y').date()
                except ValueError:
                    raise ValueError(f"Formato de fecha no válido: {fecha_str}. Use YYYY-MM-DD, DD/MM/YYYY o DD-MM-YYYY")
        
        mercado = fila_normalizada['mercado'].upper()
        instrumento = fila_normalizada['instrumento'].upper()
        
    except ValueError as e:
        raise ValueError(f"Error en tipos de datos: {str(e)}")
    
    # Buscar calificación existente
    calificacion = CalificacionTributaria.objects.filter(
        ejercicio=ejercicio,
        mercado=mercado,
        instrumento=instrumento,
        secuencia_evento=secuencia,
        estado=True
    ).first()
    
    if calificacion and not sobrescribir:
        print(f"Registro existente omitido: {instrumento} - {ejercicio} - {secuencia}")
        return False  # Omitir registro existente
    
    # Preparar datos para crear/actualizar calificación
    datos_calificacion = {
        'ejercicio': ejercicio,
        'mercado': mercado,
        'instrumento': instrumento,
        'fecha_pago': fecha_pago,
        'secuencia_evento': secuencia,
        'numero_dividendo': int(fila_normalizada.get('numero_dividendo', 0)),
        'descripcion_dividendo': fila_normalizada.get('descripcion_dividendo', ''),
        'tipo_sociedad': fila_normalizada.get('tipo_sociedad', 'A'),
        'acogido_isfut': fila_normalizada.get('acogido_isfut', 'false').lower() in ['true', '1', 'si', 'sí', 'verdadero'],
        'origen': 'Carga_Masiva',
        'usuario_creador': usuario
    }
    
    # Agregar campos opcionales si existen
    if 'valor_historico' in fila_normalizada and fila_normalizada['valor_historico']:
        try:
            datos_calificacion['valor_historico'] = Decimal(str(fila_normalizada['valor_historico']).replace(',', '.'))
        except:
            datos_calificacion['valor_historico'] = None
    
    if 'factor_actualizacion' in fila_normalizada and fila_normalizada['factor_actualizacion']:
        try:
            datos_calificacion['factor_actualizacion'] = Decimal(str(fila_normalizada['factor_actualizacion']).replace(',', '.'))
        except:
            datos_calificacion['factor_actualizacion'] = Decimal('0')
    
    # Crear o actualizar calificación
    if not calificacion:
        calificacion = CalificacionTributaria(**datos_calificacion)
        calificacion.save()
        print(f"Nueva calificación creada: {instrumento} - {ejercicio} - {secuencia}")
    else:
        for field, value in datos_calificacion.items():
            setattr(calificacion, field, value)
        calificacion.save()
        print(f"Calificación actualizada: {instrumento} - {ejercicio} - {secuencia}")
    
    # Crear o actualizar factores
    factores, created = FactorCalificacion.objects.get_or_create(
        id_calificacion=calificacion
    )
    
    # Actualizar factores del 8 al 37
    factores_actualizados = 0
    for i in range(8, 38):
        factor_key = f'factor_{i}'
        if factor_key in fila_normalizada and fila_normalizada[factor_key]:
            try:
                # Convertir a Decimal, manejando comas como separadores decimales
                valor_str = str(fila_normalizada[factor_key]).replace(',', '.')
                valor_decimal = Decimal(valor_str)
                setattr(factores, factor_key, valor_decimal)
                factores_actualizados += 1
            except Exception as e:
                print(f"Error convirtiendo {factor_key}: {fila_normalizada[factor_key]} - {e}")
                setattr(factores, factor_key, None)
    
    if factores_actualizados > 0:
        factores.save()
        print(f"Factores actualizados: {factores_actualizados} factores para {instrumento}")
    
    return True

def procesar_fila_montos(fila, sobrescribir, usuario):
    """Procesa una fila con montos para calcular factores"""
    # Por ahora, usar misma lógica que factores hasta que definamos estructura de montos
    return procesar_fila_factores(fila, sobrescribir, usuario)


import logging

logger = logging.getLogger(__name__)


def login_view(request):
    """Vista de login personalizada con soporte MFA"""
    if request.user.is_authenticated:
        return redirect('lista_calificaciones')
    
    # Track remaining attempts to show in the template
    remaining_attempts = None

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            correo = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            # Normalizar correo para evitar issues con espacios o mayúsculas
            if correo:
                correo = correo.strip()

            # Intentar localizar usuario por correo para manejar bloqueo
            usuario_obj = Usuario.objects.filter(correo__iexact=correo).first()

            logger.debug(f"Login intento para '{correo}' - usuario encontrado: {bool(usuario_obj)}")
            if usuario_obj:
                logger.debug(f"Estado: {usuario_obj.estado}, failed_attempts: {usuario_obj.failed_login_attempts}, locked_until: {usuario_obj.locked_until}")

            if usuario_obj and usuario_obj.is_locked():
                locked_until = usuario_obj.locked_until
                messages.error(request, f'Cuenta bloqueada hasta {locked_until.strftime("%Y-%m-%d %H:%M:%S")}. Intenta más tarde o contacta a un administrador.')
            else:
                user = authenticate(request, username=correo, password=password)
                if user is not None and getattr(user, 'estado', True):
                    # Reset de intentos fallidos en login exitoso
                    try:
                        if usuario_obj:
                            usuario_obj.reset_failed_login()
                    except Exception:
                        pass

                    # Si el usuario tiene MFA configurado, redirigir a verificación
                    if user.has_mfa_enabled():
                        request.session['mfa_user_id'] = user.id
                        request.session['mfa_backend'] = user.backend
                        return redirect('mfa_verify')
                    else:
                        # Login normal sin MFA
                        auth_login(request, user)
                        messages.success(request, f'¡Bienvenido {user.nombre}!')
                        # Redirección según rol
                        next_url = request.GET.get('next', 'lista_calificaciones')
                        return redirect(next_url)
                else:
                    # Credenciales inválidas: aumentar contador si existe usuario
                    if usuario_obj:
                        # Umbral y minutos de bloqueo (coherente con el modelo)
                        THRESHOLD = 3
                        LOCK_MINUTES = 15

                        locked = usuario_obj.increment_failed_login(threshold=THRESHOLD, lock_minutes=LOCK_MINUTES)
                        logger.info(f"Después incremento: usuario={usuario_obj.correo}, failed_attempts: {usuario_obj.failed_login_attempts}, locked: {locked}, locked_until: {usuario_obj.locked_until}")

                        # Registrar intento fallido en auditoría
                        try:
                            LogAuditoria.objects.create(
                                accion='LOGIN_FAIL',
                                usuario_responsable=usuario_obj,
                                detalle=f'Intento de login fallido desde {request.META.get("REMOTE_ADDR", "-")}'
                            )
                        except Exception:
                            pass

                        if locked:
                            # Registrar bloqueo en auditoría
                            try:
                                LogAuditoria.objects.create(
                                    accion='LOCK_ACCOUNT',
                                    usuario_responsable=usuario_obj,
                                    detalle='Cuenta bloqueada automáticamente por superar intentos fallidos'
                                )
                            except Exception:
                                pass
                            messages.error(request, f'Has excedido los intentos permitidos. La cuenta ha sido bloqueada hasta {usuario_obj.locked_until.strftime("%Y-%m-%d %H:%M:%S")}.')
                            remaining_attempts = 0
                        else:
                            remaining_attempts = max(0, THRESHOLD - (usuario_obj.failed_login_attempts or 0))
                            messages.error(request, f'Credenciales inválidas. Te quedan {remaining_attempts} intentos antes del bloqueo.')
                    else:
                        # Intentamos buscar por otras variantes (por si el usuario ingresó un correo con espacios)
                        alt_correo = correo.strip() if correo else correo
                        usuario_alt = Usuario.objects.filter(correo__iexact=alt_correo).first() if alt_correo else None
                        logger.debug(f"Usuario alternativo encontrado: {bool(usuario_alt)}")
                        if usuario_alt:
                            usuario_alt.increment_failed_login()
                            remaining_attempts = None
                            messages.error(request, 'Credenciales inválidas.')
                        else:
                            messages.error(request, 'Credenciales inválidas')
    else:
        form = LoginForm()

    return render(request, 'calificaciones/login.html', {'form': form, 'remaining_attempts': remaining_attempts})

@login_required
def mfa_setup(request):
    """Vista para configurar MFA por primera vez"""
    print("=== MFA SETUP VISTA INICIADA ===")
    
    if request.user.has_mfa_enabled():
        messages.info(request, 'MFA ya está configurado para tu cuenta.')
        return redirect('perfil_usuario')
    
    device = request.user.setup_mfa()
    print(f"Dispositivo creado: {device}, Confirmado: {device.confirmed}")

    # Ensure the device stores a hex key compatible with django-otp's bin_key
    # If the device.key isn't hex (bin_key access raises), generate a Base32 secret,
    # store it as hex on the device and use that Base32 for the QR.
    secret_b32 = None
    try:
        # Try to access bin_key to confirm it's hex
        _ = device.bin_key
    except Exception:
        # Generate a new Base32 secret and write it into device.key as hex
        secret_b32 = pyotp.random_base32()
        try:
            key_bytes = base64.b32decode(secret_b32)
            device.key = key_bytes.hex()
            device.save()
        except Exception:
            # If decoding fails, fallback to storing ascii-hex of secret
            device.key = secret_b32.encode('utf-8').hex()
            device.save()
    
    if request.method == 'POST':
        print("=== MÉTODO POST DETECTADO ===")
        form = MfaVerifyForm(request.user, request.POST)
        print(f"Formulario válido: {form.is_valid()}")
        print(f"Errores del formulario: {form.errors}")
        
        if form.is_valid():
            print("=== FORMULARIO VÁLIDO ===")
            # Verificar manualmente el token
            token = form.cleaned_data['token']
            print(f"Token recibido: {token}")
            
            is_valid = device.verify_token(token)
            print(f"Token válido: {is_valid}")
            
            if is_valid:
                device.confirmed = True
                device.save()
                messages.success(request, '✅ MFA configurado exitosamente!')
                
                LogAuditoria.objects.create(
                    accion='MFA_SETUP',
                    usuario_responsable=request.user,
                    detalle='Configuración de MFA/2FA',
                    ip_origen=request.META.get('REMOTE_ADDR', '127.0.0.1')
                )
                
                return redirect('perfil_usuario')
            else:
                messages.error(request, '❌ Código de verificación inválido.')
                print("Token inválido según verify_token")
        else:
            print("=== FORMULARIO INVÁLIDO ===")
            messages.error(request, '❌ Por favor corrige los errores en el formulario.')
    else:
        print("=== MÉTODO GET ===")
        form = MfaVerifyForm(request.user)
    
    # Generar QR code
    issuer = "NUAM Calificaciones"
    account_name = f"{request.user.correo}"
    
    # TOTP secret should be provided as Base32 for authenticator apps.
    # The device `key` can be stored in different formats (hex, base32, raw); handle robustly.
    import re

    secret_b32 = None
    try:
        # Preferred: device.bin_key returns binary bytes when key is hex
        secret_b32 = base64.b32encode(device.bin_key).decode('utf-8').strip('=').upper()
    except Exception:
        # If bin_key failed (non-hex key), try to derive Base32 from various formats
        raw_key = getattr(device, 'key', None)
        if raw_key:
            raw_key_str = str(raw_key).strip()
            # If it already looks like Base32 (A-Z2-7) use it (normalize)
            if re.fullmatch(r'[A-Z2-7]+=*', raw_key_str.upper()):
                secret_b32 = raw_key_str.upper().strip('=')
            else:
                # Fallback: base32-encode the bytes of the stored key string
                try:
                    secret_b32 = base64.b32encode(raw_key_str.encode('utf-8')).decode('utf-8').strip('=').upper()
                except Exception:
                    # Last ditch fallback: use hex representation of bin_key if available
                    try:
                        secret_b32 = base64.b32encode(device.bin_key).decode('utf-8').strip('=').upper()
                    except Exception:
                        secret_b32 = raw_key_str.upper()
        else:
            secret_b32 = ''

    otpauth_url = (
        f"otpauth://totp/{urllib.parse.quote(issuer)}:{urllib.parse.quote(account_name)}"
        f"?secret={secret_b32}&issuer={urllib.parse.quote(issuer)}&digits=6&algorithm=SHA1&period=30"
    )
    
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(otpauth_url)

    qr_is_svg = False
    try:
        # Prefer PNG via Pillow when available
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_code = base64.b64encode(buffer.getvalue()).decode()
        qr_is_svg = False
    except Exception:
        # Pillow not available or failed — fallback to SVG (no PIL dependency)
        try:
            from qrcode.image.svg import SvgImage
            buffer = BytesIO()
            img = qr.make_image(image_factory=SvgImage)
            img.save(buffer)
            svg = buffer.getvalue().decode('utf-8')
            qr_code = svg
            qr_is_svg = True
        except Exception:
            # As a last resort, set empty QR (template will show only secret)
            qr_code = ''
            qr_is_svg = False
    
    context = {
        'form': form,
        'qr_code': qr_code,
        'qr_is_svg': qr_is_svg,
        'secret_key': secret_b32,
        'account_name': account_name,
        'issuer': issuer,
    }
    return render(request, 'calificaciones/mfa_setup.html', context)

def mfa_verify(request):
    """Vista para verificar token MFA después del login"""
    user_id = request.session.get('mfa_user_id')
    backend = request.session.get('mfa_backend')
    
    if not user_id or not backend:
        messages.error(request, 'Sesión inválida.')
        return redirect('login')
    
    try:
        user = Usuario.objects.get(id=user_id, estado=True)
    except Usuario.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('login')
    
    if request.method == 'POST':
        # CORREGIDO: Pasar el usuario como primer argumento
        form = MfaVerifyForm(user, request.POST)
        if form.is_valid():
            # Login exitoso con MFA
            user.backend = backend
            auth_login(request, user)
            otp_login(request, form.get_device())
            
            # Limpiar sesión MFA
            request.session.pop('mfa_user_id', None)
            request.session.pop('mfa_backend', None)
            
            messages.success(request, f'¡Bienvenido {user.nombre}!')
            
            # Log de auditoría
            LogAuditoria.objects.create(
                accion='LOGIN',
                usuario_responsable=user,
                detalle='Inicio de sesión con MFA/2FA',
                ip_origen=request.META.get('REMOTE_ADDR', '127.0.0.1')
            )
            
            next_url = request.GET.get('next', 'lista_calificaciones')
            return redirect(next_url)
        else:
            messages.error(request, 'Código de verificación inválido.')
    else:
        # CORREGIDO: Pasar el usuario como primer argumento
        form = MfaVerifyForm(user)
    
    context = {
        'form': form,
        'user': user,
    }
    return render(request, 'calificaciones/mfa_verify.html', context)
@login_required
def mfa_disable(request):
    """Vista para desactivar MFA"""
    if request.method == 'POST':
        device = request.user.get_mfa_device()
        if device:
            device.delete()
            messages.success(request, 'MFA desactivado exitosamente.')
            
            # Log de auditoría
            LogAuditoria.objects.create(
                accion='MFA_DISABLE',
                usuario_responsable=request.user,
                detalle='Desactivación de MFA/2FA',
                ip_origen=request.META.get('REMOTE_ADDR', '127.0.0.1')
            )
        else:
            messages.info(request, 'MFA no estaba activado para tu cuenta.')
    
    return redirect('perfil_usuario')

@login_required
@administrador_required
def eliminar_usuario(request, usuario_id):
    """Eliminar usuario existente usando soft delete"""
    if request.method == 'POST':
        try:
            usuario = get_object_or_404(Usuario, id=usuario_id)
            
            # Prevenir que el usuario se elimine a sí mismo
            if request.user.id == usuario.id:
                messages.error(request, 'No puedes eliminar tu propio usuario.')
                return redirect('gestion_usuarios')
            
            nombre_usuario = usuario.nombre
            
            # Usar soft delete en lugar de eliminar físicamente
            usuario.soft_delete(request.user)
            
            messages.success(request, f'Usuario "{nombre_usuario}" desactivado correctamente.')
            
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
@solo_lectura_required
def lista_calificaciones(request):
    """Vista principal del mantenedor con filtros"""
    usuario_rol = request.user.rol
    
    # LÓGICA CORREGIDA PARA TODOS LOS ROLES
    if usuario_rol == "Administrador":
        calificaciones = CalificacionTributaria.objects.filter(estado=True)
    elif usuario_rol == "Analista":
        calificaciones = CalificacionTributaria.objects.filter(estado=True)
    elif usuario_rol == "Auditor":
        # Auditor puede ver todas las calificaciones (solo lectura)
        calificaciones = CalificacionTributaria.objects.filter(estado=True)
    elif usuario_rol == "Corredor":
        # Corredor ve solo calificaciones de origen Corredor
        calificaciones = CalificacionTributaria.objects.filter(
            estado=True, 
            origen='Corredor'
        )
    else:
        calificaciones = CalificacionTributaria.objects.none()

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


@login_required
@solo_lectura_required
def dashboard(request):
    """Vista del dashboard con métricas básicas de calificaciones"""
    usuario_rol = request.user.rol
    if usuario_rol == 'Corredor':
        calificaciones = CalificacionTributaria.objects.filter(estado=True, origen='Corredor')
    else:
        calificaciones = CalificacionTributaria.objects.filter(estado=True)

    total = calificaciones.count()
    por_origen = calificaciones.values('origen').annotate(count=Count('origen'))
    por_mercado = calificaciones.values('mercado').annotate(count=Count('mercado')).order_by('-count')[:10]
    recientes = calificaciones.order_by('-id_calificacion')[:5]

    context = {
        'total': total,
        'por_origen': por_origen,
        'por_mercado': por_mercado,
        'recientes': recientes,
    }
    return render(request, 'calificaciones/dashboard.html', context)

@login_required
@editor_required
def crear_calificacion_paso1(request):
    """Primer paso: Ingreso de datos básicos"""
    # Si es Corredor, redirigir a la vista especial
    if request.user.rol == 'Corredor':
        return crear_calificacion_corredor_paso1(request)
    
    # Resto del código igual...
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
@editor_required
def crear_calificacion_paso2(request):
    """Segundo paso: Ingreso de montos - ACCESIBLE PARA EDITORES"""
    # Verificar que vengamos del paso 1
    datos_paso1_serializados = request.session.get('calificacion_paso1')
    if not datos_paso1_serializados:
        messages.warning(request, 'Por favor complete primero los datos básicos.')
        return redirect('crear_calificacion_paso1')
    
    # Si es Corredor, verificar que el origen sea Corredor
    if request.user.rol == 'Corredor':
        datos_paso1 = convertir_fechas_desde_sesion(datos_paso1_serializados)
        if datos_paso1.get('origen') != 'Corredor':
            messages.error(request, 'No tienes permisos para crear calificaciones de este origen.')
            return redirect('lista_calificaciones')
    
    # Resto del código igual...
    datos_paso1 = convertir_fechas_desde_sesion(datos_paso1_serializados)
    
    if request.method == 'POST':
        form = MontosForm(request.POST)
        if form.is_valid():
            # Calcular factores automáticamente
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
            
            factores_serializables = {}
            for key, value in factores.items():
                if isinstance(value, Decimal):
                    factores_serializables[key] = str(value)
                else:
                    factores_serializables[key] = value
            
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
@editor_required
def crear_calificacion_paso3(request):
    """Tercer paso: Factores - ACCESIBLE PARA EDITORES"""
    # Verificar permisos para Corredor
    if request.user.rol == 'Corredor':
        datos_paso1_serializados = request.session.get('calificacion_paso1')
        if datos_paso1_serializados:
            datos_paso1 = convertir_fechas_desde_sesion(datos_paso1_serializados)
            if datos_paso1.get('origen') != 'Corredor':
                messages.error(request, 'No tienes permisos para crear calificaciones de este origen.')
                return redirect('lista_calificaciones')
    
    # Resto del código igual...
    datos_paso1_serializados = request.session.get('calificacion_paso1')
    montos_paso2_serializados = request.session.get('montos_paso2', {})
    factores_calculados_serializados = request.session.get('factores_calculados', {})
    
    if not datos_paso1_serializados:
        messages.warning(request, 'Por favor complete los pasos anteriores.')
        return redirect('crear_calificacion_paso1')
    
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
                
                usuario_creador = request.user
                
                # Crear calificación tributaria
                calificacion = CalificacionTributaria(
                    usuario_creador=usuario_creador,
                    **datos_paso1
                )
                calificacion.save()
                
                # Crear factores de calificación
                factores_data = form.cleaned_data
                campos_modelo = [f.name for f in FactorCalificacion._meta.get_fields()]
                factores_filtrados = {k: v for k, v in factores_data.items() if k in campos_modelo}
                
                factores = FactorCalificacion(
                    id_calificacion=calificacion,
                    **factores_filtrados
                )
                factores.save()
                
                LogAuditoria.objects.create(
                    accion='CREATE',
                    usuario_responsable=request.user,
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
    
    else:
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
            # CORRECCIÓN: Usar request.user directamente
            calificacion.estado = False
            calificacion.save()
            
            # Log de eliminación
            LogAuditoria.objects.create(
                accion='DELETE',
                usuario_responsable=request.user,  # CORREGIDO
                id_calificacion=calificacion,
                detalle='Eliminación de calificación tributaria',
                ip_origen=request.META.get('REMOTE_ADDR', '127.0.0.1')
            )
            
            messages.success(request, 'Calificación eliminada exitosamente.')
        except Exception as e:
            messages.error(request, f'Error al eliminar: {str(e)}')
    
    return redirect('lista_calificaciones')

@login_required
@editor_required
def editar_calificacion_paso1(request, id_calificacion):
    """Editar primer paso: Datos básicos"""
    calificacion = get_object_or_404(CalificacionTributaria, id_calificacion=id_calificacion)
    
    # Validar permisos para Corredor
    if request.user.rol == 'Corredor' and calificacion.origen != 'Corredor':
        return HttpResponseForbidden("No tienes permisos para editar esta calificación")
    
    if request.method == 'POST':
        form = CalificacionTributariaForm(request.POST, instance=calificacion)
        if form.is_valid():
            # Si es Corredor, forzar origen Corredor
            datos = form.cleaned_data
            if request.user.rol == 'Corredor':
                datos['origen'] = 'Corredor'
            
            datos_serializables = convertir_fechas_para_sesion(datos)
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
@editor_required
def editar_calificacion_paso2(request, id_calificacion):
    """Editar segundo paso: Montos"""
    calificacion = get_object_or_404(CalificacionTributaria, id_calificacion=id_calificacion)
    
    # Validar permisos para Corredor
    if request.user.rol == 'Corredor' and calificacion.origen != 'Corredor':
        return HttpResponseForbidden("No tienes permisos para editar esta calificación")
    
    # Resto del código igual...
    if request.session.get('edicion_calificacion') != id_calificacion:
        messages.warning(request, 'Por favor complete primero los datos básicos.')
        return redirect('editar_calificacion_paso1', id_calificacion=id_calificacion)
    
    datos_paso1_serializados = request.session.get('calificacion_paso1')
    if not datos_paso1_serializados:
        messages.warning(request, 'Por favor complete primero los datos básicos.')
        return redirect('editar_calificacion_paso1', id_calificacion=id_calificacion)
    
    datos_paso1 = convertir_fechas_desde_sesion(datos_paso1_serializados)
    
    if request.method == 'POST':
        form = MontosForm(request.POST)
        if form.is_valid():
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
@editor_required
def editar_calificacion_paso3(request, id_calificacion):
    """Editar tercer paso: Factores"""
    calificacion = get_object_or_404(CalificacionTributaria, id_calificacion=id_calificacion)
    
    # Validar permisos para Corredor
    if request.user.rol == 'Corredor' and calificacion.origen != 'Corredor':
        return HttpResponseForbidden("No tienes permisos para editar esta calificación")
    
    factores_existentes = get_object_or_404(FactorCalificacion, id_calificacion=calificacion)
    
    # Resto del código igual...
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
                # Actualizar calificación tributaria
                for field, value in datos_paso1.items():
                    setattr(calificacion, field, value)
                calificacion.save()
                
                # Actualizar factores
                factores = form.save(commit=False)
                factores.id_calificacion = calificacion
                factores.save()
                
                LogAuditoria.objects.create(
                    accion='UPDATE',
                    usuario_responsable=request.user,
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
    
    else:
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
@solo_lectura_required
def detalle_calificacion(request, id_calificacion):
    """Vista para mostrar todos los datos de una calificación - ACCESIBLE PARA TODOS"""
    calificacion = get_object_or_404(CalificacionTributaria, id_calificacion=id_calificacion)
    
    # Verificar permisos específicos para Corredor
    if request.user.rol == 'Corredor' and calificacion.origen != 'Corredor':
        return HttpResponseForbidden("No tienes permisos para ver esta calificación")
    
    # Obtener factores
    try:
        factores = FactorCalificacion.objects.get(id_calificacion=calificacion)
    except FactorCalificacion.DoesNotExist:
        factores = None
        messages.warning(request, 'No se encontraron factores asociados a esta calificación.')
    
    # Obtener logs de auditoría relacionados
    logs = LogAuditoria.objects.filter(id_calificacion=calificacion).order_by('-fecha_hora')
    
    context = {
        'calificacion': calificacion,
        'factores': factores,
        'logs': logs,
    }
    return render(request, 'calificaciones/detalle.html', context)

def login_view(request):
    """Vista de login personalizada con bloqueo por intentos fallidos y soporte MFA"""
    if request.user.is_authenticated:
        return redirect('lista_calificaciones')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            correo = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            # Intentar localizar usuario por correo para manejar bloqueo
            usuario_obj = Usuario.objects.filter(correo__iexact=correo).first()

            if usuario_obj and usuario_obj.is_locked():
                locked_until = usuario_obj.locked_until
                messages.error(request, f'Cuenta bloqueada hasta {locked_until.strftime("%Y-%m-%d %H:%M:%S")}. Intenta más tarde o contacta a un administrador.')
            else:
                user = authenticate(request, username=correo, password=password)
                if user is not None and user.estado:
                    # Reset de intentos fallidos en login exitoso
                    try:
                        usuario_obj.reset_failed_login()
                    except Exception:
                        pass

                    # Si el usuario tiene MFA configurado, redirigir a verificación
                    if user.has_mfa_enabled():
                        request.session['mfa_user_id'] = user.id
                        request.session['mfa_backend'] = user.backend
                        return redirect('mfa_verify')
                    else:
                        # Login normal sin MFA
                        auth_login(request, user)
                        messages.success(request, f'¡Bienvenido {user.nombre}!')
                        # Redirección según rol
                        next_url = request.GET.get('next', 'lista_calificaciones')
                        return redirect(next_url)
                else:
                    # Credenciales inválidas: aumentar contador si existe usuario
                    if usuario_obj:
                        usuario_obj.increment_failed_login()
                        # Si quedó bloqueado al incrementar, notifica
                        if usuario_obj.is_locked():
                            messages.error(request, 'Has excedido los intentos permitidos. La cuenta ha sido bloqueada temporalmente.')
                        else:
                            remaining = max(0, 3 - (usuario_obj.failed_login_attempts or 0))
                            messages.error(request, f'Credenciales inválidas. Te quedan {remaining} intentos antes del bloqueo.')
                    else:
                        messages.error(request, 'Credenciales inválidas')
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
    mfa_enabled = request.user.has_mfa_enabled()
    
    if request.method == 'POST':
        if 'change_password' in request.POST:
            form = PasswordChangeForm(request.user, request.POST)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Tu contraseña fue actualizada exitosamente!')
                return redirect('perfil_usuario')
        else:
            form = PasswordChangeForm(request.user)
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
        'mfa_enabled': mfa_enabled,
    }
    return render(request, 'calificaciones/perfil.html', context)

@login_required
@administrador_required
def gestion_usuarios(request):
    """Vista solo para administradores - gestión de usuarios"""
    usuarios = Usuario.objects.filter(estado=True)  # Solo usuarios activos
    return render(request, 'calificaciones/gestion_usuarios.html', {'usuarios': usuarios})

@login_required
@administrador_required
def crear_usuario(request):
    """Crear nuevo usuario (solo administradores)"""
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            # Si la contraseña fue generada automáticamente, informar al administrador
            gen_pwd = getattr(form, 'generated_password', None)
            if gen_pwd:
                messages.info(request, f'Contraseña generada para {usuario.correo}: {gen_pwd}')

            messages.success(request, f'Usuario {usuario.nombre} creado exitosamente')
            return redirect('gestion_usuarios')
    else:
        form = UsuarioForm()
    
    return render(request, 'calificaciones/crear_usuario.html', {'form': form})

@login_required
@administrador_required
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

@login_required
@corredor_required
def crear_calificacion_corredor_paso1(request):
    """Vista especial de creación para Corredor - solo datos básicos"""
    if request.method == 'POST':
        form = CalificacionTributariaForm(request.POST)
        if form.is_valid():
            # Forzar origen "Corredor" para este rol
            datos = form.cleaned_data
            datos['origen'] = 'Corredor'
            
            datos_serializables = convertir_fechas_para_sesion(datos)
            request.session['calificacion_paso1'] = datos_serializables
            return redirect('crear_calificacion_paso2')
    else:
        form = CalificacionTributariaForm()
    
    context = {'form': form, 'paso_actual': 1, 'es_corredor': True}
    return render(request, 'calificaciones/crear_paso1.html', context)