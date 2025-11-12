from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

class Usuario(models.Model):
    """Modelo USUARIO según estructura PostgreSQL"""
    ROL_OPCIONES = [
        ('Administrador', 'Administrador'),
        ('Analista', 'Analista'),
        ('Corredor', 'Corredor'),
        ('Auditor', 'Auditor'),
    ]
    
    nombre = models.CharField(max_length=100)
    correo = models.EmailField(max_length=150, unique=True)
    rol = models.CharField(max_length=20, choices=ROL_OPCIONES)
    contraseña_hash = models.CharField(max_length=255)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    estado = models.BooleanField(default=True)

    class Meta:
        db_table = 'USUARIO'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.nombre} ({self.rol})"

class ArchivoCarga(models.Model):
    """Modelo ARCHIVO_CARGA según estructura PostgreSQL"""
    TIPO_ARCHIVO_OPCIONES = [
        ('DJ1948', 'DJ1948'),
        ('CSV_FACTORES', 'CSV_FACTORES'),
    ]
    
    ESTADO_PROCESO_OPCIONES = [
        ('PENDIENTE', 'Pendiente'),
        ('PROCESADO', 'Procesado'),
        ('ERROR', 'Error'),
    ]
    
    id_archivo = models.AutoField(primary_key=True)
    nombre_archivo = models.CharField(max_length=255)
    tipo_archivo = models.CharField(max_length=15, choices=TIPO_ARCHIVO_OPCIONES)
    tamano = models.BigIntegerField(null=True, blank=True)
    usuario_carga = models.ForeignKey(Usuario, on_delete=models.RESTRICT)
    fecha_carga = models.DateTimeField(auto_now_add=True)
    estado_proceso = models.CharField(max_length=20, choices=ESTADO_PROCESO_OPCIONES, default='PENDIENTE')
    registros_procesados = models.IntegerField(default=0)
    registros_error = models.IntegerField(default=0)
    errores_detalle = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'ARCHIVO_CARGA'
        verbose_name = 'Archivo de Carga'
        verbose_name_plural = 'Archivos de Carga'

    def __str__(self):
        return f"{self.nombre_archivo} ({self.get_tipo_archivo_display()})"

class CalificacionTributaria(models.Model):
    """Modelo CALIFICACION_TRIBUTARIA según estructura PostgreSQL"""
    MERCADO_OPCIONES = [
        ('ACN', 'Acciones'),
        ('CFI', 'CFI'),
        ('Fondos_Mutuos', 'Fondos Mutuos'),
    ]
    
    ORIGEN_OPCIONES = [
        ('Sistema', 'Sistema'),
        ('Corredor', 'Corredor'),
        ('Carga_Masiva', 'Carga Masiva'),
    ]
    
    TIPO_SOCIEDAD_OPCIONES = [
        ('A', 'Abierta'),
        ('C', 'Cerrada'),
    ]

    # Campos principales
    id_calificacion = models.AutoField(primary_key=True)
    ejercicio = models.IntegerField()
    mercado = models.CharField(max_length=15, choices=MERCADO_OPCIONES)
    instrumento = models.CharField(max_length=50)
    fecha_pago = models.DateField()
    descripcion_dividendo = models.TextField(blank=True, null=True)
    secuencia_evento = models.IntegerField(null=True, blank=True)
    numero_dividendo = models.IntegerField(default=0)
    tipo_sociedad = models.CharField(max_length=1, choices=TIPO_SOCIEDAD_OPCIONES, blank=True, null=True)
    valor_historico = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    acogido_isfut = models.BooleanField(default=False)
    origen = models.CharField(max_length=15, choices=ORIGEN_OPCIONES)
    factor_actualizacion = models.DecimalField(
        max_digits=9, 
        decimal_places=8, 
        default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    
    # Campos de auditoría y relaciones
    usuario_creador = models.ForeignKey(Usuario, on_delete=models.RESTRICT)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    estado = models.BooleanField(default=True)

    class Meta:
        db_table = 'CALIFICACION_TRIBUTARIA'
        verbose_name = 'Calificación Tributaria'
        verbose_name_plural = 'Calificaciones Tributarias'
        unique_together = ['ejercicio', 'mercado', 'instrumento', 'secuencia_evento']
        ordering = ['-ejercicio', 'mercado', 'instrumento']

    def __str__(self):
        return f"{self.instrumento} - {self.ejercicio} - {self.get_mercado_display()}"

    def validar_suma_factores(self):
        """Valida que la suma de los factores del 8 al 16 no supere 1"""
        try:
            factores = self.factorcalificacion
            factores_sum = sum([
                factores.factor_8 or 0, factores.factor_9 or 0, factores.factor_10 or 0,
                factores.factor_11 or 0, factores.factor_12 or 0, factores.factor_13 or 0,
                factores.factor_14 or 0, factores.factor_15 or 0, factores.factor_16 or 0
            ])
            return factores_sum <= Decimal('1.0')
        except FactorCalificacion.DoesNotExist:
            return True

class FactorCalificacion(models.Model):
    """Modelo FACTOR_CALIFICACION según estructura PostgreSQL"""
    id_factor = models.AutoField(primary_key=True)
    id_calificacion = models.OneToOneField(
        CalificacionTributaria, 
        on_delete=models.CASCADE,
        related_name='factorcalificacion'
    )
    
    # Factores del 8 al 37
    factor_8 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_9 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_10 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_11 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_12 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_13 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_14 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_15 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_16 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_17 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_18 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_19 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_20 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_21 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_22 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_23 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_24 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_25 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_26 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_27 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_28 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_29 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_30 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_31 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_32 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_33 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_34 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_35 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_36 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    factor_37 = models.DecimalField(max_digits=9, decimal_places=8, null=True, blank=True)
    
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'FACTOR_CALIFICACION'
        verbose_name = 'Factor de Calificación'
        verbose_name_plural = 'Factores de Calificación'

    def clean(self):
        """Validación de que la suma de factores 8-16 no supere 1"""
        from django.core.exceptions import ValidationError
        
        factores_sum = sum([
            self.factor_8 or 0, self.factor_9 or 0, self.factor_10 or 0,
            self.factor_11 or 0, self.factor_12 or 0, self.factor_13 or 0,
            self.factor_14 or 0, self.factor_15 or 0, self.factor_16 or 0
        ])
        
        if factores_sum > Decimal('1.0'):
            raise ValidationError(
                f"La suma de los factores del 8 al 16 no puede superar 1. "
                f"Suma actual: {factores_sum:.8f}"
            )

class LogAuditoria(models.Model):
    """Modelo LOG_AUDITORIA según estructura PostgreSQL"""
    ACCION_OPCIONES = [
        ('CREATE', 'Crear'),
        ('UPDATE', 'Actualizar'),
        ('DELETE', 'Eliminar'),
        ('LOGIN', 'Inicio de Sesión'),
        ('CARGA_MASIVA', 'Carga Masiva'),
        ('LOGOUT', 'Cierre de Sesión'),
    ]
    
    id_log = models.AutoField(primary_key=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=50, choices=ACCION_OPCIONES)
    usuario_responsable = models.ForeignKey(Usuario, on_delete=models.RESTRICT)
    id_calificacion = models.ForeignKey(
        CalificacionTributaria, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    detalle = models.TextField(blank=True, null=True)
    ip_origen = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'LOG_AUDITORIA'
        verbose_name = 'Log de Auditoría'
        verbose_name_plural = 'Logs de Auditoría'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"{self.accion} - {self.usuario_responsable} - {self.fecha_hora}"