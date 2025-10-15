package com.example.pruebiot2

import android.app.AlertDialog
import android.content.Intent
import android.os.Bundle
import android.widget.*
import androidx.appcompat.app.AppCompatActivity

class LoginActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login)

        val txtUser = findViewById<EditText>(R.id.etEmail)
        val txtPass = findViewById<EditText>(R.id.etPassword)
        val btnLogin = findViewById<Button>(R.id.btnLogin)
        val tvRecover = findViewById<TextView>(R.id.tvRecover)
        val tvRegister = findViewById<TextView>(R.id.tvRegister)

        btnLogin.setOnClickListener {
            val user = txtUser.text.toString()
            val pass = txtPass.text.toString()

            if (user.isNotEmpty() && pass.isNotEmpty()) {
                mostrarDialogo(
                    "Inicio exitoso",
                    "Bienvenido $user"
                )
            } else {
                mostrarDialogo(
                    "Error",
                    "Por favor, completa todos los campos."
                )
            }
        }

        tvRecover.setOnClickListener {
            startActivity(Intent(this, RecoverActivity::class.java))
        }

        tvRegister.setOnClickListener {
            startActivity(Intent(this, RegisterActivity::class.java))
        }
    }

    private fun mostrarDialogo(titulo: String, mensaje: String) {
        AlertDialog.Builder(this)
            .setTitle(titulo)
            .setMessage(mensaje)
            .setPositiveButton("OK", null)
            .show()
    }
}
