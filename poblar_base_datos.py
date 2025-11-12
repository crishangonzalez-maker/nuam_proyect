"""
Script para poblar la base de datos PostgreSQL con datos de ejemplo
NUAM - Calificaciones Tributarias
"""

import os
import django
import sys

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nuam_project.settings')
django.setup()

from calificaciones.models import Usuario, CalificacionTributaria, FactorCalificacion, LogAuditoria, ArchivoCarga
from django.contrib.auth.hashers import make_password
from decimal import Decimal
from datetime import date, datetime

def crear_usuarios_ejemplo():
    """Crear usuarios de ejemplo"""
    print("👥 Creando usuarios de ejemplo...")
    
    usuarios = [
        {
            'nombre': 'Eduardo Leiva Palomera',
            'correo': 'eduardo.leiva@nuam.com',
            'rol': 'Administrador',
            'contraseña_hash': make_password('admin123'),
            'estado': True
        },
        {
            'nombre': 'Valentina Labra',
            'correo': 'valentina.labra@nuam.com', 
            'rol': 'Analista',
            'contraseña_hash': make_password('analista123'),
            'estado': True
        },
        {
            'nombre': 'Carlos Corredor',
            'correo': 'carlos.corredor@nuam.com',
            'rol': 'Corredor',
            'contraseña_hash': make_password('corredor123'),
            'estado': True
        }
    ]
    
    for usuario_data in usuarios:
        usuario, created = Usuario.objects.get_or_create(
            correo=usuario_data['correo'],
            defaults=usuario_data
        )
        if created:
            print(f"✅ Usuario creado: {usuario.nombre} ({usuario.rol})")
        else:
            print(f"⚠️  Usuario ya existe: {usuario.nombre}")

def crear_calificaciones_ejemplo():
    """Crear calificaciones tributarias de ejemplo"""
    print("\n📊 Creando calificaciones tributarias de ejemplo...")
    
    # Obtener usuario administrador
    usuario_admin = Usuario.objects.get(correo='eduardo.leiva@nuam.com')
    
    calificaciones = [
        {
            'ejercicio': 2024,
            'mercado': 'ACN',
            'instrumento': 'COPEC',
            'fecha_pago': date(2024, 3, 15),
            'descripcion_dividendo': 'Dividendo ordinario primer trimestre 2024',
            'secuencia_evento': 10001,
            'numero_dividendo': 1,
            'tipo_sociedad': 'A',
            'valor_historico': Decimal('150.75'),
            'acogido_isfut': False,
            'origen': 'Corredor',
            'factor_actualizacion': Decimal('0.85'),
            'usuario_creador': usuario_admin,
            'estado': True
        },
        {
            'ejercicio': 2024,
            'mercado': 'ACN', 
            'instrumento': 'FALABELLA',
            'fecha_pago': date(2024, 6, 30),
            'descripcion_dividendo': 'Dividendo intermedio 2024',
            'secuencia_evento': 10002,
            'numero_dividendo': 1,
            'tipo_sociedad': 'A',
            'valor_historico': Decimal('280.50'),
            'acogido_isfut': True,
            'origen': 'Sistema',
            'factor_actualizacion': Decimal('0.92'),
            'usuario_creador': usuario_admin,
            'estado': True
        },
        {
            'ejercicio': 2023,
            'mercado': 'Fondos_Mutuos',
            'instrumento': 'FONDO_A',
            'fecha_pago': date(2023, 12, 20),
            'descripcion_dividendo': 'Distribución anual fondo mutuo',
            'secuencia_evento': 10003,
            'numero_dividendo': 1,
            'tipo_sociedad': 'C',
            'valor_historico': Decimal('85.20'),
            'acogido_isfut': False,
            'origen': 'Carga_Masiva',
            'factor_actualizacion': Decimal('0.78'),
            'usuario_creador': usuario_admin,
            'estado': True
        }
    ]
    
    for cal_data in calificaciones:
        # Verificar si ya existe
        exists = CalificacionTributaria.objects.filter(
            ejercicio=cal_data['ejercicio'],
            mercado=cal_data['mercado'],
            instrumento=cal_data['instrumento'],
            secuencia_evento=cal_data['secuencia_evento']
        ).exists()
        
        if not exists:
            calificacion = CalificacionTributaria.objects.create(**cal_data)
            print(f"✅ Calificación creada: {calificacion.instrumento} - {calificacion.ejercicio}")
            
            # Crear factores para esta calificación
            crear_factores_ejemplo(calificacion)
        else:
            print(f"⚠️  Calificación ya existe: {cal_data['instrumento']} - {cal_data['ejercicio']}")

