import sqlite3

# Crear o conectar la base de datos
conn = sqlite3.connect("tareas.db")
cursor = conn.cursor()

# Crear tabla si no existe
cursor.execute("""
CREATE TABLE IF NOT EXISTS tareas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT,
    tipo TEXT,
    referencia TEXT,
    tiempo TEXT,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

def insertar_tarea(usuario, tipo, referencia, tiempo):
    conn = sqlite3.connect("tareas.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tareas (usuario, tipo, referencia, tiempo)
        VALUES (?, ?, ?, ?)
    """, (usuario, tipo, referencia, tiempo))
    conn.commit()
    conn.close()

def obtener_tareas():
    conn = sqlite3.connect("tareas.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tareas ORDER BY fecha DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows
