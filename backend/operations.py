import logging
import itertools
from datetime import datetime
from backend.db_manager import DatabaseManager

# Configurar logging
logging.basicConfig(level=logging.DEBUG)

# Instancia global de la base de datos
db = DatabaseManager()

# ——————————————————————————————
# Helpers y Validaciones
# ——————————————————————————————
def current_datetime() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def split_countries_list(countries_str: str) -> list:
    return [p.strip().upper() for p in countries_str.split(',') if p.strip()]

def check_duplicate_operation(monto: float, paises_str: str, tipo: str) -> bool:
    """
    Comprueba si ya existe una operación (envío o recepción) con mismo monto
    y mismo conjunto de países. Devuelve True si ya existe (duplicado).
    """
    paises_in = set(split_countries_list(paises_str))
    cur = db.conn.cursor()

    if tipo.lower() == "envio":
        cur.execute("SELECT id FROM envios WHERE monto = ?", (monto,))
        candidatos = [r["id"] for r in cur.fetchall()]
        for eid in candidatos:
            cur.execute("SELECT pais FROM envio_paises WHERE envio_id = ?", (eid,))
            existentes = {r["pais"] for r in cur.fetchall()}
            if existentes == paises_in:
                return True

    elif tipo.lower() == "recepcion":
        cur.execute("SELECT id FROM recepciones WHERE monto = ?", (monto,))
        candidatos = [r["id"] for r in cur.fetchall()]
        for rid in candidatos:
            cur.execute("SELECT pais FROM recepcion_paises WHERE recepcion_id = ?", (rid,))
            existentes = {r["pais"] for r in cur.fetchall()}
            if existentes == paises_in:
                return True

    return False



# ——————————————————————————————
# Gestión de Países
# ——————————————————————————————
def add_new_country(country: str):
    try:
        cur = db.conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO paises (nombre) VALUES (?)",
            (country.upper().strip(),)
        )
        db.conn.commit()
        logging.info(f"Nuevo país agregado: {country}")
    except Exception:
        logging.exception("Error en add_new_country")

# ——————————————————————————————
# Obtener Operaciones Disponibles
# ——————————————————————————————
def fetch_envios_disponibles() -> list:
    cur = db.conn.cursor()
    cur.execute("SELECT * FROM envios WHERE estado='DISPONIBLE'")
    return [dict(r) for r in cur.fetchall()]

def fetch_recepciones_disponibles() -> list:
    cur = db.conn.cursor()
    cur.execute("SELECT * FROM recepciones WHERE estado='DISPONIBLE'")
    return [dict(r) for r in cur.fetchall()]

# ——————————————————————————————
# Obtener Países de Cada Operación
# ——————————————————————————————
def fetch_paises_envio(envio_id: int) -> set:
    cur = db.conn.cursor()
    cur.execute("SELECT pais FROM envio_paises WHERE envio_id=?", (envio_id,))
    return {r['pais'] for r in cur.fetchall()}

def fetch_paises_recepcion(recepcion_id: int) -> set:
    cur = db.conn.cursor()
    cur.execute("SELECT pais FROM recepcion_paises WHERE recepcion_id=?", (recepcion_id,))
    return {r['pais'] for r in cur.fetchall()}

# ——————————————————————————————
# Matching Automático (60–140% o ±10000)
# ——————————————————————————————
def auto_match_pairings():
    try:
        cur = db.conn.cursor()
        envios = fetch_envios_disponibles()
        recepciones = fetch_recepciones_disponibles()
        for e in envios:
            paises_e = fetch_paises_envio(e['id'])
            for r in recepciones:
                paises_r = fetch_paises_recepcion(r['id'])
                # Filtro de país en común
                if not (paises_e & paises_r):
                    continue
                monto_e, monto_r = e['monto'], r['monto']
                ratio = monto_r / monto_e if monto_e else 0
                diff = abs(monto_e - monto_r)
                # Filtro de monto: ratio 0.6–1.4 OR diff <=10000
                if (0.6 <= ratio <= 1.4) or (diff <= 10000):
                    fecha = current_datetime()
                    cur.execute(
                        '''
                        INSERT OR IGNORE INTO utilizables
                        (envio_id, recepcion_id, monto_envio, monto_recepcion, diferencia, estado, fecha_hora)
                        VALUES (?, ?, ?, ?, ?, 'DISPONIBLE', ?)
                        ''',
                        (e['id'], r['id'], monto_e, monto_r, diff, fecha)
                    )
        db.conn.commit()
    except Exception:
        logging.exception("Error en auto_match_pairings")

