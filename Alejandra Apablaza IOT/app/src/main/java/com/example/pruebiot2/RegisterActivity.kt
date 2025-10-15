package com.example.pruebiot2

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import android.widget.Button
import android.widget.EditText
import androidx.appcompat.app.AlertDialog

class RegisterActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_register)

        // EditTexts
        val nombre = findViewById<EditText>(R.id.etName)
        val correo = findViewById<EditText>(R.id.etEmail)
        val clave = findViewById<EditText>(R.id.etPassword)

        // Botones
        val btnRegistrar = findViewById<Button>(R.id.btnRegister)
        val btnVolver = findViewById<Button>(R.id.btnVolver)

        // Acción de registrar
        btnRegistrar.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("Registro exitoso")
                .setMessage("Usuario ${nombre.text} registrado correctamente.")
                .setPositiveButton("Aceptar") { dialog, _ -> dialog.dismiss() }
                .show()
        }

        // Acción de volver al login
        btnVolver.setOnClickListener {
            val intent = Intent(this, LoginActivity::class.java)
            startActivity(intent)
            finish() // cerrar RegisterActivity
        }
    }
}
