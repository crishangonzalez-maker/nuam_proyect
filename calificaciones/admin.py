from django.contrib import admin
from .models import Usuario, ArchivoCarga, CalificacionTributaria, FactorCalificacion, LogAuditoria

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'correo', 'rol', 'estado', 'fecha_creacion']
    list_filter = ['rol', 'estado']
    search_fields = ['nombre', 'correo']
    readonly_fields = ['fecha_creacion']

@admin.register(ArchivoCarga)
class ArchivoCargaAdmin(admin.ModelAdmin):
    list_display = ['nombre_archivo', 'tipo_archivo', 'usuario_carga', 'fecha_carga', 'estado_proceso']
    list_filter = ['tipo_archivo', 'estado_proceso', 'fecha_carga']
    readonly_fields = ['fecha_carga', 'id_archivo']
    search_fields = ['nombre_archivo']

@admin.register(CalificacionTributaria)
class CalificacionTributariaAdmin(admin.ModelAdmin):
    list_display = ['instrumento', 'ejercicio', 'mercado', 'fecha_pago', 'origen', 'usuario_creador', 'estado']
    list_filter = ['ejercicio', 'mercado', 'origen', 'estado']
    search_fields = ['instrumento', 'descripcion_dividendo']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion', 'id_calificacion']
    date_hierarchy = 'fecha_pago'

@admin.register(FactorCalificacion)
class FactorCalificacionAdmin(admin.ModelAdmin):
    list_display = ['id_calificacion', 'fecha_calculo']
    readonly_fields = ['fecha_calculo', 'id_factor']
    search_fields = ['id_calificacion__instrumento']

@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ['accion', 'usuario_responsable', 'fecha_hora', 'ip_origen']
    list_filter = ['accion', 'fecha_hora']
    readonly_fields = ['fecha_hora', 'id_log']
    search_fields = ['usuario_responsable__nombre', 'detalle']