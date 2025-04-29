import logging
from datetime import datetime
from backend.db_manager import DatabaseManager

# Creamos una instancia global de DatabaseManager
db = DatabaseManager()

def current_datetime():
    try:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logging.exception("Error en current_datetime")
        return "ERROR_DATETIME"

def split_countries(countries_str: str) -> str:
    if not countries_str.strip():
        return ""
    # Convierte cada país a mayúsculas y elimina espacios extras
    countries = [p.strip().upper() for p in countries_str.split(',') if p.strip()]
    return ','.join(countries)

def load_available_countries():
    try:
        cur = db.conn.cursor()
        cur.execute("SELECT nombre FROM paises")
        rows = cur.fetchall()
        return [row["nombre"] for row in rows]
    except Exception as e:
        logging.exception("Error al cargar países")
        return []

def add_new_country(country: str):
    try:
        countries = load_available_countries()
        country = country.upper().strip()
        if country not in countries:
            cur = db.conn.cursor()
            cur.execute("INSERT INTO paises (nombre) VALUES (?)", (country,))
            db.conn.commit()
            logging.info(f"Nuevo país agregado: {country}")
        return load_available_countries()
    except Exception as e:
        logging.exception("Error al agregar nuevo país")
        return load_available_countries()
