# ---------------------------------------------------------------------------
# Reguera, Luciano Oscar
# Comisión D
# 11-10-2026 
# ---------------------------------------------------------------------------

"""
Sistema de Gestión de Tareas - API REST con Flask + SQLite.

Endpoints:
    POST   /registro           Registra un usuario nuevo.
    POST   /login              Verifica credenciales.
    GET    /tareas             Lista las tareas del usuario (JSON o HTML).
    POST   /tareas             Crea una tarea.
    PUT    /tareas/<id>        Modifica una tarea.
    DELETE /tareas/<id>        Elimina una tarea.

Los endpoints de /tareas requieren autenticación HTTP Basic
(usuario y contraseña registrados).
"""

import sqlite3
from functools import wraps
from html import escape

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = "tareas.db"

app = Flask(__name__)
app.json.ensure_ascii = False  # Mostrar "ñ" y tildes tal cual en las respuestas


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

def get_db():
    """Devuelve la conexión SQLite de la petición actual (una por request)."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def cerrar_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Crea las tablas si no existen."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario       TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tareas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id  INTEGER NOT NULL,
                titulo      TEXT    NOT NULL,
                descripcion TEXT    NOT NULL DEFAULT '',
                completada  INTEGER NOT NULL DEFAULT 0,
                creada_en   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
            );
            """
        )


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def leer_credenciales():
    """Extrae usuario y contraseña del cuerpo JSON. Devuelve (usuario, contraseña) o None."""
    datos = request.get_json(silent=True) or {}
    usuario = str(datos.get("usuario", "")).strip()
    contrasena = str(datos.get("contraseña", ""))
    if not usuario or not contrasena:
        return None
    return usuario, contrasena


def verificar_usuario(usuario, contrasena):
    """Devuelve la fila del usuario si las credenciales son válidas, o None."""
    fila = get_db().execute(
        "SELECT id, usuario, password_hash FROM usuarios WHERE usuario = ?", (usuario,)
    ).fetchone()
    if fila and check_password_hash(fila["password_hash"], contrasena):
        return fila
    return None


def requiere_auth(f):
    """Decorador: exige autenticación HTTP Basic válida y deja el usuario en g.usuario."""
    @wraps(f)
    def envoltura(*args, **kwargs):
        auth = request.authorization
        usuario = None
        if auth and auth.type == "basic":
            usuario = verificar_usuario(auth.username or "", auth.password or "")
        if usuario is None:
            respuesta = jsonify({"error": "Credenciales inválidas o ausentes"})
            respuesta.status_code = 401
            # Hace que el navegador muestre el cuadro de usuario/contraseña
            respuesta.headers["WWW-Authenticate"] = 'Basic realm="Tareas", charset="UTF-8"'
            return respuesta
        g.usuario = usuario
        return f(*args, **kwargs)
    return envoltura


def tarea_a_dict(fila):
    return {
        "id": fila["id"],
        "titulo": fila["titulo"],
        "descripcion": fila["descripcion"],
        "completada": bool(fila["completada"]),
        "creada_en": fila["creada_en"],
    }


def obtener_tarea(tarea_id):
    """Busca una tarea del usuario autenticado (nunca de otro usuario)."""
    return get_db().execute(
        "SELECT * FROM tareas WHERE id = ? AND usuario_id = ?",
        (tarea_id, g.usuario["id"]),
    ).fetchone()


