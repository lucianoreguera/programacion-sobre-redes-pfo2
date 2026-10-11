# ---------------------------------------------------------------------------
# Reguera, Luciano Oscar
# Comisión D
# 11-10-2026 
# ---------------------------------------------------------------------------

"""
Cliente de consola para la API de Gestión de Tareas.

Uso:
    python cliente.py                       # usa http://localhost:5000
    python cliente.py http://otro-host:5000 # usa otra URL

Dentro de cualquier operación, presionar Ctrl+C la cancela
y vuelve al menú sin realizar ningún cambio.
"""

import sys
from getpass import getpass

import requests

URL_BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:5000"
TIMEOUT = 5  # segundos


# ---------------------------------------------------------------------------
# Comunicación con la API
# ---------------------------------------------------------------------------

def llamar_api(metodo, ruta, json=None, auth=None):
    """Hace un pedido a la API. Devuelve (código HTTP, datos JSON) o (None, None) si falla la conexión."""
    try:
        resp = requests.request(metodo, URL_BASE + ruta, json=json, auth=auth, timeout=TIMEOUT)
    except requests.RequestException:
        print(f"\n❌ No se pudo conectar con el servidor en {URL_BASE}. ¿Está corriendo servidor.py?")
        return None, None
    try:
        datos = resp.json()
    except ValueError:
        datos = {}
    return resp.status_code, datos


def mostrar_error(datos):
    print(f"❌ {datos.get('error', 'Error inesperado')}")


# ---------------------------------------------------------------------------
# Entrada por teclado
# ---------------------------------------------------------------------------

def encabezado(titulo):
    print(f"\n--- {titulo} ---")
    print("    (Ctrl+C para cancelar y volver al menú)")


def pedir_texto(mensaje, obligatorio=True):
    while True:
        valor = input(mensaje).strip()
        if valor or not obligatorio:
            return valor
        print("   Este campo es obligatorio (Ctrl+C para cancelar).")


def pedir_contrasena(mensaje="Contraseña: "):
    # getpass oculta lo que se escribe; si la entrada no es una terminal (p. ej. redirigida), usa input.
    leer = getpass if sys.stdin.isatty() else input
    while True:
        valor = leer(mensaje)
        if valor:
            return valor
        print("   Este campo es obligatorio (Ctrl+C para cancelar).")


def confirmar(mensaje):
    """Pregunta s/n hasta obtener una respuesta válida. Devuelve True si la respuesta es 's'."""
    while True:
        valor = pedir_texto(f"{mensaje} (s/n): ").lower()
        if valor in ("s", "n"):
            return valor == "s"
        print("   Respondé 's' o 'n' (Ctrl+C para cancelar).")


# ---------------------------------------------------------------------------
# Acciones: usuarios
# ---------------------------------------------------------------------------

def registrarse():
    encabezado("Registro de usuario")
    usuario = pedir_texto("Usuario: ")
    while True:
        contrasena = pedir_contrasena()
        if pedir_contrasena("Repetir contraseña: ") == contrasena:
            break
        print("❌ Las contraseñas no coinciden. Probá de nuevo.")

    codigo, datos = llamar_api("POST", "/registro", json={"usuario": usuario, "contraseña": contrasena})
    if codigo == 201:
        print(f"✅ {datos['mensaje']}. Ya podés iniciar sesión.")
    elif codigo is not None:
        mostrar_error(datos)


def iniciar_sesion():
    """Devuelve la tupla (usuario, contraseña) si el login es correcto, o None."""
    encabezado("Iniciar sesión")
    usuario = pedir_texto("Usuario: ")
    contrasena = pedir_contrasena()

    codigo, datos = llamar_api("POST", "/login", json={"usuario": usuario, "contraseña": contrasena})
    if codigo == 200:
        print(f"✅ {datos['mensaje']}")
        return usuario, contrasena
    if codigo is not None:
        mostrar_error(datos)
    return None


# ---------------------------------------------------------------------------
# Acciones: tareas (requieren credenciales)
# ---------------------------------------------------------------------------

def obtener_tareas(auth):
    """Devuelve la lista de tareas del usuario, o None si hubo un error."""
    codigo, datos = llamar_api("GET", "/tareas", auth=auth)
    if codigo == 200:
        return datos["tareas"]
    if codigo is not None:
        mostrar_error(datos)
    return None


def marca(tarea):
    return "✔" if tarea["completada"] else " "


def elegir_tarea(auth):
    """Muestra las tareas y pide el ID de una hasta que sea válido. Devuelve la tarea, o None si no hay."""
    tareas = obtener_tareas(auth)
    if tareas is None:
        return None
    if not tareas:
        print("   No tenés tareas cargadas.")
        return None

    for t in tareas:
        print(f"   #{t['id']:<3} [{marca(t)}] {t['titulo']}")
    por_id = {t["id"]: t for t in tareas}
    while True:
        valor = pedir_texto("ID de la tarea: ")
        if valor.isdigit() and int(valor) in por_id:
            return por_id[int(valor)]
        print(f"   ❌ No existe una tarea con ID '{valor}'. Probá de nuevo (Ctrl+C para cancelar).")


