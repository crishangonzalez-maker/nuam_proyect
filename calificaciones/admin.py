from django.contrib import admin
from .models import CalificacionTributaria, LogAuditoria

@admin.register(CalificacionTributaria)
class CalificacionTributariaAdmin(admin.ModelAdmin):
    list_display = [
        'instrumento', 'ejercicio', 'mercado', 'fecha_pago', 
        'origen', 'acogido_isfut', 'fecha_creacion'
    ]
    list_filter = ['ejercicio', 'mercado', 'origen', 'acogido_isfut']
    search_fields = ['instrumento', 'descripcion']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    date_hierarchy = 'fecha_pago'

@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ['calificacion', 'accion', 'usuario', 'fecha_accion']
    list_filter = ['accion', 'fecha_accion']
    readonly_fields = ['fecha_accion']
    search_fields = ['usuario', 'calificacion__instrumento']