def pagina_bienvenida(usuario, tareas):
    """HTML simple que se muestra al abrir GET /tareas desde un navegador."""
    filas = "".join(
        f"<li>{'✅' if t['completada'] else '⬜'} <strong>{escape(t['titulo'])}</strong>"
        f"{' — ' + escape(t['descripcion']) if t['descripcion'] else ''}</li>"
        for t in tareas
    ) or "<li><em>Todavía no tenés tareas.</em></li>"
    return f"""<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>Mis tareas</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; }}
  h1 {{ color: #2c3e50; }}
  li {{ margin: 6px 0; }}
</style></head>
<body>
  <h1>¡Bienvenido/a, {escape(usuario)}!</h1>
  <p>Estas son tus tareas ({len(tareas)}):</p>
  <ul>{filas}</ul>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Endpoints: usuarios
# ---------------------------------------------------------------------------

@app.post("/registro")
def registro():
    credenciales = leer_credenciales()
    if credenciales is None:
        return jsonify({"error": "Se requieren 'usuario' y 'contraseña'"}), 400
    usuario, contrasena = credenciales

    db = get_db()
    try:
        db.execute(
            "INSERT INTO usuarios (usuario, password_hash) VALUES (?, ?)",
            (usuario, generate_password_hash(contrasena)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": f"El usuario '{usuario}' ya existe"}), 409

    return jsonify({"mensaje": f"Usuario '{usuario}' registrado correctamente"}), 201


@app.post("/login")
def login():
    credenciales = leer_credenciales()
    if credenciales is None:
        return jsonify({"error": "Se requieren 'usuario' y 'contraseña'"}), 400

    fila = verificar_usuario(*credenciales)
    if fila is None:
        return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

    return jsonify({
        "mensaje": f"Inicio de sesión exitoso. ¡Bienvenido/a, {fila['usuario']}!",
        "usuario": fila["usuario"],
    }), 200


# ---------------------------------------------------------------------------
# Endpoints: tareas
# ---------------------------------------------------------------------------

@app.get("/tareas")
@requiere_auth
def listar_tareas():
    filas = get_db().execute(
        "SELECT * FROM tareas WHERE usuario_id = ? ORDER BY id", (g.usuario["id"],)
    ).fetchall()
    tareas = [tarea_a_dict(f) for f in filas]

    # Desde un navegador se muestra la página de bienvenida; desde el cliente, JSON.
    if request.accept_mimetypes.best_match(["application/json", "text/html"]) == "text/html":
        return pagina_bienvenida(g.usuario["usuario"], tareas)
    return jsonify({"usuario": g.usuario["usuario"], "tareas": tareas})


@app.post("/tareas")
@requiere_auth
def crear_tarea():
    datos = request.get_json(silent=True) or {}
    titulo = str(datos.get("titulo", "")).strip()
    if not titulo:
        return jsonify({"error": "El campo 'titulo' es obligatorio"}), 400
    descripcion = str(datos.get("descripcion", "")).strip()

    db = get_db()
    cursor = db.execute(
        "INSERT INTO tareas (usuario_id, titulo, descripcion) VALUES (?, ?, ?)",
        (g.usuario["id"], titulo, descripcion),
    )
    db.commit()
    return jsonify(tarea_a_dict(obtener_tarea(cursor.lastrowid))), 201


@app.put("/tareas/<int:tarea_id>")
@requiere_auth
def actualizar_tarea(tarea_id):
    tarea = obtener_tarea(tarea_id)
    if tarea is None:
        return jsonify({"error": "Tarea no encontrada"}), 404

    datos = request.get_json(silent=True) or {}
    titulo = str(datos.get("titulo", tarea["titulo"])).strip()
    if not titulo:
        return jsonify({"error": "El campo 'titulo' no puede quedar vacío"}), 400
    descripcion = str(datos.get("descripcion", tarea["descripcion"])).strip()
    completada = int(bool(datos.get("completada", tarea["completada"])))

    db = get_db()
    db.execute(
        "UPDATE tareas SET titulo = ?, descripcion = ?, completada = ? WHERE id = ?",
        (titulo, descripcion, completada, tarea_id),
    )
    db.commit()
    return jsonify(tarea_a_dict(obtener_tarea(tarea_id)))


@app.delete("/tareas/<int:tarea_id>")
@requiere_auth
def eliminar_tarea(tarea_id):
    if obtener_tarea(tarea_id) is None:
        return jsonify({"error": "Tarea no encontrada"}), 404

    db = get_db()
    db.execute("DELETE FROM tareas WHERE id = ?", (tarea_id,))
    db.commit()
    return jsonify({"mensaje": f"Tarea {tarea_id} eliminada"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