def ver_tareas(auth):
    tareas = obtener_tareas(auth)
    if tareas is None:
        return

    print(f"\n--- Tareas de {auth[0]} ({len(tareas)}) ---")
    if not tareas:
        print("   No tenés tareas cargadas.")
        return
    for t in tareas:
        print(f"  [{marca(t)}] #{t['id']:<3} {t['titulo']}")
        if t["descripcion"]:
            print(f"          {t['descripcion']}")
        print(f"          creada: {t['creada_en']}")


def crear_tarea(auth):
    encabezado("Nueva tarea")
    titulo = pedir_texto("Título: ")
    descripcion = pedir_texto("Descripción (Enter para dejarla vacía): ", obligatorio=False)

    codigo, datos = llamar_api("POST", "/tareas", json={"titulo": titulo, "descripcion": descripcion}, auth=auth)
    if codigo == 201:
        print(f"✅ Tarea #{datos['id']} creada.")
    elif codigo is not None:
        mostrar_error(datos)


def cambiar_estado(auth):
    encabezado("Marcar tarea como completada / pendiente")
    tarea = elegir_tarea(auth)
    if tarea is None:
        return
    nuevo_estado = "pendiente" if tarea["completada"] else "completada"
    if not confirmar(f"¿Marcar '{tarea['titulo']}' como {nuevo_estado}?"):
        print("   Operación cancelada.")
        return

    codigo, datos = llamar_api("PUT", f"/tareas/{tarea['id']}", json={"completada": not tarea["completada"]}, auth=auth)
    if codigo == 200:
        print(f"✅ Tarea #{tarea['id']} marcada como {nuevo_estado}.")
    elif codigo is not None:
        mostrar_error(datos)


def editar_tarea(auth):
    encabezado("Editar tarea")
    tarea = elegir_tarea(auth)
    if tarea is None:
        return

    print("   (Enter para mantener el valor actual)")
    cambios = {}
    titulo = pedir_texto(f"Título [{tarea['titulo']}]: ", obligatorio=False)
    if titulo:
        cambios["titulo"] = titulo
    descripcion = pedir_texto(f"Descripción [{tarea['descripcion']}]: ", obligatorio=False)
    if descripcion:
        cambios["descripcion"] = descripcion
    if not cambios:
        print("   No se hicieron cambios.")
        return

    codigo, datos = llamar_api("PUT", f"/tareas/{tarea['id']}", json=cambios, auth=auth)
    if codigo == 200:
        print(f"✅ Tarea #{tarea['id']} actualizada.")
    elif codigo is not None:
        mostrar_error(datos)


def eliminar_tarea(auth):
    encabezado("Eliminar tarea")
    tarea = elegir_tarea(auth)
    if tarea is None:
        return
    if not confirmar(f"¿Seguro que querés eliminar '{tarea['titulo']}'?"):
        print("   Operación cancelada.")
        return

    codigo, datos = llamar_api("DELETE", f"/tareas/{tarea['id']}", auth=auth)
    if codigo == 200:
        print(f"✅ {datos['mensaje']}.")
    elif codigo is not None:
        mostrar_error(datos)


# ---------------------------------------------------------------------------
# Menús
# ---------------------------------------------------------------------------

def ejecutar(accion, *args):
    """Ejecuta una acción; si el usuario la cancela con Ctrl+C, vuelve al menú sin hacer nada."""
    try:
        return accion(*args)
    except KeyboardInterrupt:
        print("\n↩  Operación cancelada. Volviendo al menú.")
        return None


def menu_tareas(auth):
    """Menú para el usuario autenticado. Devuelve False si eligió salir del programa."""
    opciones = {
        "1": ver_tareas,
        "2": crear_tarea,
        "3": cambiar_estado,
        "4": editar_tarea,
        "5": eliminar_tarea,
    }
    while True:
        print(f"\n===== Tareas ({auth[0]}) =====")
        print("1. Ver mis tareas")
        print("2. Nueva tarea")
        print("3. Marcar completada / pendiente")
        print("4. Editar tarea")
        print("5. Eliminar tarea")
        print("6. Cerrar sesión")
        print("0. Salir")
        opcion = input("Opción: ").strip()

        if opcion in opciones:
            ejecutar(opciones[opcion], auth)
        elif opcion == "6":
            print("👋 Sesión cerrada.")
            return True
        elif opcion == "0":
            return False
        else:
            print("Opción inválida.")


def main():
    print("=========================================")
    print("   Sistema de Gestión de Tareas")
    print(f"   Servidor: {URL_BASE}")
    print("=========================================")

    while True:
        print("\n===== Menú principal =====")
        print("1. Registrarse")
        print("2. Iniciar sesión")
        print("0. Salir")
        opcion = input("Opción: ").strip()

        if opcion == "1":
            ejecutar(registrarse)
        elif opcion == "2":
            auth = ejecutar(iniciar_sesion)
            if auth and not menu_tareas(auth):
                break
        elif opcion == "0":
            break
        else:
            print("Opción inválida.")

    print("¡Hasta luego!")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n¡Hasta luego!")