# ——————————————————————————————
# CRUD de Envios/Recepciones
# ——————————————————————————————
def add_envio(monto: float, paises_str: str) -> int:
    try:
        cur = db.conn.cursor()
        fecha = current_datetime()
        cur.execute(
            "INSERT INTO envios (monto, estado, fecha_hora) VALUES (?, 'DISPONIBLE', ?)",
            (monto, fecha)
        )
        envio_id = cur.lastrowid
        for pais in split_countries_list(paises_str):
            cur.execute(
                "INSERT INTO envio_paises (envio_id, pais) VALUES (?, ?)",
                (envio_id, pais)
            )
        db.conn.commit()
        auto_match_pairings()
        return envio_id
    except Exception:
        logging.exception("Error en add_envio")
        return None


def add_recepcion(monto: float, paises_str: str) -> int:
    try:
        cur = db.conn.cursor()
        fecha = current_datetime()
        cur.execute(
            "INSERT INTO recepciones (monto, estado, fecha_hora) VALUES (?, 'DISPONIBLE', ?)",
            (monto, fecha)
        )
        recepcion_id = cur.lastrowid
        for pais in split_countries_list(paises_str):
            cur.execute(
                "INSERT INTO recepcion_paises (recepcion_id, pais) VALUES (?, ?)",
                (recepcion_id, pais)
            )
        db.conn.commit()
        auto_match_pairings()
        return recepcion_id
    except Exception:
        logging.exception("Error en add_recepcion")
        return None

# ——————————————————————————————
# Wrappers UI para Envios/Recepciones
# ——————————————————————————————
def add_envio_ui(monto: float, paises: str) -> str:
    try:
        envio_id = add_envio(monto, paises)
        if envio_id:
            return f"Operación de envío {envio_id} añadida."
        return "Error al agregar envío."
    except Exception:
        logging.exception("Error en add_envio_ui")
        return "Error al agregar envío."


def add_recepcion_ui(monto: float, paises: str) -> str:
    try:
        recepcion_id = add_recepcion(monto, paises)
        if recepcion_id:
            return f"Operación de recepción {recepcion_id} añadida."
        return "Error al agregar recepción."
    except Exception:
        logging.exception("Error en add_recepcion_ui")
        return "Error al agregar recepción."

# ——————————————————————————————
# Gestión de Matches
# ——————————————————————————————
def get_utilizables() -> list:
    """
    Devuelve todos los matches utilizables, incluyendo su estado.
    """
    try:
        cur = db.conn.cursor()
        cur.execute(
            """
            SELECT
                u.id,
                u.envio_id,
                u.recepcion_id,
                u.monto_envio,
                u.monto_recepcion,
                u.diferencia,
                u.estado,
                group_concat(ep.pais)   AS paises_envio,
                group_concat(rp.pais)   AS paises_recepcion,
                u.fecha_hora
            FROM utilizables u
            JOIN envio_paises    ep ON ep.envio_id    = u.envio_id
            JOIN recepcion_paises rp ON rp.recepcion_id = u.recepcion_id
            GROUP BY u.id
            """
        )
        return [dict(r) for r in cur.fetchall()]
    except Exception:
        logging.exception("Error en get_utilizables")
        return []



def get_available_matches() -> list:
    """
    Para cada envío DISPONIBLE, devuelve hasta 2 recepciones DISPONIBLES
    que cumplan país en común y filtro de monto.
    """
    resultado = []
    envios = fetch_envios_disponibles()
    recepciones = fetch_recepciones_disponibles()

    for e in envios:
        paises_e = fetch_paises_envio(e['id'])
        candidatas = []
        for r in recepciones:
            # 1) País en común?
            if not (paises_e & fetch_paises_recepcion(r['id'])):
                continue
            # 2) Filtro de monto
            me, mr = e['monto'], r['monto']
            ratio = mr / me if me else 0
            diff  = abs(me - mr)
            if (0.6 <= ratio <= 1.4) or (diff <= 10000):
                candidatas.append(r)
            if len(candidatas) >= 2:
                break

        if candidatas:
            resultado.append({
                "envio":      e,
                "candidatas": candidatas
            })

    return resultado



def reject_match_ui(match_id: int) -> str:
    try:
        cur = db.conn.cursor()
        cur.execute("DELETE FROM utilizables WHERE id = ?", (match_id,))
        db.conn.commit()
        return f"Match {match_id} rechazado exitosamente."
    except Exception:
        logging.exception("Error en reject_match_ui")
        return f"Error al rechazar match {match_id}."


