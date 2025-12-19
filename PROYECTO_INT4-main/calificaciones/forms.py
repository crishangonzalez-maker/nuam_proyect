from django import forms
from django.core.validators import RegexValidator
from django_otp.forms import OTPTokenForm
from django_otp.plugins.otp_totp.models import TOTPDevice
import re
try:
    import pyotp
except Exception:
    pyotp = None
from .models import CalificacionTributaria, Usuario, FactorCalificacion
from django.http import QueryDict
from decimal import Decimal
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.sites.shortcuts import get_current_site
from .models import Usuario
from datetime import date
from django.utils.crypto import get_random_string
import re

# ... tus otros formularios existentes ...

class MfaVerifyForm(forms.Form):
    """Formulario para verificar token MFA"""
    token = forms.CharField(
        label='Código de verificación',
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '000000',
            'autocomplete': 'one-time-code',
            'pattern': '[0-9]{6}',
            'inputmode': 'numeric',
            'style': 'text-align: center; font-size: 1.2rem; letter-spacing: 0.5em;'
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_token(self):
        token = self.cleaned_data.get('token')
        
        if not token:
            raise forms.ValidationError('Este campo es obligatorio.')
        
        if not token.isdigit():
            raise forms.ValidationError('El código debe contener solo números.')
        
        if len(token) != 6:
            raise forms.ValidationError('El código debe tener exactamente 6 dígitos.')
        # Look for any TOTP device for the user (confirmed or unconfirmed)
        try:
            device_qs = TOTPDevice.objects.filter(user=self.user)
        except Exception:
            device_qs = None

        if not device_qs or not device_qs.exists():
            raise forms.ValidationError('No se encontró un dispositivo MFA configurado para el usuario.')

        # Prefer a confirmed device, otherwise use the most-recent one
        device = device_qs.filter(confirmed=True).first() or device_qs.first()

        # Try using the device's built-in verification first
        valid = False
        try:
            valid = bool(device.verify_token(token))
        except Exception:
            valid = False

        # If built-in verification failed (e.g., device.key isn't hex), try pyotp fallback
        if not valid and pyotp is not None:
            try:
                raw_key = getattr(device, 'key', None)
                if raw_key:
                    raw = str(raw_key).strip().upper()
                    # If it looks like Base32 use directly
                    if re.fullmatch(r'[A-Z2-7]+=*', raw):
                        totp = pyotp.TOTP(raw)
                        valid = bool(totp.verify(token, valid_window=1))
                    else:
                        # Otherwise base32-encode the raw bytes/string and try
                        try:
                            b32 = pyotp.random_base32() if not raw else pyotp.utils.to_bytes(raw)
                            # If we got bytes, encode to base32
                            if isinstance(b32, bytes):
                                b32 = pyotp.utils.byte_to_base32(b32)
                        except Exception:
                            b32 = None

                        if b32:
                            totp = pyotp.TOTP(b32)
                            valid = bool(totp.verify(token, valid_window=1))
            except Exception:
                valid = False

        if not valid:
            raise forms.ValidationError('Código de verificación inválido.')

        # Store device for use in view (otp_login)
        self._device = device
        return token

    def get_device(self):
        """Devuelve el dispositivo TOTP que verificó el token (o None)."""
        return getattr(self, '_device', None)

class MfaSetupForm(forms.Form):
    """Formulario para configurar MFA"""
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

class CalificacionTributariaForm(forms.ModelForm):
    """Formulario para ingreso manual de calificaciones tributarias"""
    
    class Meta:
        model = CalificacionTributaria
        fields = [
            'ejercicio', 'mercado', 'instrumento', 'fecha_pago', 
            'secuencia_evento', 'numero_dividendo', 'descripcion_dividendo',
            'tipo_sociedad', 'valor_historico', 'acogido_isfut', 'origen'
        ]
        widgets = {
            'ejercicio': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '2000',
                'max': '2030'
            }),
            'mercado': forms.Select(attrs={'class': 'form-control'}),
            'instrumento': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: COPEC'
            }),
            'fecha_pago': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'format': '%Y-%m-%d'  
            }),
            'secuencia_evento': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '10000'
            }),
            'numero_dividendo': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'descripcion_dividendo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción del dividendo...'
            }),
            'tipo_sociedad': forms.Select(attrs={'class': 'form-control'}),
            'valor_historico': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'acogido_isfut': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'origen': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'acogido_isfut': 'Acogido a ISFUT/ISIFT',
            'valor_historico': 'Valor Histórico',
            'secuencia_evento': 'Secuencia del Evento de Capital',
            'numero_dividendo': 'Número de Dividendo',
            'descripcion_dividendo': 'Descripción del Dividendo',
        }

    def clean_secuencia_evento(self):
        """Validar que la secuencia sea mayor a 10000"""
        secuencia = self.cleaned_data.get('secuencia_evento')
        if secuencia and secuencia <= 10000:
            raise forms.ValidationError("La secuencia debe ser superior a 10.000")
        return secuencia

    def clean(self):
        """Validación adicional: la fecha de pago no puede ser anterior al ejercicio."""
        cleaned = super().clean()
        ejercicio = cleaned.get('ejercicio')
        fecha_pago = cleaned.get('fecha_pago')

        if ejercicio and fecha_pago:
            try:
                ejercicio_int = int(ejercicio)
            except Exception:
                ejercicio_int = None

            if ejercicio_int is not None:
                primero_enero = date(ejercicio_int, 1, 1)
                if fecha_pago < primero_enero:
                    self.add_error('fecha_pago', forms.ValidationError(
                        'La fecha de pago no puede ser anterior al inicio del ejercicio.'
                    ))

        return cleaned

