import os
import django
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Crear superuser personalizado para el modelo Usuario'

    def handle(self, *args, **options):
        # Configurar Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nuam_project.settings')
        django.setup()
        
        from calificaciones.models import Usuario
        
        # Verificar si ya existe
        if Usuario.objects.filter(correo='admin@nuam.com').exists():
            self.stdout.write(
                self.style.WARNING('El superuser admin@nuam.com ya existe')
            )
            return
        
        # Crear superuser
        superuser = Usuario.objects.create(
            nombre='Administrador Principal',
            correo='admin@nuam.com',
            rol='Administrador',
            is_staff=True,
            is_superuser=True,
            estado=True,
            is_active=True
        )
        superuser.set_password('admin123')
        superuser.save()
        
        self.stdout.write(
            self.style.SUCCESS('Superuser creado exitosamente: admin@nuam.com / admin123')
        )