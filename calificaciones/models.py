from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

class CalificacionTributaria(models.Model):
    # Opciones para campos de selección
    MERCADO_OPCIONES = [
        ('ACN', 'Acciones'),
        ('CFI', 'CFI'),
        ('FON', 'Fondos Mutuos'),
    ]
    
    ORIGEN_OPCIONES = [
        ('corredor', 'Corredor'),
        ('sistema', 'Sistema'),
        ('archivo', 'Archivo Carga Masiva'),
    ]
    
    TIPO_SOCIEDAD_OPCIONES = [
        ('A', 'Abierta'),
        ('C', 'Cerrada'),
    ]

    # Campos básicos según la especificación
    ejercicio = models.IntegerField(
        verbose_name="Ejercicio Comercial",
        help_text="Año comercial"
    )
    
    mercado = models.CharField(
        max_length=3,
        choices=MERCADO_OPCIONES,
        verbose_name="Tipo de Mercado"
    )
    
    instrumento = models.CharField(
        max_length=50,
        verbose_name="Instrumento"
    )
    
    fecha_pago = models.DateField(
        verbose_name="Fecha de Pago del Dividendo"
    )
    
    secuencia_evento = models.IntegerField(
        verbose_name="Secuencia del Evento de Capital",
        default=10000,
        help_text="Secuencia superior a 10.000"
    )
    
    numero_dividendo = models.IntegerField(
        verbose_name="Número de Dividendo",
        default=0
    )
    
    descripcion = models.TextField(
        verbose_name="Descripción del Dividendo",
        blank=True,
        null=True
    )
    
    tipo_sociedad = models.CharField(
        max_length=1,
        choices=TIPO_SOCIEDAD_OPCIONES,
        verbose_name="Tipo de Sociedad"
    )
    
    valor_historico = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Valor Histórico",
        default=0,
        blank=True,
        null=True
    )
    
    acogido_isfut = models.BooleanField(
        verbose_name="Acogido a ISFUT/ISIFT",
        default=False
    )
    
    origen = models.CharField(
        max_length=20,
        choices=ORIGEN_OPCIONES,
        default='corredor',
        verbose_name="Origen de la Información"
    )
    
    factor_actualizacion = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        verbose_name="Factor de Actualización",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )

    # Factores del 8 al 37 según la especificación DJ 1949
    factor_8 = models.DecimalField(
        max_digits=9, 
        decimal_places=8,
        verbose_name="Con crédito por IDPC generados a contar del 01.01.2017",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    
    factor_9 = models.DecimalField(
        max_digits=9, 
        decimal_places=8,
        verbose_name="Con crédito por IDPC acumulados hasta el 31.12.2016",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    
    factor_10 = models.DecimalField(
        max_digits=9, 
        decimal_places=8,
        verbose_name="Con derecho a crédito por pago de IDPC voluntario",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    
    factor_11 = models.DecimalField(
        max_digits=9, 
        decimal_places=8,
        verbose_name="Sin derecho a crédito",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    
    factor_12 = models.DecimalField(
        max_digits=9, 
        decimal_places=8,
        verbose_name="Rentas provenientes del registro RAP y Diferencia Inicial de sociedad acogida al ex Art. 14 TER A) LIR",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    
    factor_13 = models.DecimalField(
        max_digits=9, 
        decimal_places=8,
        verbose_name="Otras rentas percibidas Sin Prioridad en su orden de imputación",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    
    factor_14 = models.DecimalField(
        max_digits=9, 
        decimal_places=8,
        verbose_name="Exceso Distribuciones Desproporcionadas (N°9 Art.14 A)",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    
    factor_15 = models.DecimalField(
        max_digits=9, 
        decimal_places=8,
        verbose_name="Utilidades afectadas con impuesto sustitutivo al FUT (ISFUT) Ley N°20.780",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    
    factor_16 = models.DecimalField(
        max_digits=9, 
        decimal_places=8,
        verbose_name="Rentas generadas hasta el 31.12.1983 y/o utilidades afectadas con impuesto sustitutivo al FUT (ISFUT) LEY N°21.210",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    
    factor_17 = models.DecimalField(
        max_digits=9, 
        decimal_places=8,
        verbose_name="Rentas Exentas de Impuesto Global Complementario (IGC) (Artículo 11, Ley 18.401), Afectas a Impuesto Adicional",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    
    factor_18 = models.DecimalField(
        max_digits=9, 
        decimal_places=8,
        verbose_name="Rentas Exentas de Impuesto Global Complementario (IGC) y/o Impuesto Adicional (IA)",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    
    factor_19 = models.DecimalField(
        max_digits=9, 
        decimal_places=8,
        verbose_name="Ingresos No Constitutivos de Renta",
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )

    # Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    usuario_creacion = models.CharField(max_length=100, blank=True, null=True)
    usuario_actualizacion = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Calificación Tributaria"
        verbose_name_plural = "Calificaciones Tributarias"
        unique_together = ['ejercicio', 'mercado', 'instrumento', 'secuencia_evento']
        ordering = ['-ejercicio', 'mercado', 'instrumento']

    def __str__(self):
        return f"{self.instrumento} - {self.ejercicio} - {self.get_mercado_display()}"

    def validar_suma_factores(self):
        """Valida que la suma de los factores del 8 al 16 no supere 1"""
        factores_sum = sum([
            self.factor_8, self.factor_9, self.factor_10, self.factor_11,
            self.factor_12, self.factor_13, self.factor_14, self.factor_15, self.factor_16
        ])
        return factores_sum <= Decimal('1.0')

    def save(self, *args, **kwargs):
        # Validación antes de guardar
        if not self.validar_suma_factores():
            raise ValueError("La suma de los factores del 8 al 16 no puede superar 1")
        super().save(*args, **kwargs)

class LogAuditoria(models.Model):
    ACCION_OPCIONES = [
        ('crear', 'Crear'),
        ('modificar', 'Modificar'),
        ('eliminar', 'Eliminar'),
        ('carga_masiva', 'Carga Masiva'),
    ]

    calificacion = models.ForeignKey(
        CalificacionTributaria, 
        on_delete=models.CASCADE,
        related_name='logs'
    )
    accion = models.CharField(max_length=20, choices=ACCION_OPCIONES)
    descripcion = models.TextField()
    usuario = models.CharField(max_length=100)
    fecha_accion = models.DateTimeField(auto_now_add=True)
    datos_anteriores = models.JSONField(blank=True, null=True)
    datos_nuevos = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name = "Log de Auditoría"
        verbose_name_plural = "Logs de Auditoría"
        ordering = ['-fecha_accion']

    def __str__(self):
        return f"{self.accion} - {self.calificacion} - {self.fecha_accion}"