def marcar_pendiente(envio_id: int, recepcion_id: int):
    """
    Inserta el pairing en 'pendientes', marca ambas operaciones
    como NO DISPONIBLE y borra el registro de 'utilizables'.
    """
    try:
        cur = db.conn.cursor()
        fecha = current_datetime()

        # 1) Insertar en pendientes
        cur.execute(
            "INSERT OR IGNORE INTO pendientes (envio_id, recepcion_id, fecha_hora) VALUES (?, ?, ?)",
            (envio_id, recepcion_id, fecha)
        )
        # 2) Actualizar estados de envío y recepción
        cur.execute("UPDATE envios      SET estado='NO DISPONIBLE' WHERE id=?", (envio_id,))
        cur.execute("UPDATE recepciones SET estado='NO DISPONIBLE' WHERE id=?", (recepcion_id,))
        # 3) Eliminar de utilizables
        cur.execute(
            "DELETE FROM utilizables WHERE envio_id=? AND recepcion_id=?",
            (envio_id, recepcion_id)
        )

        db.conn.commit()
    except Exception:
        logging.exception("Error en marcar_pendiente")



def confirm_match_ui(match_id: int) -> str:
    try:
        cur = db.conn.cursor()
        cur.execute("SELECT envio_id, recepcion_id FROM utilizables WHERE id = ?", (match_id,))
        row = cur.fetchone()
        if not row:
            return f"Match {match_id} no encontrado."
        enviar, recep = row['envio_id'], row['recepcion_id']
        marcar_pendiente(enviar, recep)
        return f"Match {match_id} marcado como pendiente."  
    except Exception:
        logging.exception("Error en confirm_match_ui")
        return f"Error al confirmar match {match_id}."


def get_prioritized_matches() -> list:
    matches = get_available_matches()
    for m in matches:
        m['Prioridad'] = 1
    matches.sort(key=lambda x: (-x['Prioridad'], x['id']))
    return matches[:5]


def get_pending_matches() -> list:
    """
    Devuelve matches pendientes con IDs, montos y países de envío y recepción.
    Evita duplicados de país usando DISTINCT.
    """
    try:
        cur = db.conn.cursor()
        cur.execute(
            """
            SELECT
                p.id                AS pending_id,
                e.id                AS envio_id,
                e.monto             AS monto_envio,
                GROUP_CONCAT(DISTINCT ep.pais) AS paises_envio,
                r.id                AS recepcion_id,
                r.monto             AS monto_recepcion,
                GROUP_CONCAT(DISTINCT rp.pais) AS paises_recepcion
            FROM pendientes p
            JOIN envios e           ON e.id = p.envio_id
            JOIN recepciones r      ON r.id = p.recepcion_id
            LEFT JOIN envio_paises  ep ON ep.envio_id    = e.id
            LEFT JOIN recepcion_paises rp ON rp.recepcion_id = r.id
            GROUP BY p.id
            ORDER BY p.id ASC
            """
        )
        return [dict(r) for r in cur.fetchall()]
    except Exception:
        logging.exception("Error en get_pending_matches")
        return []





def cerrar_concluida(envio_id: int, recepcion_id: int):
    try:
        cur = db.conn.cursor()
        fecha = current_datetime()

        cur.execute(
            "INSERT INTO concluidas (envio_id, recepcion_id, fecha_hora) VALUES (?, ?, ?)",
            (envio_id, recepcion_id, fecha)
        )
        # 1) Guardar en concluidas
        cur.execute(
            "INSERT INTO concluidas (envio_id, recepcion_id, fecha_hora) VALUES (?, ?, ?)",
            (envio_id, recepcion_id, fecha)
        )
        # 2) Actualizar estados a NO DISPONIBLE
        cur.execute("UPDATE envios      SET estado='NO DISPONIBLE' WHERE id=?", (envio_id,))
        cur.execute("UPDATE recepciones SET estado='NO DISPONIBLE' WHERE id=?", (recepcion_id,))

        # 3) Remover de pendientes
        cur.execute(
            "DELETE FROM pendientes WHERE envio_id=? AND recepcion_id=?",
            (envio_id, recepcion_id)
        )
        db.conn.commit()
    except Exception:
        logging.exception("Error en cerrar_concluida")



