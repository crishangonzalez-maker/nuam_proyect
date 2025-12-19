import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nuam_project.settings')
django.setup()

from calificaciones.models import Usuario

# Lista de usuarios a crear
usuarios = [
    {
        'nombre': 'Gabitos',
        'correo': 'Gabriel.analista@nuam.com', 
        'password': '123',
        'rol': 'Analista'
    },
    {
        'nombre': 'Kryshan',
        'correo': 'Kryshan.auditor@nuam.com',
        'password': '123',
        'rol': 'Auditor'  
    },
    {
        'nombre': 'Diego',
        'correo': 'Diego.corredor@nuam.com',
        'password': '123',
        'rol': 'Corredor'
    },
    {
        'nombre': 'Ale',
        'correo': 'Ale.admin@nuam.com',
        'password': '123',
        'rol': 'Administrador',
        'is_staff': True
    }
]

for user_data in usuarios:
    try:
        usuario = Usuario.objects.create_user(**user_data)
        print(f"✅ {user_data['rol']} creado: {user_data['correo']}")
    except Exception as e:
        print(f"❌ Error creando {user_data['correo']}: {e}")

print("\n🎉 Usuarios de prueba creados exitosamente!")