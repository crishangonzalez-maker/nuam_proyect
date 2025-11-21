from django.core.management.base import BaseCommand
from calificaciones.models import Usuario

class Command(BaseCommand):
    help = 'Arreglar superusers para que puedan acceder al admin'

    def handle(self, *args, **options):
        # Encontrar todos los usuarios que deberían ser superusers
        superusers = Usuario.objects.filter(correo__in=['admin@nuam.com', 'tu_correo@admin.com'])
        
        for user in superusers:
            user.is_superuser = True
            user.is_staff = True
            user.rol = 'Administrador'
            user.estado = True
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Superuser arreglado: {user.correo}')
            )