def cerrar_match_ui(match_id: int) -> str:
    try:
        cur = db.conn.cursor()
        cur.execute("SELECT envio_id, recepcion_id FROM pendientes WHERE id = ?", (match_id,))
        row = cur.fetchone()
        if not row:
            return f"Pendiente {match_id} no encontrado."
        enviar, recep = row['envio_id'], row['recepcion_id']
        cerrar_concluida(enviar, recep)
        return f"Match pendiente {match_id} cerrado y movido a concluidas."
    except Exception:
        logging.exception("Error en cerrar_match_ui")
        return f"Error al cerrar match pendiente {match_id}."

# ——————————————————————————————
# Generación de Reportes (adaptar según nuevo esquema)
# ——————————————————————————————
def generate_pdf_report_ui(mes: int) -> str:
    """
    Genera un PDF con envíos, recepciones y matches concluidos del mes/año dado.
    Verifica primero si hay datos; si no, informa y no genera PDF.
    Nombre: reporte_AAAA_MM.pdf y se abre automáticamente.
    """
    import os
    import subprocess
    from datetime import datetime
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table
    from reportlab.lib.styles import getSampleStyleSheet
    from backend.operations import fetch_paises_envio, fetch_paises_recepcion

    año = datetime.now().year
    mes_str = f"{mes:02d}"
    filename = f"reporte_{año}_{mes_str}.pdf"

    try:
        cur = db.conn.cursor()

        # --- 1) Consultas ---
        # Envíos
        cur.execute(
            "SELECT e.id, e.monto, e.fecha_hora, GROUP_CONCAT(ep.pais) AS paises "
            "FROM envios e "
            "LEFT JOIN envio_paises ep ON ep.envio_id = e.id "
            "WHERE strftime('%m', e.fecha_hora)=? "
            "GROUP BY e.id",
            (mes_str,)
        )
        envs = cur.fetchall()

        # Recepciones
        cur.execute(
            "SELECT r.id, r.monto, r.fecha_hora, GROUP_CONCAT(rp.pais) AS paises "
            "FROM recepciones r "
            "LEFT JOIN recepcion_paises rp ON rp.recepcion_id = r.id "
            "WHERE strftime('%m', r.fecha_hora)=? "
            "GROUP BY r.id",
            (mes_str,)
        )
        recs = cur.fetchall()

        # Concluidas
        cur.execute(
            "SELECT envio_id, recepcion_id, fecha_hora "
            "FROM concluidas "
            "WHERE strftime('%m', fecha_hora)=?",
            (mes_str,)
        )
        concl = cur.fetchall()

        # --- 2) Verificar datos ---
        if not envs and not recs and not concl:
            return f"No hay datos ni matches concluidos para {mes_str}/{año}. PDF no generado."

        # --- 3) Construir PDF ---
        doc = SimpleDocTemplate(filename)
        styles = getSampleStyleSheet()
        elements = []

        # Sección Envios
        elements.append(Paragraph("Envíos", styles['Heading2']))
        tabla_envs = [["ID","Monto","Fecha","Países"]]
        tabla_envs += [[e["id"], f"${e["monto"]:.2f}", e["fecha_hora"], e["paises"] or "N/A"] for e in envs]
        elements.append(Table(tabla_envs, hAlign='LEFT'))

        # Sección Recepciones
        elements.append(Paragraph("Recepciones", styles['Heading2']))
        tabla_recs = [["ID","Monto","Fecha","Países"]]
        tabla_recs += [[r["id"], f"${r["monto"]:.2f}", r["fecha_hora"], r["paises"] or "N/A"] for r in recs]
        elements.append(Table(tabla_recs, hAlign='LEFT'))

                # Sección Matches Concluidos
        elements.append(Paragraph("Matches Concluidos", styles['Heading2']))
        tabla_conc = [["ID Envío","ID Recepción","Fecha","País Operativo"]]
        # Usamos GROUP BY para evitar duplicados
        cur.execute(
            """
            SELECT envio_id, recepcion_id, MIN(fecha_hora) AS fecha_hora
            FROM concluidas
            WHERE strftime('%m', fecha_hora)=?
            GROUP BY envio_id, recepcion_id
            """,
            (mes_str,)
        )
        concl = cur.fetchall()
        for c in concl:
            eid, rid = c["envio_id"], c["recepcion_id"]
            pe = set(fetch_paises_envio(eid))
            pr = set(fetch_paises_recepcion(rid))
            comunes = ", ".join(sorted(pe & pr)) or "N/A"
            tabla_conc.append([eid, rid, c["fecha_hora"], comunes])
        elements.append(Table(tabla_conc, hAlign='LEFT'))


        # Generar
        doc.build(elements)

        # --- 4) Abrir automáticamente ---
        if os.name == 'nt':  # Windows
            os.startfile(filename)
        else:
            # Mac o Linux
            try:
                opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                subprocess.call([opener, filename])
            except Exception:
                pass

        return f"PDF generado y abierto: {os.path.abspath(filename)}"

    except Exception:
        logging.exception("Error generando PDF")
        return "Error al generar el PDF"



