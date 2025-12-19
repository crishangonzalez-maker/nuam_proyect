from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .decorators import editor_required
from .forms import CustomPasswordResetForm

urlpatterns = [
    # Autenticación
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views.perfil_usuario, name='perfil_usuario'),

    # Password reset (Django built-ins)
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='calificaciones/password_reset_form.html', form_class=CustomPasswordResetForm), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='calificaciones/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='calificaciones/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='calificaciones/password_reset_complete.html'), name='password_reset_complete'),
    
    # MFA URLs
    path('mfa/setup/', views.mfa_setup, name='mfa_setup'),
    path('mfa/verify/', views.mfa_verify, name='mfa_verify'),
    path('mfa/disable/', views.mfa_disable, name='mfa_disable'),
    
    # Gestión de usuarios (solo admin)
    path('usuarios/', views.gestion_usuarios, name='gestion_usuarios'),
    path('usuarios/crear/', views.crear_usuario, name='crear_usuario'),
    path('usuarios/editar/<int:user_id>/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/eliminar/<int:usuario_id>/', views.eliminar_usuario, name='eliminar_usuario'),
    
    # Calificaciones - Vistas accesibles para todos (solo lectura)
    path('', views.lista_calificaciones, name='lista_calificaciones'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('ver/<int:id_calificacion>/', views.detalle_calificacion, name='detalle_calificacion'),
    
    # Creación/Edición (Admin, Analista)
    path('crear/paso1/', views.crear_calificacion_paso1, name='crear_calificacion_paso1'),
    path('crear/paso2/', views.crear_calificacion_paso2, name='crear_calificacion_paso2'),
    path('crear/paso3/', views.crear_calificacion_paso3, name='crear_calificacion_paso3'),
    
    # Creación para Corredor
    path('crear/corredor/paso1/', views.crear_calificacion_corredor_paso1, name='crear_calificacion_corredor_paso1'),
    
    # Edición (Admin, Analista)
    path('editar/<int:id_calificacion>/paso1/', views.editar_calificacion_paso1, name='editar_calificacion_paso1'),
    path('editar/<int:id_calificacion>/paso2/', views.editar_calificacion_paso2, name='editar_calificacion_paso2'),
    path('editar/<int:id_calificacion>/paso3/', views.editar_calificacion_paso3, name='editar_calificacion_paso3'),
    
    # Eliminación (solo Admin)
    path('eliminar/<int:id_calificacion>/', views.eliminar_calificacion, name='eliminar_calificacion'),
    path('carga-masiva/', views.carga_masiva, name='carga_masiva'),
]