def crear_factores_ejemplo(calificacion):
    """Crear factores de calificación de ejemplo"""
    print(f"   📈 Creando factores para {calificacion.instrumento}...")
    
    # Factores calculados según montos realistas
    factores_data = {
        'factor_8': Decimal('0.32423423'),  # Con crédito por IDPC generados a contar del 01.01.2017
        'factor_9': Decimal('0.10789123'),  # Con crédito por IDPC acumulados hasta el 31.12.2016
        'factor_10': Decimal('0.00000000'), # Con derecho a crédito por pago de IDPC voluntario
        'factor_11': Decimal('0.18812345'), # Sin derecho a crédito
        'factor_12': Decimal('0.11987654'), # Rentas provenientes del registro RAP...
        'factor_13': Decimal('0.05000000'), # Otras rentas percibidas...
        'factor_14': Decimal('0.03000000'), # Exceso Distribuciones Desproporcionadas...
        'factor_15': Decimal('0.08000000'), # Utilidades afectadas con ISFUT Ley 20.780
        'factor_16': Decimal('0.10000000'), # Rentas generadas hasta 31.12.1983...
        'factor_17': Decimal('0.00000000'),
        'factor_18': Decimal('0.00000000'),
        'factor_19': Decimal('0.00000000'),
        'id_calificacion': calificacion
    }
    
    # Verificar si ya existen factores
    if not hasattr(calificacion, 'factorcalificacion'):
        factores = FactorCalificacion.objects.create(**factores_data)
        print(f"   ✅ Factores creados para {calificacion.instrumento}")

def crear_logs_auditoria_ejemplo():
    """Crear logs de auditoría de ejemplo"""
    print("\n📝 Creando logs de auditoría de ejemplo...")
    
    usuario_admin = Usuario.objects.get(correo='eduardo.leiva@nuam.com')
    calificaciones = CalificacionTributaria.objects.all()
    
    logs = [
        {
            'accion': 'CREATE',
            'usuario_responsable': usuario_admin,
            'id_calificacion': calificaciones[0],
            'detalle': 'Creación inicial de calificación tributaria',
            'ip_origen': '192.168.1.100'
        },
        {
            'accion': 'LOGIN',
            'usuario_responsable': usuario_admin,
            'id_calificacion': None,
            'detalle': 'Inicio de sesión del usuario administrador',
            'ip_origen': '192.168.1.100'
        },
        {
            'accion': 'CARGA_MASIVA',
            'usuario_responsable': usuario_admin,
            'id_calificacion': calificaciones[2],
            'detalle': 'Carga masiva de factores desde archivo CSV',
            'ip_origen': '192.168.1.150'
        }
    ]
    
    for log_data in logs:
        log = LogAuditoria.objects.create(**log_data)
        print(f"✅ Log creado: {log.accion} - {log.fecha_hora}")

def crear_archivos_carga_ejemplo():
    """Crear archivos de carga de ejemplo"""
    print("\n📁 Creando archivos de carga de ejemplo...")
    
    usuario_admin = Usuario.objects.get(correo='eduardo.leiva@nuam.com')
    
    archivos = [
        {
            'nombre_archivo': 'factores_calificaciones_2024.csv',
            'tipo_archivo': 'CSV_FACTORES',
            'tamano': 102400,  # 100KB
            'usuario_carga': usuario_admin,
            'estado_proceso': 'PROCESADO',
            'registros_procesados': 150,
            'registros_error': 2,
            'errores_detalle': 'Línea 45: Formato de fecha inválido\nLínea 89: Instrumento no existe'
        },
        {
            'nombre_archivo': 'DJ1948_2023.xlsx',
            'tipo_archivo': 'DJ1948',
            'tamano': 512000,  # 500KB
            'usuario_carga': usuario_admin,
            'estado_proceso': 'PENDIENTE',
            'registros_procesados': 0,
            'registros_error': 0,
            'errores_detalle': ''
        }
    ]
    
    for archivo_data in archivos:
        archivo = ArchivoCarga.objects.create(**archivo_data)
        print(f"✅ Archivo creado: {archivo.nombre_archivo} ({archivo.get_tipo_archivo_display()})")

def mostrar_estadisticas():
    """Mostrar estadísticas de la base de datos"""
    print("\n" + "="*50)
    print("📊 ESTADÍSTICAS DE LA BASE DE DATOS")
    print("="*50)
    
    print(f"👥 Usuarios: {Usuario.objects.count()}")
    print(f"📊 Calificaciones: {CalificacionTributaria.objects.count()}")
    print(f"📈 Factores: {FactorCalificacion.objects.count()}")
    print(f"📝 Logs de auditoría: {LogAuditoria.objects.count()}")
    print(f"📁 Archivos de carga: {ArchivoCarga.objects.count()}")
    
    print("\n📋 Detalle de calificaciones:")
    for cal in CalificacionTributaria.objects.all():
        print(f"   - {cal.instrumento} ({cal.ejercicio}) - {cal.get_mercado_display()} - {cal.get_origen_display()}")

def main():
    """Función principal"""
    print("🚀 INICIANDO POBLADO DE BASE DE DATOS POSTGRESQL")
    print("="*60)
    
    try:
        # Ejecutar en orden
        crear_usuarios_ejemplo()
        crear_calificaciones_ejemplo()
        crear_logs_auditoria_ejemplo()
        crear_archivos_carga_ejemplo()
        mostrar_estadisticas()
        
        print("\n🎉 ¡BASE DE DATOS POBLADA EXITOSAMENTE!")
        print("\n🔗 Ahora puedes:")
        print("   - Acceder al admin: http://127.0.0.1:8000/admin/")
        print("   - Ver las calificaciones: http://127.0.0.1:8000/")
        print("   - Probar el flujo completo")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Asegúrate de que:")
        print("   - PostgreSQL esté funcionando")
        print("   - La base de datos 'nuam_calificaciones' exista")
        print("   - Las migraciones de Django estén aplicadas")

if __name__ == "__main__":
    main()