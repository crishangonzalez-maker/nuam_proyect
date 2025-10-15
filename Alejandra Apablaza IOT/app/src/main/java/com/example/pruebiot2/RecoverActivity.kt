package com.example.pruebiot2;

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity

class RecoverActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_recover)

        val correo = findViewById<EditText>(R.id.txtCorreoRecuperar)
        val btnEnviar = findViewById<Button>(R.id.btnCorreoRecuperacion)
        val btnVolver = findViewById<Button>(R.id.btnVolverLogin)

        // ✅ Al presionar "Enviar correo de recuperación"
        btnEnviar.setOnClickListener {
            val correoIngresado = correo.text.toString()

            if (correoIngresado.isNotEmpty()) {
                AlertDialog.Builder(this)
                    .setTitle("Correo enviado")
                    .setMessage("Se ha enviado un enlace de recuperación a: $correoIngresado")
                    .setPositiveButton("Aceptar") { dialog, _ -> dialog.dismiss() }
                    .show()
            } else {
                AlertDialog.Builder(this)
                    .setTitle("Error")
                    .setMessage("Por favor, ingresa un correo válido.")
                    .setPositiveButton("Aceptar") { dialog, _ -> dialog.dismiss() }
                    .show()
            }
        }

        // ✅ Botón para volver al login
        btnVolver.setOnClickListener {
            val intent = Intent(this, LoginActivity::class.java)
            startActivity(intent)
            finish()
        }
    }
}