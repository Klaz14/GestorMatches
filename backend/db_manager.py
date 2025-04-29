import sqlite3
import logging

class DatabaseManager:
    def __init__(self, db_file="db.sqlite"):
        # Conecta (o crea) la BD
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        cur = self.conn.cursor()
        # Envios
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS envios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    monto REAL NOT NULL,
                    estado TEXT NOT NULL CHECK(estado IN ('DISPONIBLE','NO DISPONIBLE')),
                    fecha_hora TEXT NOT NULL
                )
            ''')
            logging.debug("Tabla 'envios' creada o existente.")
        except Exception:
            logging.exception("Error creando tabla 'envios'")

        # Países por envío
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS envio_paises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    envio_id INTEGER NOT NULL,
                    pais TEXT NOT NULL
                )
            ''')
            logging.debug("Tabla 'envio_paises' creada o existente.")
        except Exception:
            logging.exception("Error creando tabla 'envio_paises'")

        # Recepciones
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS recepciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    monto REAL NOT NULL,
                    estado TEXT NOT NULL CHECK(estado IN ('DISPONIBLE','NO DISPONIBLE')),
                    fecha_hora TEXT NOT NULL
                )
            ''')
            logging.debug("Tabla 'recepciones' creada o existente.")
        except Exception:
            logging.exception("Error creando tabla 'recepciones'")

        # Países por recepción
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS recepcion_paises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recepcion_id INTEGER NOT NULL,
                    pais TEXT NOT NULL
                )
            ''')
            logging.debug("Tabla 'recepcion_paises' creada o existente.")
        except Exception:
            logging.exception("Error creando tabla 'recepcion_paises'")

        # Matches potenciales (utilizables)
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS utilizables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    envio_id INTEGER NOT NULL REFERENCES envios(id),
                    recepcion_id INTEGER NOT NULL REFERENCES recepciones(id),
                    monto_envio REAL NOT NULL,
                    monto_recepcion REAL NOT NULL,
                    diferencia REAL NOT NULL,
                    estado TEXT NOT NULL CHECK(estado IN ('DISPONIBLE','NO DISPONIBLE')),
                    fecha_hora TEXT NOT NULL,
                    UNIQUE(envio_id, recepcion_id)
                )
            ''')
            logging.debug("Tabla 'utilizables' creada o existente.")
        except Exception:
            logging.exception("Error creando tabla 'utilizables'")

        # Pendientes
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS pendientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    envio_id INTEGER NOT NULL REFERENCES envios(id),
                    recepcion_id INTEGER NOT NULL REFERENCES recepciones(id),
                    fecha_hora TEXT NOT NULL
                )
            ''')
            logging.debug("Tabla 'pendientes' creada o existente.")
        except Exception:
            logging.exception("Error creando tabla 'pendientes'")

        # Concluidas
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS concluidas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    envio_id INTEGER NOT NULL,
                    recepcion_id INTEGER NOT NULL,
                    fecha_hora TEXT NOT NULL
                )
            ''')
            logging.debug("Tabla 'concluidas' creada o existente.")
        except Exception:
            logging.exception("Error creando tabla 'concluidas'")
            
        # Países (para guardar nuevos países)
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS paises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT UNIQUE NOT NULL
                )
            ''')
            logging.debug("Tabla 'paises' creada o existente.")
        except Exception:
            logging.exception("Error creando tabla 'paises'")
            
        try:
            cur.execute(
                "INSERT OR IGNORE INTO paises (nombre) VALUES (?), (?)",
                ("ARGENTINA", "USA")
            )
            logging.debug("Valores predeterminados en 'paises' insertados.")
        except Exception:
            logging.exception("Error insertando valores predeterminados en 'paises'")

        self.conn.commit()

    def close(self):
        self.conn.close()
        

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    db = DatabaseManager()
    print("¡Tablas inicializadas con éxito, Onii‑Chan! 💾")
    db.close()