class MontosForm(forms.Form):
    """Formulario para ingreso de montos (segundo paso)"""
    
    # Montos según la especificación DJ 1949
    monto_8 = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Con crédito por IDPC generados a contar del 01.01.2017",
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    monto_9 = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Con crédito por IDPC acumulados hasta el 31.12.2016",
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    monto_10 = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Con derecho a crédito por pago de IDPC voluntario",
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    monto_11 = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Sin derecho a crédito",
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    monto_12 = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Rentas provenientes del registro RAP y Diferencia Inicial de sociedad acogida al ex Art. 14 TER A) LIR",
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    def calcular_factores(self):
        """Calcula los factores a partir de los montos ingresados"""
        montos = []
        for i in range(8, 13):  # Del monto_8 al monto_12
            monto = self.cleaned_data.get(f'monto_{i}', Decimal('0'))
            montos.append(monto)
        
        total_montos = sum(montos)
        
        if total_montos == 0:
            return {}
        
        factores = {}
        for i, monto in enumerate(montos, start=8):
            factor = monto / total_montos
            # Redondear a 8 decimales
            factores[f'factor_{i}'] = factor.quantize(Decimal('0.00000001'))
        
        return factores

class FactoresForm(forms.ModelForm):
    """Formulario para ingreso/edición directa de factores (tercer paso)"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If form was bound with data that may contain scientific-notation
        # numbers (e.g. '0E-8'), normalize them so the widget displays
        # fixed-point 8-decimal strings instead of scientific notation.
        if hasattr(self, 'data') and self.data:
            try:
                # QueryDict.copy() returns a mutable copy
                if isinstance(self.data, QueryDict):
                    mutable = self.data.copy()
                else:
                    mutable = dict(self.data)

                for i in range(8, 20):
                    key = f'factor_{i}'
                    if key in mutable and mutable.get(key) not in (None, ''):
                        raw = mutable.get(key)
                        try:
                            v = Decimal(str(raw))
                            v = v.quantize(Decimal('0.00000001'))
                            mutable[key] = format(v, '.8f')
                        except Exception:
                            # fallback: try parse float then format
                            try:
                                parsed = float(raw)
                                mutable[key] = format(Decimal(str(parsed)).quantize(Decimal('0.00000001')), '.8f')
                            except Exception:
                                # leave value as-is
                                pass

                # Replace self.data with the normalized mutable copy
                self.data = mutable
            except Exception:
                # If anything goes wrong, don't break form construction
                pass
        # Ensure factor values display as fixed-point decimals with 8 places
        for i in range(8, 20):
            field_name = f'factor_{i}'
            if field_name not in self.fields:
                continue
            val = None
            # Prefer explicit initial, otherwise instance attribute
            # support both 'factor_8' and 'factor8' keys coming from session
            alt_key = field_name.replace('_', '')
            if self.initial.get(field_name) is not None:
                val = self.initial.get(field_name)
            elif self.initial.get(alt_key) is not None:
                val = self.initial.get(alt_key)
            elif getattr(getattr(self, 'instance', None), field_name, None) is not None:
                val = getattr(self.instance, field_name)

            if val is not None:
                try:
                    v = Decimal(str(val)).quantize(Decimal('0.00000001'))
                    # Format with 8 decimal places to avoid scientific notation
                    formatted = format(v, '.8f')
                    self.fields[field_name].widget.attrs['value'] = formatted
                    # Also normalize initial so Django will render the formatted value
                    if self.initial is None:
                        self.initial = {}
                    self.initial[field_name] = formatted
                except Exception:
                    # If formatting fails, skip silently and let widget render default
                    pass
    
    class Meta:
        model = FactorCalificacion
        fields = [
            'factor_8', 'factor_9', 'factor_10', 'factor_11', 'factor_12',
            'factor_13', 'factor_14', 'factor_15', 'factor_16', 'factor_17',
            'factor_18', 'factor_19'
        ]
        widgets = {
            'factor_8': forms.TextInput(attrs={
                'class': 'form-control factor-input',
                'inputmode': 'decimal',
                'pattern': r'^[0-9]*\.?[0-9]+$',
                'data-step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_9': forms.TextInput(attrs={
                'class': 'form-control factor-input',
                'inputmode': 'decimal',
                'pattern': r'^[0-9]*\.?[0-9]+$',
                'data-step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_10': forms.TextInput(attrs={
                'class': 'form-control factor-input',
                'inputmode': 'decimal',
                'pattern': r'^[0-9]*\.?[0-9]+$',
                'data-step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_11': forms.TextInput(attrs={
                'class': 'form-control factor-input',
                'inputmode': 'decimal',
                'pattern': r'^[0-9]*\.?[0-9]+$',
                'data-step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_12': forms.TextInput(attrs={
                'class': 'form-control factor-input',
                'inputmode': 'decimal',
                'pattern': r'^[0-9]*\.?[0-9]+$',
                'data-step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_13': forms.TextInput(attrs={
                'class': 'form-control factor-input',
                'inputmode': 'decimal',
                'pattern': r'^[0-9]*\.?[0-9]+$',
                'data-step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_14': forms.TextInput(attrs={
                'class': 'form-control factor-input',
                'inputmode': 'decimal',
                'pattern': r'^[0-9]*\.?[0-9]+$',
                'data-step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_15': forms.TextInput(attrs={
                'class': 'form-control factor-input',
                'inputmode': 'decimal',
                'pattern': r'^[0-9]*\.?[0-9]+$',
                'data-step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_16': forms.TextInput(attrs={
                'class': 'form-control factor-input',
                'inputmode': 'decimal',
                'pattern': r'^[0-9]*\.?[0-9]+$',
                'data-step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_17': forms.TextInput(attrs={
                'class': 'form-control factor-input',
                'inputmode': 'decimal',
                'pattern': r'^[0-9]*\.?[0-9]+$',
                'data-step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_18': forms.TextInput(attrs={
                'class': 'form-control factor-input',
                'inputmode': 'decimal',
                'pattern': r'^[0-9]*\.?[0-9]+$',
                'data-step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_19': forms.TextInput(attrs={
                'class': 'form-control factor-input',
                'inputmode': 'decimal',
                'pattern': r'^[0-9]*\.?[0-9]+$',
                'data-step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        # Validate factors 8..16 (inclusive)
        factores_validar = [f'factor_{i}' for i in range(8, 17)]
        
        suma_factores = Decimal('0.00000000')
        
        for factor_field in factores_validar:
            valor = cleaned_data.get(factor_field)
            if valor is None:
                valor = Decimal('0.00000000')
            suma_factores += valor

        # Ensure individual factors are > 0 (no zeros or negatives allowed)
        for i in range(8, 20):
            fname = f'factor_{i}'
            if fname in cleaned_data and cleaned_data[fname] is not None:
                try:
                    v = Decimal(cleaned_data[fname])
                except Exception:
                    continue
                if v < Decimal('0'):
                    self.add_error(fname, forms.ValidationError('El factor no puede ser negativo'))

        if suma_factores > Decimal('1.00000000'):
            raise forms.ValidationError(
                f"La suma de los factores del 8 al 16 ({suma_factores:.8f}) "
                f"no puede ser mayor a 1.00000000"
            )
        
        # NO agregar suma_factores_8_16 a cleaned_data
        return cleaned_data

class FiltroCalificacionesForm(forms.Form):
    """Formulario para filtrar calificaciones en el mantenedor"""
    
    ejercicio = forms.IntegerField(
        required=False,
        label="Ejercicio",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 2024'
        })
    )
    
    mercado = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos')] + CalificacionTributaria.MERCADO_OPCIONES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    origen = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos')] + CalificacionTributaria.ORIGEN_OPCIONES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    instrumento = forms.CharField(
        required=False,
        label="Instrumento",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar instrumento...'
        })
    )



class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label='Correo Electrónico',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'tu.correo@empresa.com'
        })
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa tu contraseña'
        })
    )

class UsuarioForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control password-field', 'autocomplete': 'new-password'}),
        required=False
    )
    
    class Meta:
        model = Usuario
        fields = ['nombre', 'correo', 'rol', 'estado']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'rol': forms.Select(attrs={'class': 'form-control'}),
            'estado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
            self.generated_password = None
        else:
            # Generar contraseña segura aleatoria si no se proporcionó
            generated = get_random_string(12, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+")
            user.set_password(generated)
            # Guardar la contraseña generada en el formulario para que la vista la pueda mostrar
            self.generated_password = generated
        if commit:
            user.save()
        return user

    def clean_password(self):
        pwd = self.cleaned_data.get('password')
        if not pwd:
            return pwd
        # Reglas de seguridad: mínimo 8 caracteres, mayúscula, minúscula, dígito y símbolo
        if len(pwd) < 8:
            raise forms.ValidationError('La contraseña debe tener al menos 8 caracteres.')
        if not re.search(r'[A-Z]', pwd):
            raise forms.ValidationError('La contraseña debe contener al menos una letra mayúscula.')
        if not re.search(r'[a-z]', pwd):
            raise forms.ValidationError('La contraseña debe contener al menos una letra minúscula.')
        if not re.search(r'\d', pwd):
            raise forms.ValidationError('La contraseña debe contener al menos un número.')
        if not re.search(r'[!@#$%^&*()_\-+=\[\]{};:\"\\|,.<>\/?]', pwd):
            raise forms.ValidationError('La contraseña debe contener al menos un carácter especial.')
        return pwd
    
class CargaMasivaForm(forms.Form):
    """Formulario para carga masiva de calificaciones desde archivo"""
    TIPO_CARGA_OPCIONES = [
        ('factores', 'Factores (CSV con factores 8-37)'),
        ('montos', 'Montos (CSV con montos para calcular factores)'),
    ]
    
    tipo_carga = forms.ChoiceField(
        choices=TIPO_CARGA_OPCIONES,
        label="Tipo de Carga",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    archivo = forms.FileField(
        label="Archivo CSV/Excel",
        help_text="Seleccione el archivo con los datos de calificación",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls'
        })
    )
    
    sobrescribir = forms.BooleanField(
        required=False,
        initial=False,
        label="Sobrescribir registros existentes",
        help_text="Si está marcado, reemplazará registros existentes. Si no, los omitirá.",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class CustomPasswordResetForm(PasswordResetForm):
    """Formulario de restablecimiento de contraseña que busca usuarios por el campo `correo`."""

    # Indica al form qué atributo del usuario contiene el correo (por defecto 'email')
    email_field_name = 'correo'

    def get_users(self, email):
        """Generador de usuarios activos cuyo `correo` coincide (case-insensitive).
        Nuestro modelo usa `estado` en lugar de `is_active`, así que filtramos por ese campo."""
        UserModel = get_user_model()
        for user in UserModel._default_manager.filter(correo__iexact=email, estado=True):
            if user.has_usable_password():
                yield user

    def save(self, domain_override=None,
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.html',
             use_https=False, token_generator=default_token_generator,
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):
        """Genera el token/uid y envía el correo de restablecimiento usando `correo`."""
        email = self.cleaned_data.get('email')
        for user in self.get_users(email):
            # Use the `correo` field directly (compatibilidad con nuestro modelo)
            user_email = getattr(user, 'correo', None)
            if not user_email:
                continue

            if not domain_override and request is not None:
                current_site = get_current_site(request)
                site_name = current_site.name
                domain = current_site.domain
            else:
                domain = domain_override or ''
                site_name = domain

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)

            context = {
                'email': user_email,
                'domain': domain,
                'site_name': site_name,
                'uid': uid,
                'user': user,
                'token': token,
                'protocol': 'https' if use_https else 'http',
            }
            if extra_email_context:
                context.update(extra_email_context)

            self.send_mail(subject_template_name, email_template_name, context, from_email, user_email, html_email_template_name=html_email_template_name)