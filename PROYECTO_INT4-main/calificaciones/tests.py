from django.test import TestCase
from .forms import CalificacionTributariaForm
from django.urls import reverse
from .models import Usuario
from django_otp.plugins.otp_totp.models import TOTPDevice


class CalificacionFormTests(TestCase):
	def test_fecha_pago_not_before_ejercicio(self):
		data = {
			'ejercicio': 2024,
			'mercado': 'ACN',
			'instrumento': 'TEST',
			'fecha_pago': '2023-12-31',
			'secuencia_evento': 10001,
			'numero_dividendo': 1,
			'origen': 'Sistema'
		}
		form = CalificacionTributariaForm(data)
		self.assertFalse(form.is_valid())
		self.assertIn('fecha_pago', form.errors)
		self.assertIn('no puede ser anterior', str(form.errors['fecha_pago']))

	def test_fecha_pago_on_or_after_start_allowed(self):
		data = {
			'ejercicio': 2024,
			'mercado': 'ACN',
			'instrumento': 'TEST',
			'fecha_pago': '2024-01-01',
			'secuencia_evento': 10001,
			'numero_dividendo': 1,
			'origen': 'Sistema'
		}
		form = CalificacionTributariaForm(data)
		self.assertTrue(form.is_valid())

	def test_factor_values_cannot_be_negative(self):
		# Build minimal valid calificacion data
		cal_data = {
			'ejercicio': 2024,
			'mercado': 'ACN',
			'instrumento': 'TEST',
			'fecha_pago': '2024-01-01',
			'secuencia_evento': 10001,
			'numero_dividendo': 1,
			'origen': 'Sistema'
		}
		# Create a factores form with a zero and negative factor
		from .forms import FactoresForm
		factores_data = {
			'factor_8': '0.00000000',
			'factor_9': '-0.00000001'
		}
		form = FactoresForm(data=factores_data)
		self.assertFalse(form.is_valid())
		# factor_8 (zero) is allowed, factor_9 (negative) should be an error
		self.assertNotIn('factor_8', form.errors)
		self.assertIn('factor_9', form.errors)

	def test_scientific_notation_is_normalized_in_bound_and_initial(self):
		from .forms import FactoresForm
		from decimal import Decimal

		# Bound data with scientific notation
		bound = {'factor_17': '0E-8', 'factor_18': '2E-8'}
		form_bound = FactoresForm(data=bound)
		# Data should be normalized into fixed 8-decimal strings
		self.assertEqual(form_bound.data.get('factor_17'), '0.00000000')
		self.assertEqual(form_bound.data.get('factor_18'), '0.00000002')

		# Initial values (e.g., from calculated factores) also normalized
		initial = {'factor_17': Decimal('0E-8'), 'factor_18': Decimal('2E-8')}
		form_initial = FactoresForm(initial=initial)
		# The rendered widget value should be the formatted string
		self.assertEqual(form_initial.initial.get('factor_17'), '0.00000000')
		self.assertEqual(form_initial.initial.get('factor_18'), '0.00000002')

	def test_mfa_disable_endpoint_works_without_changing_password(self):
		# Create a user and enable a confirmed TOTPDevice
		user = Usuario.objects.create_user(correo='mfa@example.com', password='testpass', nombre='MFA User')
		device = TOTPDevice.objects.create(user=user, name='default', confirmed=True)

		# Log in
		logged = self.client.login(correo='mfa@example.com', password='testpass')
		self.assertTrue(logged)

		# POST to disable MFA
		resp = self.client.post(reverse('mfa_disable'))
		# Should redirect back to perfil
		self.assertEqual(resp.status_code, 302)
		self.assertFalse(TOTPDevice.objects.filter(user=user, confirmed=True).exists())

	def test_perfil_page_renders_for_logged_in_user(self):
		user = Usuario.objects.create_user(correo='perfil@example.com', password='testpass', nombre='Perfil User')
		logged = self.client.login(correo='perfil@example.com', password='testpass')
		self.assertTrue(logged)
		resp = self.client.get('/perfil/')
		self.assertEqual(resp.status_code, 200)
