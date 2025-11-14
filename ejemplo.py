"""
Archivo para ingresar 3 ejemplos básicos a la base de datos
Ejecutar desde el shell de Django: python manage.py shell < ingresar_ejemplos.py
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
def ingresar_ejemplos_basicos():
    print("Ingresando 3 ejemplos básicos a la base de datos...")
    
    # 1. Crear un usuario administrador de ejemplo
    print("\n1. Creando usuario administrador...")
    try:
        admin, creado = Usuario.objects.get_or_create(
            correo='admin@ejemplo.com',
            defaults={
                'nombre': 'Administrador Ejemplo',
                'rol': 'Administrador',
                'is_staff': True
            }
        )
        if creado:
            admin.set_password('admin123')
            admin.save()
            print("✓ Usuario administrador creado")
        else:
            print("→ Usuario administrador ya existe")
    except Exception as e:
        print(f"✗ Error creando usuario: {e}")
        return
    
    # 2. Crear una calificación tributaria de ejemplo
    print("\n2. Creando calificación tributaria...")
    try:
        calificacion = CalificacionTributaria.objects.create(
            ejercicio=2024,
            mercado='ACN',
            instrumento='EJEMPLO_ACCION',
            fecha_pago=date(2024, 6, 15),
            descripcion_dividendo='Dividendo ejemplo para demostración',
            secuencia_evento=1,
            numero_dividendo=1,
            tipo_sociedad='A',
            valor_historico=Decimal('100.50'),
            acogido_isfut=False,
            origen='Sistema',
            factor_actualizacion=Decimal('0.85'),
            usuario_creador=admin
        )
        print("✓ Calificación tributaria creada")
    except Exception as e:
        print(f"✗ Error creando calificación: {e}")
        return
    
    # 3. Crear factores de calificación de ejemplo
    print("\n3. Creando factores de calificación...")
    try:
        factores = FactorCalificacion.objects.create(
            id_calificacion=calificacion,
            factor_8=Decimal('0.15'),
            factor_9=Decimal('0.12'),
            factor_10=Decimal('0.10'),
            factor_17=Decimal('0.25'),
            factor_18=Decimal('0.20')
        )
        print("✓ Factores de calificación creados")
    except Exception as e:
        print(f"✗ Error creando factores: {e}")
        return
    
    print("\n" + "="*50)
    print("✓ 3 EJEMPLOS INGRESADOS EXITOSAMENTE")
    print("="*50)
    print("\nResumen:")
    print(f"1. Usuario: {admin.nombre} ({admin.correo})")
    print(f"2. Calificación: {calificacion.instrumento} - {calificacion.ejercicio}")
    print(f"3. Factores: {factores.id_factor} para {calificacion.instrumento}")

if __name__ == "__main__":
    ingresar_ejemplos_basicos()