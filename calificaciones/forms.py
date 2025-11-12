from django import forms
from .models import CalificacionTributaria, Usuario, FactorCalificacion
from decimal import Decimal

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
    
    class Meta:
        model = FactorCalificacion
        fields = [
            'factor_8', 'factor_9', 'factor_10', 'factor_11', 'factor_12',
            'factor_13', 'factor_14', 'factor_15', 'factor_16', 'factor_17',
            'factor_18', 'factor_19'
        ]
        widgets = {
            'factor_8': forms.NumberInput(attrs={
                'class': 'form-control factor-input',
                'step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_9': forms.NumberInput(attrs={
                'class': 'form-control factor-input',
                'step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_10': forms.NumberInput(attrs={
                'class': 'form-control factor-input',
                'step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_11': forms.NumberInput(attrs={
                'class': 'form-control factor-input',
                'step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_12': forms.NumberInput(attrs={
                'class': 'form-control factor-input',
                'step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_13': forms.NumberInput(attrs={
                'class': 'form-control factor-input',
                'step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_14': forms.NumberInput(attrs={
                'class': 'form-control factor-input',
                'step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_15': forms.NumberInput(attrs={
                'class': 'form-control factor-input',
                'step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_16': forms.NumberInput(attrs={
                'class': 'form-control factor-input',
                'step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_17': forms.NumberInput(attrs={
                'class': 'form-control factor-input',
                'step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_18': forms.NumberInput(attrs={
                'class': 'form-control factor-input',
                'step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
            'factor_19': forms.NumberInput(attrs={
                'class': 'form-control factor-input',
                'step': '0.00000001',
                'min': '0',
                'max': '1'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        
        factores_validar = [
            'factor8', 'factor9', 'factor10', 'factor11', 'factor12',
            'factor13', 'factor14', 'factor15', 'factor16'
        ]
        
        suma_factores = Decimal('0.00000000')
        
        for factor_field in factores_validar:
            valor = cleaned_data.get(factor_field)
            if valor is None:
                valor = Decimal('0.00000000')
            suma_factores += valor

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