def modify_operacion_ui(op_id: int, new_monto_str: str, new_countries_str: str) -> str:
    """
    Actualiza monto y países de la operación (envío o recepción) con ID op_id.
    """
    try:
        cur = db.conn.cursor()
        # ¿Es envío?
        cur.execute("SELECT id FROM envios WHERE id = ?", (op_id,))
        if cur.fetchone():
            # Actualizar monto si se indicó
            if new_monto_str:
                monto = float(new_monto_str)
                cur.execute("UPDATE envios SET monto = ? WHERE id = ?", (monto, op_id))
            # Actualizar países si se indicó
            if new_countries_str.strip():
                cur.execute("DELETE FROM envio_paises WHERE envio_id = ?", (op_id,))
                for pais in split_countries_list(new_countries_str):
                    cur.execute(
                        "INSERT INTO envio_paises (envio_id, pais) VALUES (?, ?)",
                        (op_id, pais)
                    )
        else:
            # ¿Es recepción?
            cur.execute("SELECT id FROM recepciones WHERE id = ?", (op_id,))
            if cur.fetchone():
                if new_monto_str:
                    monto = float(new_monto_str)
                    cur.execute("UPDATE recepciones SET monto = ? WHERE id = ?", (monto, op_id))
                if new_countries_str.strip():
                    cur.execute("DELETE FROM recepcion_paises WHERE recepcion_id = ?", (op_id,))
                    for pais in split_countries_list(new_countries_str):
                        cur.execute(
                            "INSERT INTO recepcion_paises (recepcion_id, pais) VALUES (?, ?)",
                            (op_id, pais)
                        )
            else:
                return f"Operación {op_id} no encontrada."
        db.conn.commit()
        # Recalculamos matches si hace falta
        auto_match_pairings()
        return f"Operación {op_id} modificada exitosamente."
    except Exception:
        logging.exception("Error en modify_operacion_ui")
        return f"Error modificando operación {op_id}."

def get_last_operations(tipo: str, limit: int = 10) -> list:
    """
    Devuelve las últimas `limit` operaciones de tipo 'envio' o 'recepcion',
    con sus IDs, montos y países concatenados.
    """
    cur = db.conn.cursor()
    if tipo.lower() == "envio":
        cur.execute(
            """
            SELECT
              e.id          AS NumeroOperacion,
              e.monto       AS Monto,
              GROUP_CONCAT(ep.pais) AS PaisEnvio,
              e.fecha_hora
            FROM envios e
            LEFT JOIN envio_paises ep ON ep.envio_id = e.id
            GROUP BY e.id
            ORDER BY e.id DESC
            LIMIT ?
            """,
            (limit,)
        )
    else:  # recepcion
        cur.execute(
            """
            SELECT
              r.id          AS NumeroOperacion,
              r.monto       AS Monto,
              GROUP_CONCAT(rp.pais) AS PaisRecepcion,
              r.fecha_hora
            FROM recepciones r
            LEFT JOIN recepcion_paises rp ON rp.recepcion_id = r.id
            GROUP BY r.id
            ORDER BY r.id DESC
            LIMIT ?
            """,
            (limit,)
        )
    return [dict(r) for r in cur.fetchall()]

def reactivate_pending(envio_id: int, recepcion_id: int):
    """
    Elimina el match de 'pendientes' y marca envío/recepción como DISPONIBLE.
    """
    try:
        cur = db.conn.cursor()
        cur.execute(
            "DELETE FROM pendientes WHERE envio_id=? AND recepcion_id=?",
            (envio_id, recepcion_id)
        )
        cur.execute("UPDATE envios      SET estado='DISPONIBLE' WHERE id=?", (envio_id,))
        cur.execute("UPDATE recepciones SET estado='DISPONIBLE' WHERE id=?", (recepcion_id,))
        db.conn.commit()
    except Exception:
        logging.exception("Error en reactivate_pending")

