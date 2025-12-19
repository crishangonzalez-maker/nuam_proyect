from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from functools import wraps

def rol_requerido(roles_permitidos):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            if request.user.rol not in roles_permitidos:
                return HttpResponseForbidden("No tienes permisos para acceder a esta página")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

# Decoradores específicos para cada rol
def administrador_required(view_func):
    return rol_requerido(['Administrador'])(view_func)

def analista_required(view_func):
    return rol_requerido(['Administrador', 'Analista'])(view_func)

def auditor_required(view_func):
    return rol_requerido(['Administrador', 'Auditor'])(view_func)

def corredor_required(view_func):
    return rol_requerido(['Administrador', 'Corredor'])(view_func)

# NUEVO: Decorator para creación/edición (Admin, Analista, Corredor)
def editor_required(view_func):
    return rol_requerido(['Administrador', 'Analista', 'Corredor'])(view_func)

# NUEVO: Decorator para vistas de solo lectura (todos los roles)
def solo_lectura_required(view_func):
    return rol_requerido(['Administrador', 'Analista', 'Auditor', 'Corredor'])(view_func)