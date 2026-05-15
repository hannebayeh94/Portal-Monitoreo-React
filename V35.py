import streamlit as st
import datetime
import json
import base64
import re
import hmac
import hashlib
import logging
import bcrypt
import mysql.connector
import pandas as pd
import string
from mysql.connector import pooling, Error
from jinja2 import Template
import smtplib
from email.message import EmailMessage

# Pydantic para validación segura
from pydantic import BaseModel, ValidationError

try:
    import modulo_reportes as reportes # Descomenta si tienes tu módulo de reportes
except ImportError:
    pass

st.set_page_config(page_title="Portal de Comunicados TI", layout="wide", page_icon="⚡")

# ==========================================
# 0. CONFIGURACIÓN INICIAL, SEGURIDAD Y PYDANTIC
# ==========================================

logging.basicConfig(
    filename='portal_ti.log', 
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

SECRET_KEY = b"super_secreta_llave_portal_ti_2024"

class SystemConfig(BaseModel):
    sla_horas: int
    correo_escalacion: str
    correo_seguridad: str

class AnalistaValidado(BaseModel):
    id: int
    nombre: str
    apellido: str
    correo: str
    rol: str
    estado: bool = True

# ==========================================
# 1. BASE DE DATOS (POOLING Y DAO)
# ==========================================

@st.cache_resource
def get_connection_pool():
    try:
        return pooling.MySQLConnectionPool(
            pool_name="portal_pool",
            pool_size=10,
            pool_reset_session=True,
            host='localhost',
            port=3306,
            user='root',
            password='123456789', # ⚠️ Cambia esto por tu contraseña
            database='react2' # 👈 Base de Datos
        )
    except Error as e:
        logging.error(f"Fallo crítico al crear Connection Pool: {e}")
        st.error("Error crítico de Base de Datos. Contacte al administrador.")
        st.stop()

class DBManager:
    @staticmethod
    def get_conn():
        try:
            return get_connection_pool().get_connection()
        except Error as e:
            logging.error(f"Error obteniendo conexión del pool: {e}")
            return None

    @staticmethod
    def fetch_all(query, params=None):
        conn = DBManager.get_conn()
        if not conn: return []
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Error BD en fetch_all: {e} | Query: {query}")
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def fetch_one(query, params=None):
        conn = DBManager.get_conn()
        if not conn: return None
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            return cursor.fetchone()
        except Error as e:
            logging.error(f"Error BD en fetch_one: {e} | Query: {query}")
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def execute(query, params=None):
        conn = DBManager.get_conn()
        if not conn: return False
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return True
        except Error as e:
            conn.rollback()
            logging.error(f"Error BD en execute: {e} | Query: {query}")
            return False
        finally:
            cursor.close()
            conn.close()

@st.cache_resource
def asegurar_columnas_dinamicas():
    check_query = """
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'comunicado' 
        AND COLUMN_NAME = 'html_cierre'
    """
    if not DBManager.fetch_one(check_query):
        logging.info("Agregando columnas html_cierre y asunto_cierre.")
        DBManager.execute("ALTER TABLE comunicado ADD COLUMN html_cierre TEXT")
        DBManager.execute("ALTER TABLE comunicado ADD COLUMN asunto_cierre VARCHAR(200)")

    check_rt = "SELECT COUNT(*) as count FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'regla_texto'"
    res_rt = DBManager.fetch_one(check_rt)
    if res_rt and res_rt['count'] > 0:
        check_t_id = "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'regla_texto' AND COLUMN_NAME = 'tercero_id'"
        if not DBManager.fetch_one(check_t_id):
            logging.info("Agregando columna tercero_id a regla_texto.")
            DBManager.execute("ALTER TABLE regla_texto ADD COLUMN tercero_id INT NULL")
            try: DBManager.execute("ALTER TABLE regla_texto ADD FOREIGN KEY (tercero_id) REFERENCES tercero(id)")
            except Exception as e: logging.error(f"No se pudo agregar FK: {e}")

@st.cache_resource
def asegurar_tablas_dinamicas():
    check_conf = "SELECT COUNT(*) as count FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'configuracion_sistema'"
    res_conf = DBManager.fetch_one(check_conf)
    if res_conf and res_conf['count'] == 0:
        logging.info("Creando tabla configuracion_sistema para el SLA dinámico.")
        DBManager.execute("""
            CREATE TABLE configuracion_sistema (
                id INT PRIMARY KEY,
                sla_horas INT NOT NULL,
                correo_escalacion VARCHAR(255) NOT NULL,
                correo_seguridad VARCHAR(255) NOT NULL
            )
        """)
        DBManager.execute("INSERT INTO configuracion_sistema (id, sla_horas, correo_escalacion, correo_seguridad) VALUES (1, 4, 'directores_ti@empresa.com', 'admin_seguridad@empresa.com')")

    check_reglas = "SELECT COUNT(*) as count FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'regla_texto'"
    res_reglas = DBManager.fetch_one(check_reglas)
    if res_reglas and res_reglas['count'] == 0:
        logging.info("Creando tabla regla_texto para el Motor de Reglas.")
        DBManager.execute("""
            CREATE TABLE regla_texto (
                id INT AUTO_INCREMENT PRIMARY KEY,
                plataforma_id INT NULL,
                servicio_id INT NULL,
                tercero_id INT NULL,
                tipo_comunicado_id INT NULL,
                fase VARCHAR(50) NOT NULL,
                entidad_afectada VARCHAR(255) NULL,
                asunto_template VARCHAR(255) NOT NULL,
                descripcion_template TEXT NOT NULL,
                estado TINYINT(1) DEFAULT 1,
                FOREIGN KEY (plataforma_id) REFERENCES plataforma(id),
                FOREIGN KEY (servicio_id) REFERENCES servicio(id),
                FOREIGN KEY (tercero_id) REFERENCES tercero(id),
                FOREIGN KEY (tipo_comunicado_id) REFERENCES tipo_comunicado(id)
            )
        """)
        # Obtener IDs básicos para semillar la tabla
        plat_gral = DBManager.fetch_one("SELECT id FROM plataforma WHERE UPPER(nombre) = 'GENERAL'")
        serv_gral = DBManager.fetch_one("SELECT id FROM servicio WHERE UPPER(nombre) = 'GENERAL'")
        plat_movii = DBManager.fetch_one("SELECT id FROM plataforma WHERE UPPER(nombre) = 'MOVII'")
        serv_movii = DBManager.fetch_one("SELECT id FROM servicio WHERE UPPER(nombre) = 'MOVII'")
        plat_moviired = DBManager.fetch_one("SELECT id FROM plataforma WHERE UPPER(nombre) = 'MOVIIRED'")
        serv_moviired = DBManager.fetch_one("SELECT id FROM servicio WHERE UPPER(nombre) = 'MOVIIRED'")
        plat_b2b = DBManager.fetch_one("SELECT id FROM plataforma WHERE UPPER(nombre) = 'B2B'")
        serv_b2b = DBManager.fetch_one("SELECT id FROM servicio WHERE UPPER(nombre) = 'B2B'")
        tipo_saldo = DBManager.fetch_one("SELECT id FROM tipo_comunicado WHERE UPPER(nombre) = 'SALDO'")

        reglas_iniciales = [
            (plat_gral['id'] if plat_gral else None, serv_gral['id'] if serv_gral else None, None, None, 'APERTURA', 'Movii y Moviired', '{consecutivo} - Comunicado Novedad Global - {plataforma}', 'Se informa que los servicios de {entidad} presentan novedad. La incidencia ya ha sido escalada. Una vez presente normalidad les informaremos. Agradecemos su comprensión.'),
            (plat_movii['id'] if plat_movii else None, serv_movii['id'] if serv_movii else None, None, None, 'APERTURA', 'Movii', '{consecutivo} - Comunicado Novedad Masiva - {plataforma}', 'Se informa que los servicios de {entidad} presentan novedad. La incidencia ha sido escalada.'),
            (plat_moviired['id'] if plat_moviired else None, serv_moviired['id'] if serv_moviired else None, None, None, 'APERTURA', 'Moviired', '{consecutivo} - Comunicado Novedad Masiva - {plataforma}', 'Se informa que los servicios de {entidad} presentan novedad. La incidencia ha sido escalada.'),
            (plat_b2b['id'] if plat_b2b else None, serv_b2b['id'] if serv_b2b else None, None, None, 'APERTURA', 'B2B', '{consecutivo} - Comunicado Novedad Masiva - {plataforma}', 'Se informa que los servicios de {entidad} presentan novedad. La incidencia ha sido escalada.'),
            (None, None, None, tipo_saldo['id'] if tipo_saldo else None, 'APERTURA', 'el cliente {tercero}', '{consecutivo} - Comunicado de novedad con {entidad} sin saldo', 'Se presenta novedad con {entidad} por saldo insuficiente. La novedad ha sido escalada, apenas tengamos un avance les estaremos informando.'),
            (None, None, None, tipo_saldo['id'] if tipo_saldo else None, 'CIERRE', '{tercero}', '{consecutivo} - Comunicado de normalidad con el cliente - {entidad}', 'Le informamos que el balance de la cuenta del cliente {entidad} ha sido actualizado con éxito. Ya puede continuar con sus operaciones de forma habitual.'),
            (None, None, None, None, 'APERTURA', 'la entidad {tercero}', '{consecutivo} Comunicado de Novedad con {servicio} {tercero}', 'Se informa que {entidad} presenta novedad en el servicio de {servicio}. La incidencia ya ha sido escalada. Una vez presente normalidad les informaremos. Agradecemos su comprensión.'),
            (None, None, None, None, 'CIERRE', '{tercero}', '{consecutivo} Comunicado de Normalidad con {servicio} {tercero}', 'El servicio de {servicio} ha sido restablecido y opera con normalidad.'),
            (None, None, None, None, 'MANTENIMIENTO', '{tercero}', '{consecutivo} - Comunicado de Ventana de Mantenimiento con {servicio} {tercero}', 'Se realizará una actualización en el core del sistema para mejorar el rendimiento y la seguridad.'),
            (None, None, None, None, 'FIN_MANTENIMIENTO', '{tercero}', '{consecutivo} - Fin de Ventana de Mantenimiento con {servicio} {tercero}', 'La ventana de mantenimiento ha concluido con éxito. Todos los sistemas están operando de manera óptima.')
        ]

        query_ins = "INSERT INTO regla_texto (plataforma_id, servicio_id, tercero_id, tipo_comunicado_id, fase, entidad_afectada, asunto_template, descripcion_template) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        for r in reglas_iniciales:
            DBManager.execute(query_ins, r)

asegurar_columnas_dinamicas()
asegurar_tablas_dinamicas()

@st.cache_data(ttl=60)
def get_system_config():
    config_db = DBManager.fetch_one("SELECT sla_horas, correo_escalacion, correo_seguridad FROM configuracion_sistema WHERE id = 1")
    if not config_db:
        default_config = {'sla_horas': 4, 'correo_escalacion': 'directores_ti@empresa.com', 'correo_seguridad': 'admin_seguridad@empresa.com'}
        return SystemConfig(**default_config).model_dump()
    try:
        config_valida = SystemConfig(**config_db)
        return config_valida.model_dump()
    except ValidationError as e:
        return {'sla_horas': 4, 'correo_escalacion': 'directores_ti@empresa.com', 'correo_seguridad': 'admin_seguridad@empresa.com'}

# ==========================================
# MOTOR DE REGLAS (SAFE FORMAT)
# ==========================================

class SafeDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'

def format_seguro(template_str, **kwargs):
    if not template_str: return ""
    formatter = string.Formatter()
    return formatter.vformat(template_str, (), SafeDict(**kwargs))

def evaluar_regla(plat_id, serv_id, tipo_id, fase, terc_id=None):
    query = """
        SELECT * FROM regla_texto 
        WHERE fase = %s AND estado = 1
        AND (plataforma_id = %s OR plataforma_id IS NULL)
        AND (servicio_id = %s OR servicio_id IS NULL)
        AND (tipo_comunicado_id = %s OR tipo_comunicado_id IS NULL)
        AND (tercero_id = %s OR tercero_id IS NULL)
        ORDER BY 
            (plataforma_id IS NOT NULL) DESC,
            (servicio_id IS NOT NULL) DESC,
            (tercero_id IS NOT NULL) DESC,
            (tipo_comunicado_id IS NOT NULL) DESC
        LIMIT 1
    """
    regla = DBManager.fetch_one(query, (fase, plat_id, serv_id, tipo_id, terc_id))
    if not regla:
        return {
            'entidad_afectada': 'la entidad {tercero}',
            'asunto_template': '{consecutivo} - Comunicado sobre {servicio}',
            'descripcion_template': 'Notificación del servicio {servicio} para {entidad}.'
        }
    return regla

# ==========================================
# LÓGICA DE AUDITORÍA Y SLA 
# ==========================================
def registrar_auditoria(analista_id, accion, detalles):
    query = "INSERT INTO audit_log (analista_id, accion, detalles) VALUES (%s, %s, %s)"
    DBManager.execute(query, (analista_id, accion, detalles))
    if accion in ['ADMIN_CRITICO', 'SEGURIDAD', 'ADMIN_REGLAS']:
        config = get_system_config()
        html_alerta = f"<h3>Alerta de Seguridad - Portal TI</h3><p><b>Acción:</b> {detalles}</p><p><b>Usuario ID:</b> {analista_id}</p><p><b>Fecha:</b> {datetime.datetime.now()}</p>"
        enviar_correo(config['correo_seguridad'], "⚠️ Alerta Crítica - Modificación en Portal TI", html_alerta, is_intern=True)

@st.cache_data(ttl=300, show_spinner=False) 
def revisar_y_escalar_slas():
    config = get_system_config()
    sla_horas = config['sla_horas']
    
    query = f"""
        SELECT id, consecutivo_num, asunto_final, fecha_creacion, servicio_id 
        FROM comunicado 
        WHERE estado = 'Abierto' AND escalado = FALSE 
        AND TIMESTAMPDIFF(HOUR, fecha_creacion, NOW()) >= {sla_horas}
    """
    incidentes_vencidos = DBManager.fetch_all(query)
    
    for inc in incidentes_vencidos:
        asunto_esc = f"🔥 ESCALACIÓN SLA: Incidente {inc['consecutivo_num']} supera {sla_horas} horas"
        html_esc = f"""
        <h3>Aviso Automático de Escalación</h3>
        <p>El incidente <b>{inc['consecutivo_num']}</b> ({inc['asunto_final']}) ha superado el tiempo máximo de resolución de {sla_horas} horas.</p>
        <p><b>Fecha de Apertura:</b> {inc['fecha_creacion']}</p>
        <p>Por favor, revisar el estado de este caso inmediatamente.</p>
        """
        exito, _ = enviar_correo(config['correo_escalacion'], asunto_esc, html_esc, is_intern=True)
        if exito:
            DBManager.execute("UPDATE comunicado SET escalado = TRUE WHERE id = %s", (inc['id'],))
            registrar_auditoria(None, 'SISTEMA_SLA', f"Incidente {inc['consecutivo_num']} escalado automáticamente.")

# ==========================================
# GESTIÓN DE SESIÓN, PASSWORDS Y COLAS TOAST
# ==========================================
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'toasts' not in st.session_state: st.session_state['toasts'] = []

def generar_token_seguro(uid):
    uid_str = str(uid)
    firma = hmac.new(SECRET_KEY, uid_str.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{uid_str}:{firma}".encode()).decode()

def validar_token_seguro(token_b64):
    try:
        decodificado = base64.urlsafe_b64decode(token_b64).decode()
        uid_str, firma_recibida = decodificado.split(':')
        firma_esperada = hmac.new(SECRET_KEY, uid_str.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(firma_recibida, firma_esperada): return uid_str
    except Exception: pass
    return None

def verificar_password(plain_password, stored_password):
    try: return bcrypt.checkpw(plain_password.encode('utf-8'), stored_password.encode('utf-8'))
    except ValueError: return plain_password == stored_password

def hash_password(plain_password):
    return bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

token = st.query_params.get("session_token")
if not st.session_state.get('logged_in') and token:
    uid_seguro = validar_token_seguro(token)
    if uid_seguro:
        usr = DBManager.fetch_one("SELECT id, nombre, apellido, correo, rol FROM analista WHERE id = %s AND estado = TRUE", (uid_seguro,))
        if usr:
            try:
                user_valido = AnalistaValidado(**usr)
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = user_valido.model_dump()
            except ValidationError: pass

if st.session_state.get('logged_in') and st.session_state.get('user_info'):
    st.query_params["session_token"] = generar_token_seguro(st.session_state['user_info']['id'])


st.markdown(
    """
    <style>
    /* 🎨 VARIABLES */
    :root {
        --rojo-purpureo: #d51b5d;
        --picton-blue: #2bbcee;
        --cetacean-blue: #10004F;
        --bg-light: #F8F9FA;
    }
    
    h1, h2, h3, h5, h6 { color: var(--cetacean-blue) !important; font-weight: 700 !important; }
    label { color: var(--cetacean-blue) !important; font-weight: 600 !important; }

    /* Estilos de st.metric nativo */
    [data-testid="stMetricValue"] { color: var(--cetacean-blue) !important; font-weight: 800 !important; font-size: 2.2rem !important;}
    [data-testid="stMetricLabel"] { color: rgba(16, 0, 79, 0.7) !important; font-weight: 600 !important; font-size: 1.1rem !important;}
    
    hr {
        border-top: 1px solid rgba(16, 0, 79, 0.1) !important;
        margin: 2.5em 0 !important;
    }
    
    [data-testid="stForm"] {
        background-color: #FFFFFF !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 2.5rem 2rem !important;
        box-shadow: 0 4px 24px rgba(16, 0, 79, 0.06) !important;
    }

    div[data-baseweb="input"] > div, 
    div[data-baseweb="textarea"] > div, 
    div[data-baseweb="select"] > div { 
        background-color: var(--bg-light) !important; 
        border: 1px solid rgba(16, 0, 79, 0.15) !important; 
        border-radius: 8px !important; 
        box-shadow: none !important;
        transition: all 0.3s ease;
        padding: 2px 6px;
    }
    
    div[data-baseweb="input"] > div:focus-within, 
    div[data-baseweb="textarea"] > div:focus-within, 
    div[data-baseweb="select"] > div:focus-within {
        border-color: var(--rojo-purpureo) !important;
        box-shadow: 0 0 0 3px rgba(213, 27, 93, 0.15) !important;
        background-color: #FFFFFF !important;
    }
    
    [data-testid="stDataFrame"] > div {
        background-color: #FFFFFF !important;
        border: 1px solid rgba(16, 0, 79, 0.1) !important;
        border-radius: 8px !important;
        padding: 0 !important;
        box-shadow: 0 2px 12px rgba(16, 0, 79, 0.04) !important;
    }

    section[data-testid="stSidebar"] > div > div {
        display: flex !important;
        flex-direction: column !important;
    }
    
    div[data-testid="stSidebarUserContent"] {
        order: 1 !important;
        padding-top: 1.5rem !important;
    }

    div[data-testid="stSidebarNav"] {
        order: 3 !important;
        padding-top: 1rem !important;
    }
    
    div[data-testid="stSidebarHeader"] {
        order: 0 !important;
    }

    [data-testid="stSidebarNav"] [aria-current="page"] {
        background-color: var(--rojo-purpureo) !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 12px rgba(213, 27, 93, 0.3) !important;
    }
    
    [data-testid="stSidebarNav"] [aria-current="page"] span,
    [data-testid="stSidebarNav"] [aria-current="page"] p {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.2);
    }
    
    [data-testid="stSidebarNav"] [aria-current="page"] svg {
        fill: #FFFFFF !important;
        color: #FFFFFF !important;
    }
    
    [data-testid="stSidebarNav"] a:not([aria-current="page"]):hover {
        background-color: rgba(213, 27, 93, 0.08) !important;
        border-radius: 10px !important;
    }
    
    [data-testid="stSidebarNav"] a {
        transition: all 0.25s ease;
    }

    /* Estilo especial para la caja de preview */
    .preview-box {
        background-color: #F8F9FA;
        border-left: 4px solid #d51b5d;
        padding: 20px;
        border-radius: 8px;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
        height: 100%;
    }
    </style>
    """, 
    unsafe_allow_html=True
)

if st.session_state['toasts']:
    for t in st.session_state['toasts']: 
        st.toast(t['msg'], icon=t.get('icon', '✔️'))
    st.session_state['toasts'].clear()

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
def formatear_fecha_es(fecha_obj, hora_obj=None):
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    fecha_str = f"{fecha_obj.day:02d} {meses[fecha_obj.month - 1]} {fecha_obj.year}"
    if hora_obj: return f"{fecha_str} - {hora_obj.strftime('%I:%M %p')} (COT)"
    return fecha_str

def calcular_tiempo_transcurrido(inicio, fin):
    diff = fin - inicio
    total_segundos = int(diff.total_seconds())
    if total_segundos < 0: return "Error en fechas"
    if total_segundos < 60: return "Menos de 1 minuto"
    horas, minutos = total_segundos // 3600, (total_segundos % 3600) // 60
    texto = []
    if horas > 0: texto.append(f"{horas} hora{'s' if horas != 1 else ''}")
    if minutos > 0: texto.append(f"{minutos} minuto{'s' if minutos != 1 else ''}")
    return ", ".join(texto)

def calcular_estado_sla(fecha_creacion, sla_horas):
    if not isinstance(fecha_creacion, datetime.datetime): return "⚪ N/A"
    horas_pasadas = (datetime.datetime.now() - fecha_creacion).total_seconds() / 3600
    if horas_pasadas >= sla_horas: return "🔴 Incumplido"
    if horas_pasadas >= (sla_horas * 0.75): return "🟡 En Riesgo"
    return "🟢 A tiempo"

def mostrar_vista_previa(html_str, height=550):
    b64_html = base64.b64encode(html_str.encode('utf-8')).decode('utf-8')
    st.markdown(f'<iframe src="data:text/html;base64,{b64_html}" width="100%" height="{height}" style="border:none; border-radius:8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);"></iframe>', unsafe_allow_html=True)

def es_correo_valido(correo):
    return re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", correo) is not None

def enviar_correo(destinatarios_str, asunto, cuerpo_html, is_intern=False, es_reenvio=False):
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SMTP_USER = "hannejosebayehvillarreal@gmail.com" 
    SMTP_PASSWORD = "etbn ebyl ulet oqgh"  
    
    if not destinatarios_str: return False, "No se especificaron destinatarios."
    try:
        lista_destinatarios = [email.strip() for email in destinatarios_str.split(",") if email.strip()]
        lista_internos = obtener_correos_cc() if not is_intern and not es_reenvio else []
        
        msg = EmailMessage()
        msg['Subject'] = asunto
        msg['From'] = SMTP_USER
        
        if es_reenvio: msg['To'] = SMTP_USER 
        elif is_intern: msg['To'] = ", ".join(lista_destinatarios)
        else: msg['To'] = ", ".join(lista_internos) if lista_internos else SMTP_USER
            
        msg.set_content(cuerpo_html, subtype='html')
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        
        destinatarios_totales = lista_destinatarios if (is_intern or es_reenvio) else list(set(lista_destinatarios + lista_internos))
        if not destinatarios_totales: destinatarios_totales = [SMTP_USER]
        
        server.send_message(msg, from_addr=SMTP_USER, to_addrs=destinatarios_totales)
        server.quit()
        return True, f"Correo enviado a {len(destinatarios_totales)} destinatarios."
    except Exception as e:
        return False, str(e)

# ==========================================
# CACHÉ DE DATOS BD
# ==========================================
@st.cache_data(ttl=300)
def cargar_catalogos():
    return (
        DBManager.fetch_all("SELECT id, nombre, apellido FROM analista WHERE estado = TRUE"),
        DBManager.fetch_all("SELECT id, nombre FROM plataforma WHERE estado = TRUE"),
        DBManager.fetch_all("SELECT id, nombre, serie_id FROM tipo_comunicado WHERE estado = TRUE"),
        DBManager.fetch_all("SELECT id, nombre FROM servicio WHERE estado = TRUE ORDER BY nombre ASC")
    )

def obtener_todos_servicios(): return DBManager.fetch_all("SELECT id, nombre, estado FROM servicio ORDER BY nombre ASC")
def obtener_todos_terceros(): return DBManager.fetch_all("SELECT id, nombre, estado FROM tercero ORDER BY nombre ASC")
def cargar_terceros_por_servicio(servicio_id): return DBManager.fetch_all("SELECT t.id, t.nombre FROM servicio_tercero st JOIN tercero t ON st.tercero_id = t.id WHERE st.servicio_id = %s AND t.estado = TRUE", (servicio_id,))

def cargar_correos_segmentados(servicio_id, plataforma_id, nombre_servicio="", nombre_plataforma=""):
    if nombre_plataforma.upper() == "GENERAL": return [f['email'].strip() for f in DBManager.fetch_all("SELECT DISTINCT email FROM servicio_correo WHERE estado = TRUE")]
    elif nombre_servicio.upper() == nombre_plataforma.upper(): return [f['email'].strip() for f in DBManager.fetch_all("SELECT DISTINCT email FROM servicio_correo WHERE plataforma_id = %s AND estado = TRUE", (plataforma_id,))]
    else: return [f['email'].strip() for f in DBManager.fetch_all("SELECT DISTINCT email FROM servicio_correo WHERE servicio_id = %s AND estado = TRUE", (servicio_id,))]

def obtener_siguiente_consecutivo_preview(serie_id):
    res = DBManager.fetch_one("SELECT s.codigo, c.siguiente_valor FROM consecutivo_serie c JOIN serie s ON c.serie_id = s.id WHERE s.id = %s", (serie_id,))
    return (res['codigo'], res['siguiente_valor']) if res else ("N/A", 0)

def cargar_plantillas(): return DBManager.fetch_all("SELECT id, plataforma_id, tipo_comunicado_id, asunto, html, estado FROM plantilla WHERE estado = TRUE")
def obtener_correos_cc(): return [fila['email'].strip() for fila in DBManager.fetch_all("SELECT email FROM correo_interno_cc WHERE estado = TRUE")]

def get_filtros_datos(alias_tabla='c'):
    filtro = ""
    if hasattr(st.session_state, 'SERV_IDS_RESTRINGIDOS') and st.session_state.SERV_IDS_RESTRINGIDOS: 
        filtro += f" AND {alias_tabla}.servicio_id IN ({','.join(map(str, st.session_state.SERV_IDS_RESTRINGIDOS))}) "
    if hasattr(st.session_state, 'VER_SOLO_PROPIOS') and st.session_state.VER_SOLO_PROPIOS: 
        filtro += f" AND {alias_tabla}.analista_id = {st.session_state.user_info['id']} "
    return filtro

def cargar_comunicados_abiertos():
    return DBManager.fetch_all(f"""
        SELECT c.id, c.consecutivo_num, c.asunto_final, c.plataforma_id, p.nombre AS plataforma_nom,
               s.id AS servicio_id, s.nombre AS servicio_nom, MAX(t.id) AS tercero_id, MAX(t.nombre) AS tercero_nom,
               MAX(cd.email) AS emails_apertura, c.fecha_creacion, c.descripcion,
               MAX(tc.id) AS tipo_comunicado_id, MAX(tc.nombre) AS tipo_comunicado_nom
        FROM comunicado c JOIN servicio s ON c.servicio_id = s.id LEFT JOIN plataforma p ON c.plataforma_id = p.id
        LEFT JOIN tipo_comunicado tc ON c.tipo_comunicado_id = tc.id
        LEFT JOIN comunicado_destinatario cd ON cd.comunicado_id = c.id AND cd.estado = 'Enviado'
        LEFT JOIN tercero t ON cd.tercero_id = t.id
        WHERE c.estado = 'Abierto' {get_filtros_datos('c')}
        GROUP BY c.id, c.consecutivo_num, c.asunto_final, c.plataforma_id, p.nombre, s.id, s.nombre, c.fecha_creacion, c.descripcion
    """)

def cargar_estadisticas_sidebar():
    filtro = get_filtros_datos('c')
    total = (DBManager.fetch_one(f"SELECT COUNT(*) as total FROM comunicado c WHERE 1=1 {filtro}") or {}).get('total', 0)
    cerrados = (DBManager.fetch_one(f"SELECT COUNT(*) as cerrados FROM comunicado c WHERE c.estado = 'Cerrado' {filtro}") or {}).get('cerrados', 0)
    avg_row = DBManager.fetch_one(f"SELECT AVG(TIMESTAMPDIFF(MINUTE, fecha_creacion, fecha_envio)) as avg_min FROM comunicado c WHERE c.estado = 'Cerrado' AND c.fecha_envio IS NOT NULL AND c.fecha_creacion IS NOT NULL {filtro}")
    return round((cerrados / total * 100) if total > 0 else 0, 1), round(float(avg_row['avg_min']) if avg_row and avg_row['avg_min'] is not None else 0.0)

# ==========================================
# MODALES (ST.DIALOG)
# ==========================================

@st.dialog("Vista Previa - Apertura de Novedad", width="large")
def dialog_preview_apertura(preview):
    st.markdown("<div style='background-color: rgba(255, 193, 7, 0.15); padding: 12px; border-radius: 8px; border-left: 5px solid #ffc107; margin-bottom: 20px; color: var(--cetacean-blue);'><strong style='color: #b38600; font-size: 1.1rem;'>🔸 Estado: Pendiente de Acción</strong><br>Verifica la vista previa del comunicado antes de enviarlo.</div>", unsafe_allow_html=True)
    mostrar_vista_previa(preview['html_draft'])
    db_data = preview['db_data']
    req_ap = db_data['requiere_aprobacion']
    
    c1, c2 = st.columns(2)
    if c1.button("🚀 Enviar a Aprobación" if req_ap else "✔️ Confirmar y Enviar Correo", type="primary", use_container_width=True):
        conn_save = DBManager.get_conn()
        if conn_save:
            cursor_save = conn_save.cursor(dictionary=True)
            try:
                cursor_save.execute("SELECT c.siguiente_valor, s.codigo FROM consecutivo_serie c JOIN serie s ON c.serie_id = s.id WHERE c.serie_id = %s FOR UPDATE", (db_data['serie_id'],))
                row = cursor_save.fetchone()
                consecutivo_real = f"{row['codigo']}-{row['siguiente_valor']}"
                cursor_save.execute("UPDATE consecutivo_serie SET siguiente_valor = siguiente_valor + 1 WHERE serie_id = %s", (db_data['serie_id'],))
                
                asunto_final_real = db_data['asunto_ui'].replace(db_data['consecutivo_preview'], consecutivo_real)
                html_final = Template(preview['template_html']).render(consecutivo=consecutivo_real, **preview['template_args'])
                
                cursor_save.execute("""INSERT INTO comunicado (plataforma_id, tipo_comunicado_id, serie_id, consecutivo_num, asunto_final, html_final, descripcion, afectacion, analista_id, servicio_id, estado, fecha_creacion, requiere_aprobacion) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                                    (db_data['plataforma_id'], db_data['tipo_comunicado_id'], db_data['serie_id'], consecutivo_real, asunto_final_real, html_final, db_data['descripcion'], db_data['afectacion'], db_data['analista_id'], db_data['servicio_id'], 'Pendiente Apertura' if req_ap else db_data['estado'], db_data['fecha_creacion'], req_ap))
                
                cursor_save.execute("INSERT INTO comunicado_destinatario (comunicado_id, tercero_id, email, estado, detalle) VALUES (%s, %s, %s, %s, %s)", 
                                    (cursor_save.lastrowid, db_data['tercero_id'], json.dumps([e.strip() for e in db_data['correos_input'].split(",") if e.strip()]), 'Pendiente' if req_ap else 'Enviado', db_data['diagnostico_falla']))
                conn_save.commit()

                msg_correo = ""
                if not req_ap and db_data['es_externa'] and db_data['correos_input'].strip():
                    exito, desc = enviar_correo(db_data['correos_input'], asunto_final_real, html_final)
                    msg_correo = "✉️ Correo enviado." if exito else f"⚠️ Fallo: {desc}"
                    
                registrar_auditoria(st.session_state.user_info['id'], 'CREAR_APERTURA', f"Generado {consecutivo_real}")
                st.session_state['toasts'].append({"msg": f"Novedad {consecutivo_real} registrada. {msg_correo}", "icon": "✔️"})
                if 'show_dialog_apertura' in st.session_state: del st.session_state['show_dialog_apertura']
                st.rerun()
            except Error as e:
                conn_save.rollback()
                st.error("Error BD.")
            finally:
                cursor_save.close()
                conn_save.close()
                
    if c2.button("✖️ Editar / Cancelar", use_container_width=True):
        if 'show_dialog_apertura' in st.session_state: del st.session_state['show_dialog_apertura']
        st.rerun()

@st.dialog("Vista Previa - Cierre de Novedad", width="large")
def dialog_preview_cierre(preview):
    st.markdown("<div style='background-color: rgba(255, 193, 7, 0.15); padding: 12px; border-radius: 8px; border-left: 5px solid #ffc107; margin-bottom: 20px; color: var(--cetacean-blue);'><strong style='color: #b38600; font-size: 1.1rem;'>🔸 Estado: Pendiente de Acción</strong><br>Revisa el comunicado de normalidad.</div>", unsafe_allow_html=True)
    mostrar_vista_previa(preview['html'])
    
    req_ci = preview['db_data']['requiere_aprobacion']
    c1, c2 = st.columns(2)
    if c1.button("🚀 Enviar Cierre a Aprobación" if req_ci else "✔️ Confirmar y Cerrar", type="primary", use_container_width=True):
        conn_close = DBManager.get_conn()
        if conn_close:
            cursor_close = conn_close.cursor()
            try:
                cursor_close.execute("UPDATE comunicado SET estado = %s, solucion_aplicada = %s, fecha_envio = %s, requiere_aprobacion = %s, html_cierre = %s, asunto_cierre = %s WHERE id = %s", 
                                     ('Pendiente Cierre' if req_ci else 'Cerrado', preview['solucion_interna'], preview['fecha_hora_cierre'], req_ci, preview['html'], preview['asunto_norm'], preview['comunicado_id']))
                
                cursor_close.execute("INSERT INTO comunicado_destinatario (comunicado_id, tercero_id, email, estado, detalle) VALUES (%s, %s, %s, %s, %s)", 
                                     (preview['comunicado_id'], preview['tercero_id_ci'], json.dumps([e.strip() for e in preview['correos_finales_ci'].split(",") if e.strip()]), 'Pendiente' if req_ci else 'Cierre Enviado', preview['solucion_interna']))
                conn_close.commit()
                
                msg_correo = ""
                if not req_ci and preview['correos_finales_ci'].strip():
                    exito, desc = enviar_correo(preview['correos_finales_ci'], preview['asunto_norm'], preview['html'])
                    msg_correo = "✉️ Correo enviado." if exito else f"⚠️ Fallo: {desc}"
                
                registrar_auditoria(st.session_state.user_info['id'], 'CERRAR_INCIDENTE', f"Cierre del incidente ID {preview['comunicado_id']}")
                st.session_state['toasts'].append({"msg": f"Incidente actualizado. {msg_correo}", "icon": "✔️"})
                if 'show_dialog_cierre' in st.session_state: del st.session_state['show_dialog_cierre']
                st.rerun()
            except Error as e:
                conn_close.rollback()
                st.error("Error BD.")
            finally:
                cursor_close.close()
                conn_close.close()

    if c2.button("✖️ Editar / Cancelar", use_container_width=True):
        if 'show_dialog_cierre' in st.session_state: del st.session_state['show_dialog_cierre']
        st.rerun()

@st.dialog("Vista Previa - Programación de Mantenimiento", width="large")
def dialog_preview_mt_prog(preview):
    st.markdown("<div style='background-color: rgba(255, 193, 7, 0.15); padding: 12px; border-radius: 8px; border-left: 5px solid #ffc107; margin-bottom: 20px; color: var(--cetacean-blue);'><strong style='color: #b38600; font-size: 1.1rem;'>🔸 Estado: Pendiente de Acción</strong><br>Verifica la programación de la ventana.</div>", unsafe_allow_html=True)
    mostrar_vista_previa(preview['html_draft'])
    
    db_data = preview['db_data']
    req_mt = db_data['requiere_aprobacion']
    c1, c2 = st.columns(2)
    
    if c1.button("🚀 Enviar a Aprobación" if req_mt else "✔️ Confirmar y Programar", type="primary", use_container_width=True):
        conn_mt = DBManager.get_conn()
        if conn_mt:
            cursor_mt = conn_mt.cursor(dictionary=True)
            try:
                cursor_mt.execute("SELECT c.siguiente_valor, s.codigo FROM consecutivo_serie c JOIN serie s ON c.serie_id = s.id WHERE c.serie_id = %s FOR UPDATE", (db_data['serie_id'],))
                row = cursor_mt.fetchone()
                consecutivo_real_mt = f"{row['codigo']}-{row['siguiente_valor']}"
                cursor_mt.execute("UPDATE consecutivo_serie SET siguiente_valor = siguiente_valor + 1 WHERE serie_id = %s", (db_data['serie_id'],))
                
                asunto_final_real_mt = db_data['asunto_ui'].replace(db_data['consecutivo_preview'], consecutivo_real_mt)
                html_final = Template(preview['template_html']).render(consecutivo=consecutivo_real_mt, **preview['template_args'])
                
                cursor_mt.execute("""INSERT INTO comunicado (plataforma_id, tipo_comunicado_id, serie_id, consecutivo_num, asunto_final, html_final, descripcion, afectacion, analista_id, servicio_id, estado, fecha_creacion, requiere_aprobacion) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                                  (db_data['plataforma_id'], db_data['tipo_comunicado_id'], db_data['serie_id'], consecutivo_real_mt, asunto_final_real_mt, html_final, db_data['desc_bd_mt'], db_data['afectacion_mt'], db_data['analista_id'], db_data['servicio_id'], 'Pendiente Mantenimiento' if req_mt else 'Abierto', db_data['inicio_dt'], req_mt))
                
                cursor_mt.execute("INSERT INTO comunicado_destinatario (comunicado_id, tercero_id, email, estado, detalle) VALUES (%s, %s, %s, %s, %s)", 
                                  (cursor_mt.lastrowid, db_data['tercero_id'], json.dumps([e.strip() for e in db_data['correos_input'].split(",") if e.strip()]), 'Pendiente' if req_mt else 'Enviado', "Mantenimiento Programado"))
                conn_mt.commit()

                msg_correo = ""
                if not req_mt and db_data['correos_input'].strip():
                    exito, desc = enviar_correo(db_data['correos_input'], asunto_final_real_mt, html_final)
                    msg_correo = "✉️ Correo enviado." if exito else f"⚠️ Fallo: {desc}"
                
                registrar_auditoria(st.session_state.user_info['id'], 'CREAR_MANTENIMIENTO', f"Ventana {consecutivo_real_mt} generada.")
                st.session_state['toasts'].append({"msg": f"Ventana guardada. {msg_correo}", "icon": "✔️"})
                if 'show_dialog_mt_p' in st.session_state: del st.session_state['show_dialog_mt_p']
                st.rerun()
            except Error as e:
                conn_mt.rollback()
                st.error("Error BD.")
            finally:
                cursor_mt.close()
                conn_mt.close()
                
    if c2.button("✖️ Editar / Cancelar", use_container_width=True):
        if 'show_dialog_mt_p' in st.session_state: del st.session_state['show_dialog_mt_p']
        st.rerun()

@st.dialog("Vista Previa - Fin de Mantenimiento", width="large")
def dialog_preview_mt_fin(preview):
    st.markdown("<div style='background-color: rgba(255, 193, 7, 0.15); padding: 12px; border-radius: 8px; border-left: 5px solid #ffc107; margin-bottom: 20px; color: var(--cetacean-blue);'><strong style='color: #b38600; font-size: 1.1rem;'>🔸 Estado: Pendiente de Acción</strong><br>Verifica el comunicado del fin de ventana.</div>", unsafe_allow_html=True)
    mostrar_vista_previa(preview['html'])
    
    req_mf = preview['db_data']['requiere_aprobacion']
    c1, c2 = st.columns(2)
    if c1.button("🚀 Enviar Cierre a Aprobación" if req_mf else "✔️ Confirmar y Finalizar", type="primary", use_container_width=True):
        conn_mf = DBManager.get_conn()
        if conn_mf:
            cursor_mf = conn_mf.cursor()
            try:
                cursor_mf.execute("UPDATE comunicado SET estado = %s, solucion_aplicada = %s, fecha_envio = %s, requiere_aprobacion = %s, html_cierre = %s, asunto_cierre = %s WHERE id = %s", 
                                  ('Pendiente Cierre' if req_mf else 'Cerrado', preview['solucion_interna'], preview['fecha_hora_cierre'], req_mf, preview['html'], preview['asunto_norm'], preview['comunicado_id']))
                
                cursor_mf.execute("INSERT INTO comunicado_destinatario (comunicado_id, tercero_id, email, estado, detalle) VALUES (%s, %s, %s, %s, %s)", 
                                  (preview['comunicado_id'], preview['tercero_id_ci'], json.dumps([e.strip() for e in preview['correos_finales_ci'].split(",") if e.strip()]), 'Pendiente' if req_mf else 'Cierre Enviado', preview['solucion_interna']))
                conn_mf.commit()
                
                msg_correo = ""
                if not req_mf and preview['correos_finales_ci'].strip():
                    exito, desc = enviar_correo(preview['correos_finales_ci'], preview['asunto_norm'], preview['html'])
                    msg_correo = "✉️ Correo enviado." if exito else f"⚠️ Fallo: {desc}"

                registrar_auditoria(st.session_state.user_info['id'], 'CERRAR_MANTENIMIENTO', f"Finalizó Mantenimiento {preview['consecutivo']}")
                st.session_state['toasts'].append({"msg": f"Ventana {preview['consecutivo']} actualizada. {msg_correo}", "icon": "✔️"})
                if 'show_dialog_mt_f' in st.session_state: del st.session_state['show_dialog_mt_f']
                st.rerun()
            except Error as e:
                conn_mf.rollback()
                st.error("Error BD.")
            finally:
                cursor_mf.close()
                conn_mf.close()

    if c2.button("✖️ Editar / Cancelar", use_container_width=True):
        if 'show_dialog_mt_f' in st.session_state: del st.session_state['show_dialog_mt_f']
        st.rerun()

@st.dialog("Vista Previa - Reenvío de Comunicado", width="large")
def dialog_preview_reenvio(preview):
    st.markdown(f"<div style='background-color: rgba(33, 150, 243, 0.15); padding: 12px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; color: var(--cetacean-blue);'><strong style='color: #0d47a1; font-size: 1.1rem;'>✉️ Resumen de Despacho</strong><br><b>Versión seleccionada:</b> {preview['tipo_reenvio']}<br><b>Asunto:</b> {preview['asunto']}<br><b>Destinatarios (BCC):</b> {preview['correos']}<br><b>Nota:</b> El estado del comunicado no cambiará y no se notificará a correos internos (CC).</div>", unsafe_allow_html=True)
    mostrar_vista_previa(preview['html'])
    
    c1, c2 = st.columns(2)
    if c1.button("✔️ Confirmar y Despachar", type="primary", use_container_width=True):
        exito, msg = enviar_correo(preview['correos'], preview['asunto'], preview['html'], es_reenvio=True)
        if exito:
            registrar_auditoria(st.session_state.user_info['id'], 'REENVIO_COMUNICADO', f"Despachó {preview['tipo_reenvio']} del caso {preview['consecutivo']} a {len(preview['lista_correos'])} destinatario(s).")
            DBManager.execute("INSERT INTO comunicado_destinatario (comunicado_id, email, estado, detalle) VALUES (%s, %s, 'Reenviado', %s)", (preview['com_id'], json.dumps(preview['lista_correos']), f"Reenvío/Actualización: {preview['tipo_reenvio']}"))
            st.session_state['toasts'].append({"msg": f"Despachado con éxito a {len(preview['lista_correos'])} correo(s).", "icon": "✔️"})
            if 'show_dialog_reenvio' in st.session_state: del st.session_state['show_dialog_reenvio']
            st.rerun()
        else:
            st.error(f"Error al enviar: {msg}")

    if c2.button("✖️ Cancelar / Editar", use_container_width=True):
        if 'show_dialog_reenvio' in st.session_state: del st.session_state['show_dialog_reenvio']
        st.rerun()

# ==========================================
# VISTAS (PÁGINAS INDIVIDUALES) Y AUTENTICACIÓN
# ==========================================

def view_login():
    st.markdown("<div style='height: 6vh;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1.5, 2, 1.5])
    
    with col2:
        with st.form("form_login"):
            st.markdown(
                """
                <div style="display: flex; justify-content: center; margin-bottom: 0.5rem;">
                    <img src="https://res.cloudinary.com/bayehcompany/image/upload/v1778112472/dozewlylntjhfklp2bwj.png" width="280">
                </div>
                """, 
                unsafe_allow_html=True
            )
            st.markdown("<h2 style='text-align: center; font-size: 2rem; margin-bottom: 5px; color: var(--cetacean-blue);'>¡Bienvenido! 👋</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: rgba(16,0,79,0.6); font-size: 1.05rem; margin-bottom: 2.5rem;'>Ingresa tus credenciales para acceder al portal</p>", unsafe_allow_html=True)
            
            login_correo = st.text_input("✉️ Correo Electrónico", placeholder="usuario@empresa.com")
            login_password = st.text_input("🔒 Contraseña", type="password", placeholder="••••••••")
            
            st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
            btn_login = st.form_submit_button("Iniciar Sesión 🚀", type="primary", use_container_width=True)
            
            if btn_login:
                if not login_correo or not login_password:
                    st.warning("Por favor, completa todos los campos.")
                else:
                    user_data = DBManager.fetch_one("SELECT id, nombre, apellido, correo, password, rol FROM analista WHERE correo = %s AND estado = TRUE", (login_correo,))
                    if user_data and verificar_password(login_password, user_data['password']):
                        del user_data['password']
                        try:
                            user_valido = AnalistaValidado(**user_data)
                            st.session_state['logged_in'] = True
                            st.session_state['user_info'] = user_valido.model_dump()
                            st.query_params["session_token"] = generar_token_seguro(user_data['id'])
                            registrar_auditoria(user_data['id'], 'LOGIN', 'Inicio de sesión exitoso')
                            st.session_state['toasts'].append({"msg": f"¡Bienvenido {user_data['nombre']}!", "icon": "👋"})
                            st.rerun()
                        except ValidationError:
                            st.error("Error en perfil de usuario. Contacte al administrador.")
                    else:
                        logging.warning(f"Intento de inicio de sesión fallido para: {login_correo}")
                        st.error("✖️ Credenciales incorrectas o usuario inactivo.")

def view_dashboard():
    st.title("🌐 Centro Operativo SOC")
    st.markdown("<p style='color: rgba(16,0,79,0.7); font-size: 1.1rem;'>Monitoreo en tiempo real de los servicios y SLA.</p>", unsafe_allow_html=True)
    
    pct_res, tiempo_prom = cargar_estadisticas_sidebar()
    tiempo_str = f"{int(tiempo_prom // 60)}h {int(tiempo_prom % 60)}m" if tiempo_prom >= 60 else f"{int(tiempo_prom)}m"
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("🔥 Novedades Activas", len(st.session_state.inci_abiertos))
    kpi2.metric("🔧 Mant. Activos", len(st.session_state.mant_abiertos))
    kpi3.metric("📊 Resolución Global", f"{pct_res}%")
    kpi4.metric("⏳ SLA Configurado", f"{st.session_state.config_sis['sla_horas']} Horas")
    
    st.divider()
    
    ahora = datetime.datetime.now()
    alertas = [inc for inc in st.session_state.inci_abiertos if isinstance(inc.get('fecha_creacion'), datetime.datetime) and (ahora - inc['fecha_creacion']).total_seconds() / 3600 >= st.session_state.config_sis['sla_horas']]
    
    if alertas:
        st.markdown(f"### ⚠️ Alertas Críticas (SLA Vencido > {st.session_state.config_sis['sla_horas']}h)")
        for ac in alertas: 
            with st.expander(f"🔴 {ac['consecutivo_num']} - {ac['servicio_nom']} (Vencido)"):
                st.markdown(f"<p style='color: var(--cetacean-blue);'><b>Asunto:</b> {ac.get('asunto_final', 'Sin Asunto')}</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='color: var(--cetacean-blue);'><b>Abierto desde:</b> {ac['fecha_creacion'].strftime('%Y-%m-%d %H:%M')}</p>", unsafe_allow_html=True)
                st.markdown(f"<div style='background-color: var(--bg-light); padding: 10px; border-radius: 6px; border-left: 3px solid var(--rojo-purpureo);'><p style='margin:0; font-size: 0.95rem; color: var(--cetacean-blue);'><b>Descripción de Afectación:</b><br>{ac.get('descripcion', 'Sin detalle registrado.')}</p></div>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                
                c_btn, _ = st.columns([1, 1])
                if c_btn.button("Enviar Actualización 🔄", key=f"btn_alerta_{ac['id']}", type="primary"):
                    st.session_state['caso_a_editar'] = ac['id']
                    st.switch_page(pg_historial)
                    
        st.markdown("<br>", unsafe_allow_html=True)
        
    col_t1, col_t2 = st.columns([1.5, 1])
    with col_t1:
        st.markdown("#### 🔥 Novedades Pendientes (Monitor SLA)")
        if st.session_state.inci_abiertos:
            df_inc = pd.DataFrame(st.session_state.inci_abiertos)
            df_inc['SLA'] = df_inc['fecha_creacion'].apply(lambda x: calcular_estado_sla(x, st.session_state.config_sis['sla_horas']))
            df_inc['fecha_creacion'] = pd.to_datetime(df_inc['fecha_creacion']).dt.strftime('%H:%M %d/%m')
            
            df_show = df_inc[['SLA', 'consecutivo_num', 'servicio_nom', 'fecha_creacion']]
            df_show.columns = ['Estado SLA', 'ID', 'Servicio', 'Apertura']
            st.dataframe(df_show, hide_index=True, use_container_width=True)
        else:
            st.info("Todo en orden. No hay novedades abiertas.")
            
    with col_t2:
        st.markdown("#### 🔧 Mantenimientos Próximos")
        if st.session_state.mant_abiertos:
            df_man = pd.DataFrame(st.session_state.mant_abiertos)[['consecutivo_num', 'servicio_nom', 'fecha_creacion']]
            df_man['fecha_creacion'] = pd.to_datetime(df_man['fecha_creacion']).dt.strftime('%H:%M %d/%m')
            df_man.columns = ['ID', 'Servicio', 'Inicio Prog.']
            st.dataframe(df_man, hide_index=True, use_container_width=True)
        else:
            st.success("No hay mantenimientos activos.")

def view_autorizaciones():
    st.title("🛡️ Bandeja de Autorizaciones Pendientes")
    filtro_apr = get_filtros_datos('c')
    pendientes = DBManager.fetch_all(f"SELECT c.*, s.nombre AS servicio_nom, a.nombre as analista_nom FROM comunicado c JOIN servicio s ON c.servicio_id = s.id JOIN analista a ON c.analista_id = a.id WHERE c.estado LIKE 'Pendiente%' {filtro_apr}")
    
    if not pendientes: st.info("🎉 No hay comunicados pendientes de aprobación.")
    else:
        for p in pendientes:
            with st.expander(f"⏳ {p['estado']} - {p['consecutivo_num']} | {p['servicio_nom']} (Analista: {p['analista_nom']})"):
                st.write(f"**Asunto:** {p['asunto_final']}")
                mostrar_vista_previa(p['html_final'], height=400)
                
                c1, c2 = st.columns(2)
                if c1.button("✔️ Aprobar y Enviar Correo", key=f"apr_{p['id']}", type="primary"):
                    dest_row = DBManager.fetch_one("SELECT email FROM comunicado_destinatario WHERE comunicado_id = %s LIMIT 1", (p['id'],))
                    dest_emails = json.loads(dest_row['email']) if dest_row and dest_row['email'] else []
                    nuevo_estado = 'Abierto' if ('Apertura' in p['estado'] or 'Mantenimiento' in p['estado']) else 'Cerrado'
                    
                    upd1 = DBManager.execute("UPDATE comunicado SET estado = %s, aprobado_por = %s, requiere_aprobacion = FALSE WHERE id = %s", (nuevo_estado, st.session_state.user_info['id'], p['id']))
                    upd2 = DBManager.execute("UPDATE comunicado_destinatario SET estado = 'Enviado' WHERE comunicado_id = %s", (p['id'],))
                    
                    if upd1:
                        msg_correo = ""
                        if dest_emails:
                            exito_correo, desc_correo = enviar_correo(",".join(dest_emails), p['asunto_final'], p['html_final'])
                            msg_correo = "✉️ Correo enviado." if exito_correo else f"⚠️ Fallo al enviar correo: {desc_correo}"
                            
                        registrar_auditoria(st.session_state.user_info['id'], 'APROBAR_COMUNICADO', f"Aprobó comunicado {p['consecutivo_num']}")
                        st.session_state['toasts'].append({"msg": f"Comunicado {p['consecutivo_num']} aprobado. {msg_correo}", "icon": "✔️"})
                        st.rerun()
                    else: st.error("✖️ Error de BD al aprobar.")
                    
                with c2.popover("✖️ Rechazar", use_container_width=True):
                    st.markdown("¿Estás seguro de rechazar este comunicado?")
                    if st.button("Confirmar Rechazo", key=f"rec_conf_{p['id']}", type="primary"):
                        if DBManager.execute("UPDATE comunicado SET estado = 'Rechazado', aprobado_por = %s, requiere_aprobacion = FALSE WHERE id = %s", (st.session_state.user_info['id'], p['id'])):
                            registrar_auditoria(st.session_state.user_info['id'], 'RECHAZAR_COMUNICADO', f"Rechazó comunicado {p['consecutivo_num']}")
                            st.session_state['toasts'].append({"msg": f"Comunicado {p['consecutivo_num']} rechazado exitosamente.", "icon": "⚠️"})
                            st.rerun()

def view_nueva_novedad():
    st.title("📝 Apertura de Novedad (Asistente)")
    
    st.markdown("#### 1️⃣ Clasificación del Incidente")
    st.info("Seleccione los datos base. El sistema cargará las opciones dinámicamente.")
    col1, col2, col3 = st.columns(3)
    with col1:
        analista_nombres = [f"{a['nombre']} {a['apellido']}" for a in st.session_state.analistas]
        try: idx_actual = analista_nombres.index(f"{st.session_state.user_info['nombre']} {st.session_state.user_info['apellido']}")
        except ValueError: idx_actual = 0
            
        analista_nom = st.selectbox("Analista", analista_nombres, index=idx_actual, disabled=not st.session_state.ES_ADMIN, key="sel_analista_ap")
        analista_sel = next(a for a in st.session_state.analistas if f"{a['nombre']} {a['apellido']}" == analista_nom)
        plat_nom = st.selectbox("Plataforma", [p['nombre'] for p in st.session_state.plataformas], key="sel_plat_ap")
        plataforma_sel = next(p for p in st.session_state.plataformas if p['nombre'] == plat_nom)
        afectacion = st.selectbox("Afectación", ["Afecta Disponibilidad", "Afectación Parcial", "No Afecta"], key="sel_afect_ap")
        
    with col2:
        serv_nombres = [s['nombre'] for s in st.session_state.servicios if s['id'] in st.session_state.SERV_IDS_RESTRINGIDOS] if st.session_state.SERV_IDS_RESTRINGIDOS else [s['nombre'] for s in st.session_state.servicios]
        if not serv_nombres: 
            st.warning("Tu rol no tiene acceso a ningún servicio válido en la base de datos.")
            st.stop()
        serv_nom = st.selectbox("Servicio Afectado", serv_nombres, key="sel_serv_ap")
        servicio_sel = next(s for s in st.session_state.servicios if s['nombre'] == serv_nom)

        terceros_asociados = cargar_terceros_por_servicio(servicio_sel['id'])
        if terceros_asociados:
            ter_nom = st.selectbox("Tercero / Aliado", [t['nombre'] for t in terceros_asociados], key="sel_terc_ap")
            tercero_sel = next(t for t in terceros_asociados if t['nombre'] == ter_nom)
        else:
            st.selectbox("Tercero / Aliado", ["N/A"], disabled=True, key="sel_terc_na_ap")
            tercero_sel = {'id': None, 'nombre': 'N/A'}
            
    with col3:
        tipo_nombres = [t['nombre'] for t in st.session_state.tipos if t['nombre'].lower() != 'mantenimiento']
        idx_tipo_default = 0
        if servicio_sel['nombre'].upper() == 'SALDO':
            for i, nombre in enumerate(tipo_nombres):
                if nombre.upper() == 'SALDO': idx_tipo_default = i; break
        
        tipo_nom = st.selectbox("Tipo Comunicado", tipo_nombres, index=idx_tipo_default, key=f"sel_tipo_ap_{servicio_sel['id']}")
        tipo_sel = next(t for t in st.session_state.tipos if t['nombre'] == tipo_nom)
        
        if st.session_state.plantillas:
            plantillas_filtradas = [p for p in st.session_state.plantillas if p.get('tipo_comunicado_id') == tipo_sel['id']]
            if plataforma_sel: plantillas_filtradas = [p for p in plantillas_filtradas if p.get('plataforma_id') == plataforma_sel['id'] or p.get('plataforma_id') is None]
                
            if plantillas_filtradas:
                kw_apertura = ["base", "novedad", "sinsaldo", "apertura", "falla", "incidente", "caida"]
                plantillas_ap = [p for p in plantillas_filtradas if any(kw in p['asunto'].lower().replace(" ", "") for kw in kw_apertura)] or plantillas_filtradas
                
                idx_apertura_default = 0
                if tipo_sel['nombre'].upper() == 'SALDO' or servicio_sel['nombre'].upper() == 'SALDO':
                    for i, p in enumerate(plantillas_ap):
                        if "sinsaldo" in p['asunto'].lower().replace(" ", ""): idx_apertura_default = i; break
                            
                plant_nom = st.selectbox("Plantilla BD", [f"Plantilla {p['id']} - {p['asunto']}" for p in plantillas_ap], index=idx_apertura_default, key=f"sel_plant_ap_{servicio_sel['id']}_{tipo_sel['id']}")
                plantilla_sel = next(p for p in plantillas_ap if f"Plantilla {p['id']} - {p['asunto']}" == plant_nom)
            else: st.warning("No hay plantillas de Apertura."); plantilla_sel = None
        else: st.warning("No hay plantillas en BD."); plantilla_sel = None

    codigo_serie_pv, num_sig_pv = obtener_siguiente_consecutivo_preview(tipo_sel['serie_id'])
    consecutivo_preview = f"{codigo_serie_pv}-{num_sig_pv}"

    fmt_kwargs = {
        'consecutivo': consecutivo_preview,
        'plataforma': plataforma_sel['nombre'],
        'servicio': servicio_sel['nombre'],
        'tercero': tercero_sel['nombre'] if tercero_sel['nombre'] != 'N/A' else ''
    }

    regla_apertura = evaluar_regla(plataforma_sel['id'], servicio_sel['id'], tipo_sel['id'], 'APERTURA', tercero_sel.get('id'))
    
    entidad_afectada = format_seguro(regla_apertura['entidad_afectada'], **fmt_kwargs)
    fmt_kwargs['entidad'] = entidad_afectada.strip()

    asunto_calculado = format_seguro(regla_apertura['asunto_template'], **fmt_kwargs)
    desc_calculada = format_seguro(regla_apertura['descripcion_template'], **fmt_kwargs)

    st.markdown("<br>", unsafe_allow_html=True)
    with st.form("form_apertura_seguro", clear_on_submit=False):
        st.markdown("#### 2️⃣ Detalle y Generación")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            col_d1, col_h1 = st.columns(2)
            fecha_inicio = col_d1.date_input("Fecha Inicio", datetime.date.today(), key="in_fecha_ap")
            hora_inicio = col_h1.time_input("Hora Inicio", key="in_hora_ap")
            
            with st.expander("🤖 Regla Automática Aplicada (Vista DB)", expanded=False):
                st.code(f"Regla ID: {regla_apertura.get('id', 'Default')}\nAsunto: {regla_apertura['asunto_template']}\nDesc: {regla_apertura['descripcion_template']}")
                diagnostico_falla = st.text_area("Diagnóstico Técnico (Interno)", height=100, key="txt_diag_ap")
            
            if st.session_state.EXIGE_APROBACION: st.info("ℹ️ Tu rol requiere que este comunicado pase por aprobación."); requiere_ap = True
            else: requiere_ap = st.checkbox("Requiere Aprobación antes de enviar", value=False, key="chk_req_ap")
            
        with col_f2:
            st.text_input("Consecutivo (Previsualización)", value=consecutivo_preview, disabled=True)
            asunto_modificado_en_ui = st.text_input("Asunto Final", value=asunto_calculado.strip(), key=f"asunto_ap_{servicio_sel['id']}_{str(tercero_sel.get('id', 'NA'))}_{tipo_sel['id']}")
            
            lista_correos_bd = cargar_correos_segmentados(servicio_sel['id'], plataforma_sel['id'], servicio_sel['nombre'], plataforma_sel['nombre'])
            correos_input = st.text_area("Destinatarios", value=", ".join(lista_correos_bd) if lista_correos_bd else "soporte@empresa.com", height=70, key=f"txt_corr_ap_{servicio_sel['id']}")
            es_externa = st.checkbox("Comunicación Externa", value=True, key="chk_externa_ap")
            
        descripcion_final = st.text_area("Descripción Pública (Editable)", value=desc_calculada.strip(), height=100, key=f"desc_ap_{servicio_sel['id']}_{str(tercero_sel.get('id', 'NA'))}")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.form_submit_button("Generar Vista Previa", type="primary", use_container_width=True):
            inicio_dt_ap = datetime.datetime.combine(fecha_inicio, hora_inicio)
            
            if not plantilla_sel: 
                st.toast("Falta configurar una plantilla en BD", icon="⚠️")
            elif not plataforma_sel: 
                st.error("Debe seleccionar una Plataforma.")
            elif inicio_dt_ap > datetime.datetime.now():
                st.error("⚠️ La fecha y hora de inicio de la novedad no puede ser posterior a la fecha y hora actual (está en el futuro).")
            else:
                template_args = {
                    'fecha_comunicado': formatear_fecha_es(datetime.date.today(), datetime.datetime.now().time()),
                    'fecha_inicio': formatear_fecha_es(fecha_inicio, hora_inicio),
                    'servicio': fmt_kwargs['entidad'] if (plataforma_sel['nombre'].upper() == "GENERAL") else f"{servicio_sel['nombre']}{' - ' + tercero_sel['nombre'] if tercero_sel['nombre'] != 'N/A' else ''}",
                    'descripcion': descripcion_final,
                    'cliente': fmt_kwargs['entidad'],
                    'tiempo_novedad': calcular_tiempo_transcurrido(inicio_dt_ap, datetime.datetime.now())
                }
                st.session_state['show_dialog_apertura'] = {
                    'html_draft': Template(plantilla_sel['html']).render(consecutivo=consecutivo_preview, **template_args), 'template_html': plantilla_sel['html'], 'template_args': template_args,
                    'db_data': {
                        'plataforma_id': plataforma_sel['id'], 'tipo_comunicado_id': tipo_sel['id'], 'serie_id': tipo_sel['serie_id'],
                        'asunto_ui': asunto_modificado_en_ui, 'consecutivo_preview': consecutivo_preview, 'descripcion': descripcion_final,
                        'afectacion': afectacion, 'analista_id': analista_sel['id'], 'servicio_id': servicio_sel['id'],
                        'estado': 'Abierto' if tipo_sel['nombre'] in ['Incidente', 'Saldo'] else 'Cerrado',
                        'fecha_creacion': inicio_dt_ap, 'tercero_id': tercero_sel.get('id'),
                        'diagnostico_falla': diagnostico_falla, 'correos_input': correos_input, 'es_externa': es_externa, 'requiere_aprobacion': requiere_ap
                    }
                }
                st.rerun() 

    if st.session_state.get('show_dialog_apertura'):
        dialog_preview_apertura(st.session_state['show_dialog_apertura'])

def view_cerrar_novedad():
    st.title("🏁 Cierre de Novedad (Asistente)")
    if not st.session_state.inci_abiertos: st.success("🎉 No hay incidentes en estado 'Abierto' pendientes por solucionar.")
    else:
        st.markdown("#### 1️⃣ Selección de la Novedad a Cerrar")
        col_sel1, col_sel2 = st.columns(2)
        with col_sel1:
            dic_abiertos = {c.get('asunto_final') if (c.get('consecutivo_num') and c.get('consecutivo_num') in c.get('asunto_final')) else f"{c.get('consecutivo_num')} - {c.get('asunto_final')}": c for c in st.session_state.inci_abiertos}
            comunicado_cierre = dic_abiertos[st.selectbox("Novedad Abierta", list(dic_abiertos.keys()), key="sel_abierto_ci")]
            
        with col_sel2:
            if st.session_state.plantillas:
                plantillas_filtradas_ci = [p for p in st.session_state.plantillas if p.get('tipo_comunicado_id') == comunicado_cierre.get('tipo_comunicado_id')]
                if comunicado_cierre.get('plataforma_id'): plantillas_filtradas_ci = [p for p in plantillas_filtradas_ci if p.get('plataforma_id') == comunicado_cierre.get('plataforma_id') or p.get('plataforma_id') is None]

                if plantillas_filtradas_ci:
                    kw_cierre = ["cierre", "normalidad", "consaldo", "fin", "restablecimiento", "solucion"]
                    plantillas_ci = [p for p in plantillas_filtradas_ci if any(kw in p['asunto'].lower().replace(" ", "") for kw in kw_cierre)] or plantillas_filtradas_ci
                    
                    idx_cierre_default = 0
                    if comunicado_cierre.get('tipo_comunicado_nom', '').upper() == 'SALDO' or comunicado_cierre.get('servicio_nom', '').upper() == 'SALDO':
                        for i, p in enumerate(plantillas_ci):
                            if "consaldo" in p['asunto'].lower().replace(" ", ""): idx_cierre_default = i; break
                                
                    plant_cierre_nom = st.selectbox("Plantilla de Cierre", [f"Plantilla {p['id']} - {p['asunto']}" for p in plantillas_ci], index=idx_cierre_default, key=f"sel_plant_ci_{comunicado_cierre['id']}")
                    plantilla_cierre_sel = next(p for p in plantillas_ci if f"Plantilla {p['id']} - {p['asunto']}" == plant_cierre_nom)
                else: st.warning("No hay plantillas de Cierre."); plantilla_cierre_sel = None
            else: st.warning("No hay plantillas configuradas."); plantilla_cierre_sel = None

        fmt_kwargs_ci = {
            'consecutivo': comunicado_cierre['consecutivo_num'],
            'plataforma': comunicado_cierre.get('plataforma_nom', ''),
            'servicio': comunicado_cierre.get('servicio_nom', ''),
            'tercero': comunicado_cierre.get('tercero_nom', '') or ''
        }

        regla_cierre = evaluar_regla(comunicado_cierre.get('plataforma_id'), comunicado_cierre.get('servicio_id'), comunicado_cierre.get('tipo_comunicado_id'), 'CIERRE', comunicado_cierre.get('tercero_id'))
        
        entidad_ci = format_seguro(regla_cierre['entidad_afectada'], **fmt_kwargs_ci)
        fmt_kwargs_ci['entidad'] = entidad_ci.strip()
        
        asunto_norm_calculado = format_seguro(regla_cierre['asunto_template'], **fmt_kwargs_ci)
        desc_norm_calculada = format_seguro(regla_cierre['descripcion_template'], **fmt_kwargs_ci)

        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("form_cierre_seguro", clear_on_submit=False):
            st.markdown("#### 2️⃣ Registro de Solución y Cierre")
            col_f1, col_f2 = st.columns(2)
            
            with col_f1:
                col_fc, col_hc = st.columns(2)
                fecha_cierre = col_fc.date_input("Fecha Cierre", datetime.date.today(), key="in_fecha_ci")
                hora_cierre = col_hc.time_input("Hora Cierre", key="in_hora_ci")
                    
                with st.expander("🤖 Regla Automática Aplicada (Vista DB)"):
                    st.code(f"Regla ID: {regla_cierre.get('id', 'Default')}\nAsunto: {regla_cierre['asunto_template']}\nDesc: {regla_cierre['descripcion_template']}")

                descripcion_publica = st.text_area("Descripción de Normalidad (Público)", value=desc_norm_calculada.strip(), key=f"desc_ci_{comunicado_cierre['id']}")
                
                if st.session_state.EXIGE_APROBACION: st.info("ℹ️ Tu rol requiere que este comunicado pase por aprobación."); requiere_ci = True
                else: requiere_ci = st.checkbox("Requiere Aprobación antes de enviar", value=False, key="chk_req_ci")
                
            with col_f2:
                st.text_input("Asunto Normalidad", value=asunto_norm_calculado.strip(), disabled=True, key=f"asunto_ci_{comunicado_cierre['id']}")
                solucion_interna = st.text_area("Solución Técnica Aplicada (INTERNO)", height=68, key=f"sol_ci_{comunicado_cierre['id']}")
                
                lista_fallback = cargar_correos_segmentados(comunicado_cierre['servicio_id'], comunicado_cierre['plataforma_id'], comunicado_cierre['servicio_nom'], comunicado_cierre.get('plataforma_nom', ''))
                emails_apertura_json = comunicado_cierre.get('emails_apertura')
                correos_finales_ci = st.text_area("Destinatarios", value=", ".join(json.loads(emails_apertura_json)) if emails_apertura_json else (", ".join(lista_fallback) if lista_fallback else "soporte@empresa.com"), height=68, key=f"txt_corr_ci_{comunicado_cierre['id']}")

            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("Generar Vista Previa", type="primary", use_container_width=True):
                fecha_hora_cierre = datetime.datetime.combine(fecha_cierre, hora_cierre)
                
                if not plantilla_cierre_sel: 
                    st.toast("Falta configurar la plantilla de cierre", icon="⚠️")
                elif fecha_hora_cierre < comunicado_cierre['fecha_creacion']:
                    st.error(f"⚠️ La fecha y hora de cierre no puede ser anterior a la fecha de apertura del incidente ({comunicado_cierre['fecha_creacion'].strftime('%Y-%m-%d %H:%M')}).")
                elif fecha_hora_cierre > datetime.datetime.now():
                    st.error("⚠️ La fecha y hora de cierre no puede ser posterior a la actual (no se permiten cierres en el futuro).")
                else:
                    es_global_ci = comunicado_cierre.get('plataforma_nom', '').upper() == 'GENERAL'
                    es_masiva_ci = comunicado_cierre.get('servicio_nom', '').upper() == comunicado_cierre.get('plataforma_nom', '').upper()
                    st.session_state['show_dialog_cierre'] = {
                        'html': Template(plantilla_cierre_sel['html']).render(
                            consecutivo=comunicado_cierre['consecutivo_num'], 
                            fecha_comunicado=formatear_fecha_es(datetime.date.today(), datetime.datetime.now().time()),
                            servicio=fmt_kwargs_ci['entidad'] if (es_global_ci or es_masiva_ci) else comunicado_cierre['servicio_nom'],
                            fecha_inicio=formatear_fecha_es(comunicado_cierre['fecha_creacion'], comunicado_cierre['fecha_creacion']),
                            fecha_cierre=formatear_fecha_es(fecha_cierre, hora_cierre),
                            descripcion_novedad=comunicado_cierre['descripcion'],
                            tiempo_transcurrido=calcular_tiempo_transcurrido(comunicado_cierre['fecha_creacion'], fecha_hora_cierre),
                            descripcion_cierre=descripcion_publica,
                            cliente=fmt_kwargs_ci['entidad']
                        ), 'solucion_interna': solucion_interna, 'fecha_hora_cierre': fecha_hora_cierre,
                        'comunicado_id': comunicado_cierre['id'], 'tercero_id_ci': comunicado_cierre.get('tercero_id'),
                        'correos_finales_ci': correos_finales_ci, 'asunto_norm': asunto_norm_calculado.strip(), 'db_data': {'requiere_aprobacion': requiere_ci}
                    }
                    st.rerun()

    if st.session_state.get('show_dialog_cierre'):
        dialog_preview_cierre(st.session_state['show_dialog_cierre'])

def view_mantenimientos():
    st.title("🔧 Gestión de Mantenimientos")
    st.markdown("#### 📅 Próximos Mantenimientos Programados")
    futuros = DBManager.fetch_all(f"SELECT c.consecutivo_num, c.asunto_final, c.fecha_creacion as inicio, c.fecha_envio as fin, c.estado FROM comunicado c WHERE c.tipo_comunicado_id = 4 AND c.fecha_creacion >= CURDATE() {get_filtros_datos('c')} ORDER BY c.fecha_creacion ASC")
    if futuros:
        df_cal = pd.DataFrame(futuros)
        df_cal['inicio'] = pd.to_datetime(df_cal['inicio']).dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(df_cal, use_container_width=True, hide_index=True)
    else: st.info("No hay mantenimientos programados en el futuro cercano.")

    st.divider()
    modo_mant = st.radio("Selecciona la Acción:", ["📅 Programar Nueva Ventana", "✔️ Finalizar Ventana Existente"], horizontal=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    if modo_mant == "📅 Programar Nueva Ventana":
        st.markdown("#### 1️⃣ Definición de la Ventana")
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            analista_nombres = [f"{a['nombre']} {a['apellido']}" for a in st.session_state.analistas]
            try: idx_actual_mt = analista_nombres.index(f"{st.session_state.user_info['nombre']} {st.session_state.user_info['apellido']}")
            except ValueError: idx_actual_mt = 0
            
            analista_nom_mt = st.selectbox("Analista (Auto-asignado)", analista_nombres, index=idx_actual_mt, disabled=not st.session_state.ES_ADMIN, key="sel_analista_mt")
            analista_sel_mt = next(a for a in st.session_state.analistas if f"{a['nombre']} {a['apellido']}" == analista_nom_mt)
            plat_nom_mt = st.selectbox("Plataforma", [p['nombre'] for p in st.session_state.plataformas], key="sel_plat_mt")
            plataforma_sel_mt = next(p for p in st.session_state.plataformas if p['nombre'] == plat_nom_mt)
            afectacion_mt = st.selectbox("Afectación", ["Afecta Disponibilidad", "Afectación Parcial", "No Afecta"], key="sel_afect_mt")
            
        with col_m2:
            serv_nombres_mt = [s['nombre'] for s in st.session_state.servicios if s['id'] in st.session_state.SERV_IDS_RESTRINGIDOS] if st.session_state.SERV_IDS_RESTRINGIDOS else [s['nombre'] for s in st.session_state.servicios]
            serv_nom_mt = st.selectbox("Servicio en Mantenimiento", serv_nombres_mt, key="sel_serv_mt")
            servicio_sel_mt = next(s for s in st.session_state.servicios if s['nombre'] == serv_nom_mt)
            
            terceros_asociados_mt = cargar_terceros_por_servicio(servicio_sel_mt['id'])
            if terceros_asociados_mt:
                ter_nom_mt = st.selectbox("Tercero / Aliado", [t['nombre'] for t in terceros_asociados_mt], key="sel_terc_mt")
                tercero_sel_mt = next(t for t in terceros_asociados_mt if t['nombre'] == ter_nom_mt)
            else: 
                st.selectbox("Tercero / Aliado", ["N/A"], disabled=True, key="sel_terc_na_mt")
                tercero_sel_mt = {'id': None, 'nombre': 'N/A'}
                
        with col_m3:
            idx_tipo_mt = next((i for i, t in enumerate(st.session_state.tipos) if "mantenimiento" in t['nombre'].lower()), 0)
            tipo_nom_mt = st.selectbox("Tipo Comunicado", [t['nombre'] for t in st.session_state.tipos], index=idx_tipo_mt, key="sel_tipo_mt")
            tipo_sel_mt = next(t for t in st.session_state.tipos if t['nombre'] == tipo_nom_mt)
            
            if st.session_state.plantillas:
                plantillas_filtradas_mt = [p for p in st.session_state.plantillas if p.get('tipo_comunicado_id') == tipo_sel_mt['id']]
                if plataforma_sel_mt: plantillas_filtradas_mt = [p for p in plantillas_filtradas_mt if p.get('plataforma_id') == plataforma_sel_mt['id'] or p.get('plataforma_id') is None]
                    
                if plantillas_filtradas_mt:
                    plantillas_usar_ini = [p for p in plantillas_filtradas_mt if any(kw in p['asunto'].lower() for kw in ["inicio", "programad", "preventiv"])] or plantillas_filtradas_mt
                    plant_nom_mt = st.selectbox("Plantilla BD", [f"Plantilla {p['id']} - {p['asunto']}" for p in plantillas_usar_ini], index=0, key="sel_plant_mt")
                    plantilla_sel_mt = next(p for p in plantillas_usar_ini if f"Plantilla {p['id']} - {p['asunto']}" == plant_nom_mt)
                else: st.warning("No hay plantilla para la plataforma."); plantilla_sel_mt = None
            else: st.warning("No hay plantillas."); plantilla_sel_mt = None

        codigo_serie_mt, num_siguiente_mt = obtener_siguiente_consecutivo_preview(tipo_sel_mt['serie_id'])
        consecutivo_gen_mt = f"{codigo_serie_mt}-{num_siguiente_mt}"

        fmt_kwargs_mt = {
            'consecutivo': consecutivo_gen_mt,
            'plataforma': plataforma_sel_mt['nombre'],
            'servicio': servicio_sel_mt['nombre'],
            'tercero': tercero_sel_mt['nombre'] if tercero_sel_mt['nombre'] != 'N/A' else ''
        }

        regla_mant = evaluar_regla(plataforma_sel_mt['id'], servicio_sel_mt['id'], tipo_sel_mt['id'], 'MANTENIMIENTO', tercero_sel_mt.get('id'))
        
        entidad_mt = format_seguro(regla_mant['entidad_afectada'], **fmt_kwargs_mt)
        fmt_kwargs_mt['entidad'] = entidad_mt.strip()

        asunto_mt_calculado = format_seguro(regla_mant['asunto_template'], **fmt_kwargs_mt)
        desc_mt_calculada = format_seguro(regla_mant['descripcion_template'], **fmt_kwargs_mt)

        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("form_mantenimiento_prog", clear_on_submit=False):
            st.markdown("#### 2️⃣ Tiempos Estimados y Detalles")
            col_f1, col_f2 = st.columns(2)
            
            with col_f1:
                col_d1, col_h1 = st.columns(2)
                fecha_inicio_mt = col_d1.date_input("Fecha Inicio Ventana", datetime.date.today(), key="in_fecha_ini_mt")
                hora_inicio_mt = col_h1.time_input("Hora Inicio", key="in_hora_ini_mt")
                
                col_d2, col_h2 = st.columns(2)
                fecha_fin_mt = col_d2.date_input("Fecha Fin Ventana", datetime.date.today(), key="in_fecha_fin_mt")
                hora_fin_mt = col_h2.time_input("Hora Fin", key="in_hora_fin_mt")
                
                inicio_dt_mt = datetime.datetime.combine(fecha_inicio_mt, hora_inicio_mt)
                fin_dt_mt = datetime.datetime.combine(fecha_fin_mt, hora_fin_mt)
                tiempo_estimado_calc = calcular_tiempo_transcurrido(inicio_dt_mt, fin_dt_mt)
                st.info(f"⏳ **Tiempo estimado:** {tiempo_estimado_calc}")
                
                with st.expander("🤖 Regla Automática Aplicada"):
                    st.code(f"Regla ID: {regla_mant.get('id', 'Default')}\nAsunto: {regla_mant['asunto_template']}\nDesc: {regla_mant['descripcion_template']}")
                    
                if st.session_state.EXIGE_APROBACION: st.info("ℹ️ Tu rol requiere que esto pase por aprobación."); requiere_mt_p = True 
                else: requiere_mt_p = st.checkbox("Requiere Aprobación", value=False, key="chk_req_mt_p")

            with col_f2:
                st.text_input("Consecutivo (Preview)", value=consecutivo_gen_mt, disabled=True, key=f"cons_mt_{servicio_sel_mt['id']}_{tipo_sel_mt['id']}")
                asunto_modificado_mt_ui = st.text_input("Asunto Final", value=asunto_mt_calculado.strip(), key=f"asunto_mt_{servicio_sel_mt['id']}_{str(tercero_sel_mt.get('id', 'NA'))}")
                
                lista_correos_mt = cargar_correos_segmentados(servicio_sel_mt['id'], plataforma_sel_mt['id'], servicio_sel_mt['nombre'], plataforma_sel_mt['nombre'])
                correos_input_mt = st.text_area("Destinatarios", value=", ".join(lista_correos_mt) if lista_correos_mt else "soporte@empresa.com", height=70, key=f"txt_corr_mt_{servicio_sel_mt['id']}")
                
            descripcion_final_mt = st.text_area("Descripción de Tareas a Realizar", value=desc_mt_calculada.strip(), height=80, key=f"desc_mt_{servicio_sel_mt['id']}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("Generar Vista Previa", type="primary", use_container_width=True):
                if not plantilla_sel_mt: 
                    st.toast("Falta configurar una plantilla en la BD", icon="⚠️")
                elif fin_dt_mt <= inicio_dt_mt: 
                    st.error("⚠️ La fecha y hora de fin debe ser estrictamente posterior a la fecha de inicio de la ventana.")
                elif not plataforma_sel_mt: 
                    st.error("Debe seleccionar una Plataforma.")
                else:
                    template_args_mt = {
                        'fecha_comunicado': formatear_fecha_es(datetime.date.today(), datetime.datetime.now().time()),
                        'fecha_inicio': formatear_fecha_es(fecha_inicio_mt, hora_inicio_mt), 'fecha_fin': formatear_fecha_es(fecha_fin_mt, hora_fin_mt),
                        'tiempo_estimado': tiempo_estimado_calc,
                        'servicio': fmt_kwargs_mt['entidad'] if (plataforma_sel_mt['nombre'].upper() == "GENERAL") else f"{servicio_sel_mt['nombre']}{' - ' + tercero_sel_mt['nombre'] if tercero_sel_mt['nombre'] != 'N/A' else ''}", 
                        'descripcion': descripcion_final_mt, 'cliente': fmt_kwargs_mt['entidad']
                    }
                    
                    st.session_state['show_dialog_mt_p'] = {
                        'html_draft': Template(plantilla_sel_mt['html']).render(consecutivo=consecutivo_gen_mt, **template_args_mt),
                        'template_html': plantilla_sel_mt['html'], 'template_args': template_args_mt,
                        'db_data': {
                            'plataforma_id': plataforma_sel_mt['id'], 'tipo_comunicado_id': tipo_sel_mt['id'], 'serie_id': tipo_sel_mt['serie_id'],
                            'asunto_ui': asunto_modificado_mt_ui, 'consecutivo_preview': consecutivo_gen_mt, 
                            'desc_bd_mt': f"{descripcion_final_mt}\n\n[Ventana Programada: {formatear_fecha_es(fecha_inicio_mt, hora_inicio_mt)} hasta {formatear_fecha_es(fecha_fin_mt, hora_fin_mt)} - Duración: {tiempo_estimado_calc}]",
                            'afectacion_mt': afectacion_mt, 'analista_id': analista_sel_mt['id'], 'servicio_id': servicio_sel_mt['id'],
                            'inicio_dt': inicio_dt_mt, 'tercero_id': tercero_sel_mt.get('id'), 'correos_input': correos_input_mt, 'requiere_aprobacion': requiere_mt_p
                        }
                    }
                    st.rerun()

        if st.session_state.get('show_dialog_mt_p'):
            dialog_preview_mt_prog(st.session_state['show_dialog_mt_p'])

    else: # FINALIZAR VENTANA EXISTENTE
        if not st.session_state.mant_abiertos:
            st.success("🎉 No hay Ventanas de Mantenimiento abiertas pendientes por finalizar.")
        else:
            st.markdown("#### 1️⃣ Selección de la Ventana a Finalizar")
            col_sel1_mf, col_sel2_mf = st.columns(2)
            with col_sel1_mf:
                dic_mant = {c.get('asunto_final') if (c.get('consecutivo_num') and c.get('consecutivo_num') in c.get('asunto_final')) else f"{c.get('consecutivo_num')} - {c.get('asunto_final')}": c for c in st.session_state.mant_abiertos}
                abierto_nom_mf = st.selectbox("Ventana Abierta", list(dic_mant.keys()), key="sel_abierto_mf")
                comunicado_cierre_mf = dic_mant[abierto_nom_mf]
                
            with col_sel2_mf:
                if st.session_state.plantillas:
                    plantillas_filtradas_mf = [p for p in st.session_state.plantillas if p.get('tipo_comunicado_id') == comunicado_cierre_mf.get('tipo_comunicado_id')]
                    if comunicado_cierre_mf.get('plataforma_id'): plantillas_filtradas_mf = [p for p in plantillas_filtradas_mf if p.get('plataforma_id') == comunicado_cierre_mf.get('plataforma_id') or p.get('plataforma_id') is None]

                    if plantillas_filtradas_mf:
                        plantillas_usar = [p for p in plantillas_filtradas_mf if any(kw in p['asunto'].lower() for kw in ["fin", "cierre", "finalizad", "completad", "terminad"])] or plantillas_filtradas_mf
                        plant_cierre_nom_mf = st.selectbox("Plantilla de Cierre (Fin Ventana)", [f"Plantilla {p['id']} - {p['asunto']}" for p in plantillas_usar], index=0, key="sel_plant_mf")
                        plantilla_cierre_sel_mf = next(p for p in plantillas_usar if f"Plantilla {p['id']} - {p['asunto']}" == plant_cierre_nom_mf)
                    else: plantilla_cierre_sel_mf = None; st.warning("No hay plantilla para esta plataforma.")
                else: plantilla_cierre_sel_mf = None; st.warning("No hay plantillas configuradas.")

            fmt_kwargs_mf = {
                'consecutivo': comunicado_cierre_mf['consecutivo_num'],
                'plataforma': comunicado_cierre_mf.get('plataforma_nom', ''),
                'servicio': comunicado_cierre_mf.get('servicio_nom', ''),
                'tercero': comunicado_cierre_mf.get('tercero_nom', '') or ''
            }

            regla_mf = evaluar_regla(comunicado_cierre_mf.get('plataforma_id'), comunicado_cierre_mf.get('servicio_id'), comunicado_cierre_mf.get('tipo_comunicado_id'), 'FIN_MANTENIMIENTO', comunicado_cierre_mf.get('tercero_id'))
            
            entidad_mf = format_seguro(regla_mf['entidad_afectada'], **fmt_kwargs_mf)
            fmt_kwargs_mf['entidad'] = entidad_mf.strip()

            asunto_mf_calculado = format_seguro(regla_mf['asunto_template'], **fmt_kwargs_mf)
            desc_mf_calculada = format_seguro(regla_mf['descripcion_template'], **fmt_kwargs_mf)

            st.markdown("<br>", unsafe_allow_html=True)

            with st.form("form_finalizar_mantenimiento", clear_on_submit=False):
                st.markdown("#### 2️⃣ Datos de Finalización")
                col_fm1, col_fm2 = st.columns(2)
                with col_fm1:
                    col_d3, col_h3 = st.columns(2)
                    fecha_cierre_mf = col_d3.date_input("Fecha Finalización Real", datetime.date.today(), key="in_fecha_ci_mf")
                    hora_cierre_mf = col_h3.time_input("Hora Finalización Real", key="in_hora_ci_mf")
                    
                    with st.expander("🤖 Regla Automática Aplicada"):
                        st.code(f"Regla ID: {regla_mf.get('id', 'Default')}\nAsunto: {regla_mf['asunto_template']}\nDesc: {regla_mf['descripcion_template']}")

                    descripcion_publica_mf = st.text_area("Descripción Pública de Finalización", value=desc_mf_calculada.strip(), height=100, key=f"desc_mf_{comunicado_cierre_mf['id']}")
                    
                    lista_fb_mf = cargar_correos_segmentados(comunicado_cierre_mf['servicio_id'], comunicado_cierre_mf['plataforma_id'], comunicado_cierre_mf['servicio_nom'], comunicado_cierre_mf.get('plataforma_nom', ''))
                    emails_apertura_json_mf = comunicado_cierre_mf.get('emails_apertura')
                    correos_input_ci_mf = ", ".join(json.loads(emails_apertura_json_mf)) if emails_apertura_json_mf else (", ".join(lista_fb_mf) if lista_fb_mf else "soporte@empresa.com")
                    correos_finales_ci_mf = st.text_area("Destinatarios", value=correos_input_ci_mf, height=70, key=f"txt_corr_mf_{comunicado_cierre_mf['id']}")
                    
                    if st.session_state.EXIGE_APROBACION: st.info("ℹ️ Tu rol requiere que esto pase por aprobación."); requiere_mt_f = True
                    else: requiere_mt_f = st.checkbox("Requiere Aprobación antes de enviar", value=False, key="chk_req_mt_f")
                    
                with col_fm2:
                    st.text_input("Asunto Cierre", value=asunto_mf_calculado.strip(), disabled=True, key=f"asunto_mf_{comunicado_cierre_mf['id']}")
                    solucion_interna_mf = st.text_area("Comentarios / Labores realizadas (Interno)", height=100, key=f"sol_mf_{comunicado_cierre_mf['id']}")
                    
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("Generar Vista Previa", type="primary", use_container_width=True):
                    fecha_hora_cierre_mf = datetime.datetime.combine(fecha_cierre_mf, hora_cierre_mf)
                    
                    if not plantilla_cierre_sel_mf: 
                        st.toast("Falta configurar plantilla de fin de ventana", icon="⚠️")
                    elif fecha_hora_cierre_mf < comunicado_cierre_mf['fecha_creacion']:
                        st.error(f"⚠️ La fecha y hora de finalización no puede ser anterior al inicio de la ventana ({comunicado_cierre_mf['fecha_creacion'].strftime('%Y-%m-%d %H:%M')}).")
                    elif fecha_hora_cierre_mf > datetime.datetime.now():
                        st.error("⚠️ La fecha y hora de finalización real no puede estar en el futuro.")
                    else:
                        es_global_mf = comunicado_cierre_mf.get('plataforma_nom', '').upper() == 'GENERAL'
                        es_masiva_mf = comunicado_cierre_mf['servicio_nom'].upper() == comunicado_cierre_mf.get('plataforma_nom', '').upper()
                        
                        st.session_state['show_dialog_mt_f'] = {
                            'html': Template(plantilla_cierre_sel_mf['html']).render(
                                consecutivo=comunicado_cierre_mf['consecutivo_num'], 
                                fecha_comunicado=formatear_fecha_es(datetime.date.today(), datetime.datetime.now().time()),
                                servicio=fmt_kwargs_mf['entidad'] if (es_global_mf or es_masiva_mf) else comunicado_cierre_mf['servicio_nom'], 
                                fecha_inicio=formatear_fecha_es(comunicado_cierre_mf['fecha_creacion'], comunicado_cierre_mf['fecha_creacion']),
                                fecha_cierre=formatear_fecha_es(fecha_cierre_mf, hora_cierre_mf),
                                descripcion_novedad=comunicado_cierre_mf['descripcion'],
                                tiempo_transcurrido=calcular_tiempo_transcurrido(comunicado_cierre_mf['fecha_creacion'], fecha_hora_cierre_mf),
                                descripcion_cierre=descripcion_publica_mf,
                                cliente=fmt_kwargs_mf['entidad'] 
                            ), 'solucion_interna': solucion_interna_mf, 'fecha_hora_cierre': fecha_hora_cierre_mf,
                            'comunicado_id': comunicado_cierre_mf['id'], 'tercero_id_ci': comunicado_cierre_mf.get('tercero_id'),
                            'correos_finales_ci': correos_finales_ci_mf, 'asunto_norm': asunto_mf_calculado.strip(), 'consecutivo': comunicado_cierre_mf['consecutivo_num'],
                            'db_data': {'requiere_aprobacion': requiere_mt_f}
                        }
                        st.rerun()

            if st.session_state.get('show_dialog_mt_f'):
                dialog_preview_mt_fin(st.session_state['show_dialog_mt_f'])

def view_historial():
    st.title("🕰️ Historial de Comunicados y Edición")
    
    query_ed = f"""SELECT c.id, c.consecutivo_num as Consecutivo, s.nombre as Servicio, c.estado as Estado, c.fecha_creacion as Fecha, c.asunto_final as Asunto, c.descripcion as Descripcion, c.solucion_aplicada as Solucion FROM comunicado c JOIN servicio s ON c.servicio_id = s.id WHERE 1=1 {get_filtros_datos('c')} ORDER BY c.id DESC"""
    df_raw = pd.DataFrame(DBManager.fetch_all(query_ed))
    
    if not df_raw.empty:
        c1, c2, c3, c4 = st.columns(4)
        filtro_txt = c1.text_input("🔎 Buscar (Asunto/Desc)")
        filtro_srv = c2.multiselect("Servicio", df_raw['Servicio'].unique())
        filtro_est = c3.multiselect("Estado", df_raw['Estado'].unique())
        filtro_fecha = c4.date_input("Fechas (Opcional)", [])
        
        df_filtrado = df_raw.copy()
        if filtro_txt: df_filtrado = df_filtrado[df_filtrado['Asunto'].str.contains(filtro_txt, case=False, na=False) | df_filtrado['Descripcion'].str.contains(filtro_txt, case=False, na=False)]
        if filtro_srv: df_filtrado = df_filtrado[df_filtrado['Servicio'].isin(filtro_srv)]
        if filtro_est: df_filtrado = df_filtrado[df_filtrado['Estado'].isin(filtro_est)]
        
        df_display = df_filtrado.copy()
        df_display['Fecha'] = pd.to_datetime(df_display['Fecha']).dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(
            df_display[['Consecutivo', 'Servicio', 'Estado', 'Fecha', 'Asunto']], 
            use_container_width=True, hide_index=True, height=250,
            column_config={"Estado": st.column_config.TextColumn("Estado", help="Estado actual del caso")}
        )
        
        st.divider()

        if st.session_state.ES_PUEDE_EDITAR:
            col_edi, col_reenv = st.columns(2)
            
            df_filtrado['Label_Select'] = df_filtrado['Consecutivo'] + " - " + df_filtrado['Asunto'].fillna("Sin Asunto")
            labels_list = df_filtrado['Label_Select'].tolist()
            
            if 'caso_a_editar' in st.session_state:
                try:
                    target_label = df_filtrado[df_filtrado['id'] == st.session_state['caso_a_editar']]['Label_Select'].iloc[0]
                    if target_label in labels_list:
                        st.session_state['sel_historial'] = target_label
                except IndexError: pass
                del st.session_state['caso_a_editar']
                
            edicion_sel_label = st.selectbox("Seleccione un Comunicado para interactuar", labels_list, key="sel_historial")
            
            if edicion_sel_label:
                row = df_filtrado[df_filtrado['Label_Select'] == edicion_sel_label].iloc[0]
                com_id = int(row['id'])
                old_desc = row['Descripcion'] if pd.notna(row['Descripcion']) else ""
                old_sol = row['Solucion'] if pd.notna(row['Solucion']) else ""
                
                with col_edi:
                    st.markdown("#### 🖊️ Edición de Textos (Auditable)")
                    with st.form("form_edicion"):
                        new_desc = st.text_area("Descripción (Pública)", value=old_desc, height=150)
                        new_sol = st.text_area("Solución (Interna)", value=old_sol, height=150)
                        
                        if st.form_submit_button("Guardar Cambios", type="primary", use_container_width=True):
                            cambios = False
                            if new_desc != old_desc:
                                DBManager.execute("INSERT INTO comunicado_historial (comunicado_id, analista_id, campo_modificado, valor_anterior, valor_nuevo) VALUES (%s,%s,%s,%s,%s)", (com_id, int(st.session_state.user_info['id']), 'descripcion', old_desc, new_desc)); cambios = True
                            if new_sol != old_sol:
                                DBManager.execute("INSERT INTO comunicado_historial (comunicado_id, analista_id, campo_modificado, valor_anterior, valor_nuevo) VALUES (%s,%s,%s,%s,%s)", (com_id, int(st.session_state.user_info['id']), 'solucion', old_sol, new_sol)); cambios = True
                                
                            if cambios:
                                if DBManager.execute("UPDATE comunicado SET descripcion = %s, solucion_aplicada = %s WHERE id = %s", (new_desc, new_sol, com_id)):
                                    registrar_auditoria(st.session_state.user_info['id'], 'EDICION_COMUNICADO', f"Editó textos del comunicado {row['Consecutivo']}")
                                    st.session_state['toasts'].append({"msg": f"El comunicado {row['Consecutivo']} fue actualizado.", "icon": "🖊️"})
                                    st.rerun()
                                else: st.error("Error de base de datos al intentar guardar.")
                            else: st.toast("No se detectaron cambios.", icon="ℹ️")

                with col_reenv:
                    st.markdown("#### ✉️ Despachar o Actualizar")
                    with st.form("form_reenvio"):
                        st.info("Despacha nuevamente el comunicado o envía una actualización de estado.")
                        com_record = DBManager.fetch_one("SELECT asunto_final, html_final, asunto_cierre, html_cierre, consecutivo_num FROM comunicado WHERE id = %s", (com_id,))
                        
                        dest_record = DBManager.fetch_one("SELECT email FROM comunicado_destinatario WHERE comunicado_id = %s LIMIT 1", (com_id,))
                        correos_originales = ""
                        if dest_record and dest_record.get('email'):
                            try: correos_originales = ", ".join(json.loads(dest_record['email']))
                            except: pass
                        
                        opciones_reenvio = ["Apertura / Novedad / Programación", "📢 Enviar Actualización de Estado"]
                        if com_record and com_record.get('html_cierre'): opciones_reenvio.append("Cierre / Normalidad / Fin Mantenimiento")
                            
                        tipo_reenvio = st.radio("¿Qué versión deseas despachar?", opciones_reenvio)
                        
                        mensaje_actualizacion = ""
                        if tipo_reenvio == "📢 Enviar Actualización de Estado":
                            st.markdown("<p style='font-size: 0.9rem; color: var(--cetacean-blue); font-weight: 600;'>Mensaje de Avance o Extensión de Tiempo</p>", unsafe_allow_html=True)
                            mensaje_actualizacion = st.text_area("Escribe aquí el texto de actualización", placeholder="Ej: Continuamos en labores de revisión con el aliado técnico. El SLA se extenderá 2 horas adicionales...", label_visibility="collapsed")
                            correos_prellenados = correos_originales
                        else:
                            correos_prellenados = ""
                        
                        st.markdown("<p style='font-size: 0.9rem; color: var(--cetacean-blue); font-weight: 600;'>Destinatarios Adicionales o Principales</p>", unsafe_allow_html=True)
                        correos_adicionales = st.text_area("Correos (separados por coma)", value=correos_prellenados, placeholder="ejemplo1@empresa.com, ejemplo2@empresa.com", height=80, label_visibility="collapsed")
                        
                        if st.form_submit_button("Generar Vista Previa de Despacho 🚀", type="primary", use_container_width=True):
                            if not correos_adicionales.strip(): st.warning("Debes ingresar al menos un correo válido.")
                            elif tipo_reenvio == "📢 Enviar Actualización de Estado" and not mensaje_actualizacion.strip():
                                st.warning("Debes escribir un mensaje para enviar la actualización.")
                            else:
                                correos_lista = [c.strip() for c in correos_adicionales.split(",") if c.strip() and es_correo_valido(c.strip())]
                                if not correos_lista: st.warning("No se detectaron correos válidos.")
                                else:
                                    asunto_reenvio = com_record['asunto_final']
                                    html_reenvio = com_record['html_final']
                                    
                                    if tipo_reenvio == "Cierre / Normalidad / Fin Mantenimiento":
                                        asunto_reenvio = com_record.get('asunto_cierre') or f"Cierre de Novedad - {com_record['consecutivo_num']}"
                                        html_reenvio = com_record['html_cierre']
                                        
                                    elif tipo_reenvio == "📢 Enviar Actualización de Estado":
                                        asunto_reenvio = f"ACTUALIZACIÓN: {com_record['asunto_final']}"
                                        banner_html = f"""
                                        <div style="background-color: #E3F2FD; border-left: 5px solid #2bbcee; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                                            <h3 style="margin-top: 0; margin-bottom: 8px; color: #10004F; font-family: Arial, sans-serif; font-size: 16px;">📢 Actualización de Novedad</h3>
                                            <p style="margin: 0; color: #10004F; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5;">{mensaje_actualizacion}</p>
                                        </div>
                                        """
                                        if '<h1 style="font-size: 22px;' in html_reenvio:
                                            html_reenvio = html_reenvio.replace('<h1 style="font-size: 22px;', banner_html + '<h1 style="font-size: 22px;')
                                        else:
                                            html_reenvio = banner_html + html_reenvio

                                    if not html_reenvio: st.error("No se encontró el formato HTML original.")
                                    else:
                                        st.session_state['show_dialog_reenvio'] = {
                                            'asunto': asunto_reenvio, 'html': html_reenvio, 'correos': ", ".join(correos_lista),
                                            'lista_correos': correos_lista, 'tipo_reenvio': tipo_reenvio,
                                            'consecutivo': com_record['consecutivo_num'], 'com_id': com_id
                                        }
                                        st.rerun()

        if st.session_state.get('show_dialog_reenvio'):
            dialog_preview_reenvio(st.session_state['show_dialog_reenvio'])

    else: 
        st.info("No tienes comunicados disponibles en tu ámbito de acceso.")

def view_reportes():
    st.title("📊 Informes y Métricas")
    try: reportes.render_tab_reportes(DBManager)
    except NameError: st.info("Módulo de reportes no disponible en este momento. Verifica el archivo `modulo_reportes.py`.")

def view_admin():
    st.title("⚙️ Panel de Administración y Auditoría")

    admin_menu = st.pills("Selecciona un módulo:", [
        "Configuración Global (SLA)", "Reglas de Textos (Motor)", "Roles y Permisos", "Servicios", "Terceros (Aliados)", "Vincular Servicio-Tercero", 
        "Correos de Servicios", "Correos Internos", "Usuarios", "Plantillas HTML", "Auditoría"
    ], default="Reglas de Textos (Motor)")
    st.divider()

    if admin_menu == "Reglas de Textos (Motor)":
        st.markdown("#### 🏗️ Asistente de Creación y Edición de Reglas")
        st.info("Utiliza este asistente para configurar el armado de textos. Al escribir, observarás a la derecha cómo lucirá la plantilla generada.")
        
        opt_plats = [{"id": None, "nombre": "(Cualquier Plataforma)"}] + st.session_state.plataformas
        opt_servs = [{"id": None, "nombre": "(Cualquier Servicio)"}] + st.session_state.servicios
        opt_tipos = [{"id": None, "nombre": "(Cualquier Tipo)"}] + st.session_state.tipos
        opt_tercs = [{"id": None, "nombre": "(Cualquier Tercero)"}] + obtener_todos_terceros()

        reglas_existentes = DBManager.fetch_all("""
            SELECT r.*, p.nombre as plat_nom, s.nombre as serv_nom, tc.nombre as tipo_nom, t.nombre as terc_nom 
            FROM regla_texto r 
            LEFT JOIN plataforma p ON r.plataforma_id = p.id 
            LEFT JOIN servicio s ON r.servicio_id = s.id 
            LEFT JOIN tipo_comunicado tc ON r.tipo_comunicado_id = tc.id 
            LEFT JOIN tercero t ON r.tercero_id = t.id
            WHERE r.estado = 1 ORDER BY r.fase ASC, r.id DESC
        """)

        modo_regla = st.radio("Acción a realizar:", ["✨ Crear Nueva Regla", "✏️ Editar Regla Existente"], horizontal=True)
        st.markdown("<br>", unsafe_allow_html=True)

        regla_activa = None
        if modo_regla == "✏️ Editar Regla Existente":
            if not reglas_existentes:
                st.warning("No hay reglas configuradas para editar.")
            else:
                dic_r = {f"ID: {r['id']} | Fase: {r['fase']} | Plat: {r['plat_nom'] or '*'} | Serv: {r['serv_nom'] or '*'} | Terc: {r['terc_nom'] or '*'}": r for r in reglas_existentes}
                sel_r_key = st.selectbox("Seleccione la Regla a Editar", list(dic_r.keys()))
                regla_activa = dic_r[sel_r_key]
        
        def get_index(lst, key_name, val):
            for i, item in enumerate(lst):
                if isinstance(item, dict) and item.get(key_name) == val: return i
            return 0

        idx_fase = ["APERTURA", "CIERRE", "MANTENIMIENTO", "FIN_MANTENIMIENTO"].index(regla_activa['fase']) if regla_activa else 0
        idx_plat = get_index(opt_plats, 'id', regla_activa['plataforma_id']) if regla_activa else 0
        idx_serv = get_index(opt_servs, 'id', regla_activa['servicio_id']) if regla_activa else 0
        idx_terc = get_index(opt_tercs, 'id', regla_activa['tercero_id']) if regla_activa else 0
        idx_tipo = get_index(opt_tipos, 'id', regla_activa['tipo_comunicado_id']) if regla_activa else 0

        col_c1, col_c2, col_c3 = st.columns(3)
        fase_regla = col_c1.selectbox("1️⃣ Fase de Ejecución", ["APERTURA", "CIERRE", "MANTENIMIENTO", "FIN_MANTENIMIENTO"], index=idx_fase)
        plat_regla = col_c2.selectbox("2️⃣ Plataforma", [p['nombre'] for p in opt_plats], index=idx_plat)
        serv_regla = col_c3.selectbox("3️⃣ Servicio", [s['nombre'] for s in opt_servs], index=idx_serv)

        col_c4, col_c5 = st.columns(2)
        terc_regla = col_c4.selectbox("4️⃣ Tercero (Aliado)", [t['nombre'] for t in opt_tercs], index=idx_terc)
        tipo_regla = col_c5.selectbox("5️⃣ Tipo Comunicado", [t['nombre'] for t in opt_tipos], index=idx_tipo)

        st.markdown("<br>##### ✍️ Redacción Interactiva", unsafe_allow_html=True)
        st.markdown("**Variables Dinámicas Disponibles (Cópialas y pégalas en los campos):** `{consecutivo}` `{plataforma}` `{servicio}` `{tercero}` `{entidad}`")

        col_ed, col_prev = st.columns([1.1, 0.9])

        with col_ed:
            def_ent = regla_activa['entidad_afectada'] if regla_activa else "la entidad {tercero}"
            def_asu = regla_activa['asunto_template'] if regla_activa else "{consecutivo} - Novedad en el servicio de {servicio}"
            def_desc = regla_activa['descripcion_template'] if regla_activa else "Se informa que {entidad} presenta novedad en el servicio de {servicio}. La incidencia ha sido escalada internamente."

            entidad_regla = st.text_input("Definición de Entidad Afectada", value=def_ent)
            asunto_regla = st.text_input("Estructura del Asunto", value=def_asu)
            desc_regla = st.text_area("Cuerpo / Descripción Principal", value=def_desc, height=150)

            btn_label = "💾 Guardar Nueva Regla Automática" if modo_regla == "✨ Crear Nueva Regla" else "💾 Actualizar Regla Existente"
            
            if st.button(btn_label, type="primary", use_container_width=True):
                p_id = next(p['id'] for p in opt_plats if p['nombre'] == plat_regla)
                s_id = next(s['id'] for s in opt_servs if s['nombre'] == serv_regla)
                terc_id = next(t['id'] for t in opt_tercs if t['nombre'] == terc_regla)
                t_id = next(t['id'] for t in opt_tipos if t['nombre'] == tipo_regla)
                
                if not asunto_regla or not desc_regla:
                    st.warning("⚠️ El Asunto y la Descripción son obligatorios para guardar.")
                else:
                    if modo_regla == "✨ Crear Nueva Regla":
                        DBManager.execute("""
                            INSERT INTO regla_texto (plataforma_id, servicio_id, tercero_id, tipo_comunicado_id, fase, entidad_afectada, asunto_template, descripcion_template) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (p_id, s_id, terc_id, t_id, fase_regla, entidad_regla, asunto_regla, desc_regla))
                        registrar_auditoria(st.session_state.user_info['id'], 'ADMIN_REGLAS', f"Creó regla para fase {fase_regla}")
                        st.session_state['toasts'].append({"msg": "Regla guardada correctamente.", "icon": "✔️"})
                    else:
                        DBManager.execute("""
                            UPDATE regla_texto 
                            SET plataforma_id=%s, servicio_id=%s, tercero_id=%s, tipo_comunicado_id=%s, fase=%s, entidad_afectada=%s, asunto_template=%s, descripcion_template=%s
                            WHERE id=%s
                        """, (p_id, s_id, terc_id, t_id, fase_regla, entidad_regla, asunto_regla, desc_regla, regla_activa['id']))
                        registrar_auditoria(st.session_state.user_info['id'], 'ADMIN_REGLAS', f"Actualizó regla ID {regla_activa['id']}")
                        st.session_state['toasts'].append({"msg": "Regla actualizada correctamente.", "icon": "✔️"})
                    st.rerun()

        # Renderizado de Vista Previa (Simulador en tiempo real)
        with col_prev:
            st.markdown("<div class='preview-box'>", unsafe_allow_html=True)
            st.markdown("<h5 style='margin-top: 0; color: #d51b5d;'>👁️ Vista Previa del Simulador</h5>", unsafe_allow_html=True)
            
            # Textos de reemplazo Dummy
            dummy_plat = "Moviired" if plat_regla == "(Cualquier Plataforma)" else plat_regla
            dummy_serv = "Billetera Digital" if serv_regla == "(Cualquier Servicio)" else serv_regla
            dummy_terc = "Banco Aliado" if terc_regla == "(Cualquier Tercero)" else terc_regla
            
            mock_entidad = format_seguro(entidad_regla, tercero=dummy_terc)
            mock_asunto = format_seguro(asunto_regla, consecutivo="CMO-999", plataforma=dummy_plat, servicio=dummy_serv, tercero=dummy_terc, entidad=mock_entidad)
            mock_desc = format_seguro(desc_regla, consecutivo="CMO-999", plataforma=dummy_plat, servicio=dummy_serv, tercero=dummy_terc, entidad=mock_entidad)

            st.markdown(f"**Asunto resultante:**<br><span style='color:#10004F; font-size:1.1rem; font-weight:600;'>{mock_asunto}</span>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 15px 0 !important; border-top: 1px dashed #ccc !important;'>", unsafe_allow_html=True)
            st.markdown(f"**Descripción resultante:**<br><span style='color:#333; font-size:1.05rem;'>{mock_desc}</span>", unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br><h5>Reglas Configuradas Actualmente</h5>", unsafe_allow_html=True)
        
        if reglas_existentes:
            df_reglas = pd.DataFrame(reglas_existentes)
            df_reglas_disp = df_reglas[['id', 'fase', 'plat_nom', 'serv_nom', 'terc_nom', 'tipo_nom', 'asunto_template']].copy()
            df_reglas_disp.columns = ['ID', 'Fase', 'Plataforma', 'Servicio', 'Tercero', 'Tipo', 'Plantilla Asunto']
            df_reglas_disp.fillna('(Cualquiera)', inplace=True)
            st.dataframe(df_reglas_disp, use_container_width=True, hide_index=True)
            
            st.markdown("##### 🗑️ Eliminar Regla")
            with st.form("form_eliminar_regla"):
                opciones_del = {f"ID: {r['id']} | Fase: {r['fase']} | Plat: {r['plat_nom'] or '*'} | Serv: {r['serv_nom'] or '*'} | Terc: {r['terc_nom'] or '*'}": r['id'] for r in reglas_existentes}
                regla_a_eliminar = st.selectbox("Seleccione la regla que desea eliminar", list(opciones_del.keys()))
                
                if st.form_submit_button("Eliminar Regla", type="primary"):
                    if DBManager.execute("DELETE FROM regla_texto WHERE id = %s", (opciones_del[regla_a_eliminar],)):
                        registrar_auditoria(st.session_state.user_info['id'], 'ADMIN_REGLAS', f"Eliminó regla ID {opciones_del[regla_a_eliminar]}")
                        st.session_state['toasts'].append({"msg": "Regla eliminada exitosamente.", "icon": "🗑️"})
                        st.rerun()
                    else:
                        st.error("Error al eliminar la regla en la base de datos.")
        else:
            st.info("No hay reglas activas configuradas.")

    elif admin_menu == "Configuración Global (SLA)":
        st.markdown("#### ⚙️ Configuración del Sistema y SLA")
        st.info("Ajusta los tiempos de resolución y los canales de notificación para escalaciones críticas.")
        
        with st.form("form_config"):
            c1, c2 = st.columns(2)
            with c1:
                new_sla = st.number_input("Horas Límite para SLA", min_value=1, max_value=72, value=st.session_state.config_sis['sla_horas'])
            new_esc = st.text_input("Correo(s) Escalación", value=st.session_state.config_sis['correo_escalacion'])
            new_seg = st.text_input("Correo Seguridad", value=st.session_state.config_sis['correo_seguridad'])

            if st.form_submit_button("Actualizar", type="primary"):
                if DBManager.execute("UPDATE configuracion_sistema SET sla_horas=%s, correo_escalacion=%s, correo_seguridad=%s WHERE id=1", (new_sla, new_esc, new_seg)):
                    registrar_auditoria(st.session_state.user_info['id'], 'ADMIN_CRITICO', "Actualizó configuración global del SLA.")
                    st.session_state['toasts'].append({"msg": "Actualizado.", "icon": "✔️"})
                    st.cache_data.clear()
                    st.rerun()

    elif admin_menu == "Roles y Permisos":
        st.markdown("#### 🔐 Gestión Dinámica de Accesos")
        roles_list = list(set([r['rol'].capitalize() for r in DBManager.fetch_all("SELECT DISTINCT rol FROM analista")] + ["Administrador", "Lider", "Monitoreo", "Corporate"]))
        rol_sel = st.selectbox("Seleccione un Rol para configurar", sorted(roles_list))
        
        permisos_actuales = DBManager.fetch_one("SELECT * FROM rol_permisos WHERE LOWER(rol_nombre) = LOWER(%s)", (rol_sel,)) or {'ver_aprobaciones': 0, 'ver_apertura': 1, 'ver_cierre': 1, 'ver_mantenimiento': 1, 'ver_edicion': 1, 'ver_reportes': 1, 'ver_admin': 0, 'puede_aprobar': 0, 'ver_solo_propios': 0, 'exige_aprobacion': 1}
        serv_activos = obtener_todos_servicios()
        nombres_restricted = [s['nombre'] for s in serv_activos if s['id'] in [r['servicio_id'] for r in DBManager.fetch_all("SELECT servicio_id FROM rol_servicios WHERE LOWER(rol_nombre) = LOWER(%s)", (rol_sel,))]]
        
        with st.form("form_permisos"):
            st.markdown(f"**Visibilidad de Módulos (Sidebar) para: {rol_sel}**")
            c1, c2, c3 = st.columns(3)
            p_apr = c1.checkbox("Bandeja de Aprobaciones", value=bool(permisos_actuales.get('ver_aprobaciones')))
            p_ape = c1.checkbox("Apertura de Novedad", value=bool(permisos_actuales.get('ver_apertura')))
            p_cie = c1.checkbox("Cierre de Novedad", value=bool(permisos_actuales.get('ver_cierre')))
            p_man = c2.checkbox("Mantenimientos", value=bool(permisos_actuales.get('ver_mantenimiento')))
            p_edi = c2.checkbox("Editar / Historial", value=bool(permisos_actuales.get('ver_edicion')))
            p_rep = c2.checkbox("Informes y Métricas", value=bool(permisos_actuales.get('ver_reportes')))
            p_adm = c3.checkbox("Panel de Administración", value=bool(permisos_actuales.get('ver_admin')))
                
            st.markdown("**Permisos de Flujo de Trabajo**")
            p_p_apr = st.checkbox("✔️ Capacidad de Aprobar Casos", value=bool(permisos_actuales.get('puede_aprobar')))
            p_exige_apr = st.checkbox("🔒 Envíos requieren aprobación", value=bool(permisos_actuales.get('exige_aprobacion')))
                
            st.markdown("**Restricciones de Datos (ABAC)**")
            p_propios = st.checkbox("👁️ Ver SÓLO casos propios", value=bool(permisos_actuales.get('ver_solo_propios')))
            serv_seleccionados = st.multiselect("Restringir acceso SÓLO a estos servicios (Vacío = Todos)", [s['nombre'] for s in serv_activos], default=nombres_restricted)
            
            if st.form_submit_button("Actualizar Permisos de Rol", type="primary"):
                conn_rbac = DBManager.get_conn()
                if conn_rbac:
                    cursor_rbac = conn_rbac.cursor()
                    try:
                        cursor_rbac.execute("SELECT rol_nombre FROM rol_permisos WHERE LOWER(rol_nombre) = LOWER(%s)", (rol_sel,))
                        if cursor_rbac.fetchone(): 
                            cursor_rbac.execute("UPDATE rol_permisos SET ver_aprobaciones=%s, ver_apertura=%s, ver_cierre=%s, ver_mantenimiento=%s, ver_edicion=%s, ver_reportes=%s, ver_admin=%s, puede_aprobar=%s, ver_solo_propios=%s, exige_aprobacion=%s WHERE LOWER(rol_nombre)=LOWER(%s)", (p_apr, p_ape, p_cie, p_man, p_edi, p_rep, p_adm, p_p_apr, p_propios, p_exige_apr, rol_sel))
                        else: 
                            cursor_rbac.execute("INSERT INTO rol_permisos (rol_nombre, ver_aprobaciones, ver_apertura, ver_cierre, ver_mantenimiento, ver_edicion, ver_reportes, ver_admin, puede_aprobar, ver_solo_propios, exige_aprobacion) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (rol_sel.capitalize(), p_apr, p_ape, p_cie, p_man, p_edi, p_rep, p_adm, p_p_apr, p_propios, p_exige_apr))
                                                
                        cursor_rbac.execute("DELETE FROM rol_servicios WHERE LOWER(rol_nombre) = LOWER(%s)", (rol_sel,))
                        if serv_seleccionados:
                            for nom in serv_seleccionados: 
                                cursor_rbac.execute("INSERT INTO rol_servicios (rol_nombre, servicio_id) VALUES (%s, %s)", (rol_sel.capitalize(), next(s['id'] for s in serv_activos if s['nombre'] == nom)))
                                
                        conn_rbac.commit()
                        registrar_auditoria(st.session_state.user_info['id'], 'ADMIN_RBAC', f"Actualizó configuración de rol: {rol_sel}")
                        st.session_state['toasts'].append({"msg": "Permisos actualizados.", "icon": "✔️"})
                        st.rerun()
                    except Error as e:
                        conn_rbac.rollback()
                        st.error("Error al actualizar la base de datos.")
                    finally:
                        cursor_rbac.close()
                        conn_rbac.close()

    elif admin_menu == "Plantillas HTML":
        st.markdown("#### 🎨 Gestor Visual de Plantillas")
        modo_plantilla = st.radio("Acción", ["Crear Nueva Plantilla", "Editar Existente"], horizontal=True, label_visibility="collapsed")
        
        if modo_plantilla == "Crear Nueva Plantilla":
            col_p1, col_p2 = st.columns([1, 1])
            with col_p1:
                with st.form("form_nueva_plantilla"):
                    plat_sel_p = st.selectbox("Plataforma", ["(Aplica a todas)"] + [p['nombre'] for p in st.session_state.plataformas])
                    tipo_sel_p = st.selectbox("Tipo de Comunicado", [t['nombre'] for t in st.session_state.tipos])
                    asunto_p = st.text_input("Asunto / Nombre")
                    html_p = st.text_area("Código HTML", height=300)
                    
                    btn_preview = st.form_submit_button("Previsualizar (Prueba)")
                    btn_save = st.form_submit_button("Guardar Plantilla", type="primary")
                    
            with col_p2:
                if btn_preview and html_p:
                    try: mostrar_vista_previa(Template(html_p).render(consecutivo="PRE-123", servicio="Servicio Prueba", descripcion="Texto de prueba.", cliente="Cliente Prueba", fecha_inicio="01 Ene 2026", fecha_cierre="02 Ene 2026", fecha_comunicado="01 Ene 2026", tiempo_estimado="2 h", tiempo_transcurrido="1 h"), height=450)
                    except Exception as e: st.error(f"Error Jinja2: {e}")
                    
            if btn_save:
                if not asunto_p.strip() or not html_p.strip(): st.warning("Asunto y HTML son obligatorios.")
                else:
                    if DBManager.execute("INSERT INTO plantilla (plataforma_id, tipo_comunicado_id, version, asunto, html, estado) VALUES (%s, %s, 1, %s, %s, TRUE)", (None if plat_sel_p == "(Aplica a todas)" else next(p['id'] for p in st.session_state.plataformas if p['nombre'] == plat_sel_p), next(t['id'] for t in st.session_state.tipos if t['nombre'] == tipo_sel_p), asunto_p.strip(), html_p)):
                        st.session_state['toasts'].append({"msg": "Plantilla creada.", "icon": "✔️"})
                        st.rerun()
                        
        else: 
            if st.session_state.plantillas:
                dic_pl = {f"ID: {p['id']} - {p['asunto']}": p for p in st.session_state.plantillas}
                pl_data = dic_pl[st.selectbox("Seleccione Plantilla a Editar", list(dic_pl.keys()))]
                
                col_p1, col_p2 = st.columns([1, 1])
                with col_p1:
                    with st.form("form_editar_plantilla"):
                        asunto_edit_p = st.text_input("Asunto", value=pl_data['asunto'])
                        html_edit_p = st.text_area("Código HTML", value=pl_data['html'], height=400)
                        estado_edit_p = st.checkbox("Plantilla Activa", value=bool(pl_data.get('estado', True)))
                        btn_preview_edit = st.form_submit_button("Previsualizar Cambios")
                        btn_update = st.form_submit_button("Actualizar Plantilla en BD", type="primary")
                        
                with col_p2:
                    if btn_preview_edit or not btn_update:
                        try: mostrar_vista_previa(Template(html_edit_p).render(consecutivo="PRE-123", servicio="Servicio Prueba", descripcion="Texto modificado.", cliente="Cliente Prueba", fecha_inicio="01 Ene 2026", fecha_cierre="02 Ene 2026", fecha_comunicado="01 Ene 2026", tiempo_estimado="2 h", tiempo_transcurrido="1 h"), height=500)
                        except Exception as e: st.error(f"Error Jinja2: {e}")
                            
                if btn_update:
                    if not asunto_edit_p.strip() or not html_edit_p.strip(): st.warning("Requeridos.")
                    else:
                        if DBManager.execute("UPDATE plantilla SET asunto=%s, html=%s, estado=%s WHERE id=%s", (asunto_edit_p.strip(), html_edit_p, estado_edit_p, pl_data['id'])):
                            st.session_state['toasts'].append({"msg": "Plantilla actualizada.", "icon": "✔️"})
                            st.cache_data.clear()
                            st.rerun()
            else: st.info("No hay plantillas.")

    elif admin_menu == "Auditoría":
        st.markdown("#### 📑 Registro de Actividades y Seguridad")
        logs = DBManager.fetch_all("SELECT al.fecha, an.nombre as analista, al.accion, al.detalles FROM audit_log al LEFT JOIN analista an ON al.analista_id = an.id ORDER BY al.id DESC LIMIT 200")
        if logs: 
            df_logs = pd.DataFrame(logs)
            df_logs['fecha'] = pd.to_datetime(df_logs['fecha']).dt.strftime('%Y-%m-%d %H:%M:%S')
            st.dataframe(df_logs, use_container_width=True, hide_index=True)
        else: st.info("No hay logs registrados.")

    elif admin_menu == "Servicios":
        todos_servicios = obtener_todos_servicios()
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            with st.form("form_nuevo_servicio", clear_on_submit=True):
                st.markdown("**Crear Nuevo Servicio**")
                nuevo_nom_serv = st.text_input("Nombre del Servicio")
                if st.form_submit_button("Crear Servicio", type="primary"):
                    if not nuevo_nom_serv.strip(): st.warning("El nombre no puede estar vacío.")
                    else:
                        DBManager.execute("INSERT INTO servicio (nombre, estado) VALUES (%s, TRUE)", (nuevo_nom_serv.upper().strip(),))
                        st.session_state['toasts'].append({"msg": "Servicio creado con éxito.", "icon": "✔️"})
                        st.cache_data.clear()
                        st.rerun()
        with col_s2:
            if todos_servicios:
                st.markdown("**Editar Servicio**")
                dic_servicios = {s['nombre']: s for s in todos_servicios}
                serv_sel_data = dic_servicios[st.selectbox("Seleccionar Servicio", list(dic_servicios.keys()))]
                with st.form("form_editar_servicio"):
                    nuevo_nom_edit = st.text_input("Editar Nombre", value=serv_sel_data['nombre'])
                    nuevo_estado_edit = st.checkbox("Activo", value=bool(serv_sel_data['estado']))
                    if st.form_submit_button("Actualizar"):
                        DBManager.execute("UPDATE servicio SET nombre=%s, estado=%s WHERE id=%s", (nuevo_nom_edit.upper().strip(), nuevo_estado_edit, serv_sel_data['id']))
                        st.session_state['toasts'].append({"msg": "Actualizado.", "icon": "✔️"})
                        st.cache_data.clear()
                        st.rerun()

    elif admin_menu == "Terceros (Aliados)":
        todos_terceros = obtener_todos_terceros()
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            with st.form("form_nuevo_tercero", clear_on_submit=True):
                st.markdown("**Crear Nuevo Tercero**")
                nuevo_nom_terc = st.text_input("Nombre")
                if st.form_submit_button("Crear", type="primary"):
                    if not nuevo_nom_terc.strip(): st.warning("Vacío no permitido.")
                    else:
                        DBManager.execute("INSERT INTO tercero (nombre, estado) VALUES (%s, TRUE)", (nuevo_nom_terc.upper().strip(),))
                        st.session_state['toasts'].append({"msg": "Creado.", "icon": "✔️"})
                        st.cache_data.clear()
                        st.rerun()
        with col_t2:
            if todos_terceros:
                st.markdown("**Editar Tercero**")
                dic_terceros = {t['nombre']: t for t in todos_terceros}
                terc_sel_data = dic_terceros[st.selectbox("Seleccionar", list(dic_terceros.keys()))]
                with st.form("form_editar_tercero"):
                    nuevo_nom_edit_t = st.text_input("Nombre", value=terc_sel_data['nombre'])
                    nuevo_estado_edit_t = st.checkbox("Activo", value=bool(terc_sel_data['estado']))
                    if st.form_submit_button("Actualizar"):
                        DBManager.execute("UPDATE tercero SET nombre=%s, estado=%s WHERE id=%s", (nuevo_nom_edit_t.upper().strip(), nuevo_estado_edit_t, terc_sel_data['id']))
                        st.session_state['toasts'].append({"msg": "Actualizado.", "icon": "✔️"})
                        st.cache_data.clear()
                        st.rerun()

    elif admin_menu == "Vincular Servicio-Tercero":
        servs_activos = [s for s in obtener_todos_servicios() if s['estado']]
        tercs_activos = [t for t in obtener_todos_terceros() if t['estado']]
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            with st.form("form_relacion_crear", clear_on_submit=True):
                st.markdown("**Vincular**")
                serv_sel_rel = st.selectbox("Servicio", [s['nombre'] for s in servs_activos])
                terc_sel_rel = st.selectbox("Tercero", [t['nombre'] for t in tercs_activos])
                if st.form_submit_button("Vincular", type="primary"):
                    id_s = next(s['id'] for s in servs_activos if s['nombre'] == serv_sel_rel)
                    id_t = next(t['id'] for t in tercs_activos if t['nombre'] == terc_sel_rel)
                    if DBManager.fetch_one("SELECT id FROM servicio_tercero WHERE servicio_id=%s AND tercero_id=%s", (id_s, id_t)): st.warning("Ya existe.")
                    else:
                        DBManager.execute("INSERT INTO servicio_tercero (servicio_id, tercero_id) VALUES (%s, %s)", (id_s, id_t))
                        st.session_state['toasts'].append({"msg": "Vinculado.", "icon": "✔️"})
                        st.cache_data.clear()
                        st.rerun()
        with col_r2:
            st.markdown("**Desvincular**")
            serv_sel_ver = st.selectbox("Ver relaciones de", [s['nombre'] for s in servs_activos], key="sel_s_ver")
            id_s_ver = next(s['id'] for s in servs_activos if s['nombre'] == serv_sel_ver)
            relaciones = DBManager.fetch_all("SELECT st.id, t.nombre FROM servicio_tercero st JOIN tercero t ON st.tercero_id = t.id WHERE st.servicio_id = %s", (id_s_ver,))
            if relaciones:
                dic_rels = {r['nombre']: r['id'] for r in relaciones}
                rel_sel_eliminar = st.selectbox("Seleccionar Tercero para Desvincular", list(dic_rels.keys()))
                with st.form("form_relacion_eliminar"):
                    if st.form_submit_button("Desvincular"):
                        DBManager.execute("DELETE FROM servicio_tercero WHERE id = %s", (dic_rels[rel_sel_eliminar],))
                        st.session_state['toasts'].append({"msg": "Desvinculado.", "icon": "✔️"})
                        st.cache_data.clear()
                        st.rerun()

    elif admin_menu == "Correos de Servicios":
        servs_activos = [s for s in obtener_todos_servicios() if s['estado']]
        serv_sel_corr_ui = st.selectbox("Buscar por Servicio", [s['nombre'] for s in servs_activos], key="sel_serv_corr_admin")
        id_s_corr = next(s['id'] for s in servs_activos if s['nombre'] == serv_sel_corr_ui)
        correos_existentes = DBManager.fetch_all("SELECT sc.id, sc.email, sc.nombre as contacto_nom, sc.estado, sc.plataforma_id, p.nombre as plataforma_nom, sc.tercero_id, t.nombre as tercero_nom FROM servicio_correo sc LEFT JOIN plataforma p ON sc.plataforma_id = p.id LEFT JOIN tercero t ON sc.tercero_id = t.id WHERE sc.servicio_id=%s", (id_s_corr,))
        st.divider()

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            with st.form("form_nuevo_correo", clear_on_submit=True):
                st.markdown("**Agregar Correo(s)**")
                nuevo_nombre_contacto = st.text_input("Nombre de Contacto (Opcional)")
                nuevo_email_str = st.text_area("Correos (separados por coma)")
                plat_sel_corr_nom = st.selectbox("Plataforma", ["Global"] + [p['nombre'] for p in st.session_state.plataformas])
                terceros_del_servicio = cargar_terceros_por_servicio(id_s_corr)
                terc_sel_corr_nom = st.selectbox("Tercero", ["Ninguno"] + [t['nombre'] for t in terceros_del_servicio])
                
                if st.form_submit_button("Guardar", type="primary"):
                    correos_lista = [c.strip().lower() for c in nuevo_email_str.replace('\n', ',').split(',') if c.strip() and es_correo_valido(c.strip())]
                    if correos_lista:
                        plat_id = None if plat_sel_corr_nom == "Global" else next(p['id'] for p in st.session_state.plataformas if p['nombre'] == plat_sel_corr_nom)
                        t_id = None if terc_sel_corr_nom == "Ninguno" else next(t['id'] for t in terceros_del_servicio if t['nombre'] == terc_sel_corr_nom)
                        for em in correos_lista: DBManager.execute("INSERT INTO servicio_correo (servicio_id, nombre, email, estado, plataforma_id, tercero_id) VALUES (%s, %s, %s, TRUE, %s, %s)", (id_s_corr, nuevo_nombre_contacto.strip(), em, plat_id, t_id))
                        st.session_state['toasts'].append({"msg": "Guardado.", "icon": "✔️"})
                        st.rerun()
        with col_c2:
            if correos_existentes:
                st.markdown("**Editar Correo**")
                dic_correos = {f"{c['contacto_nom']} - {c['email']}": c for c in correos_existentes}
                correo_data = dic_correos[st.selectbox("Seleccionar", list(dic_correos.keys()))]
                with st.form("form_editar_correo"):
                    nombre_edit_val = st.text_input("Nombre", value=correo_data['contacto_nom'])
                    email_edit_val = st.text_input("Dirección", value=correo_data['email'])
                    estado_corr_edit = st.checkbox("Activo", value=bool(correo_data['estado']))
                    if st.form_submit_button("Actualizar"):
                        DBManager.execute("UPDATE servicio_correo SET nombre=%s, email=%s, estado=%s WHERE id=%s", (nombre_edit_val.strip(), email_edit_val.strip().lower(), estado_corr_edit, correo_data['id']))
                        st.session_state['toasts'].append({"msg": "Actualizado.", "icon": "✔️"})
                        st.rerun()

    elif admin_menu == "Correos Internos":
        internos_existentes = DBManager.fetch_all("SELECT id, email, estado FROM correo_interno_cc")
        col_ci1, col_ci2 = st.columns(2)
        with col_ci1:
            with st.form("form_nuevo_interno", clear_on_submit=True):
                nuevo_interno_str = st.text_area("Correos Internos (separados por coma)")
                if st.form_submit_button("Guardar", type="primary"):
                    correos_lista = [c.strip().lower() for c in nuevo_interno_str.replace('\n', ',').split(',') if c.strip() and es_correo_valido(c.strip())]
                    for em in correos_lista: DBManager.execute("INSERT INTO correo_interno_cc (email, estado) VALUES (%s, TRUE)", (em,))
                    st.session_state['toasts'].append({"msg": "Guardado.", "icon": "✔️"})
                    st.rerun()
        with col_ci2:
            if internos_existentes:
                dic_int = {c['email']: c for c in internos_existentes}
                int_data = dic_int[st.selectbox("Seleccionar", list(dic_int.keys()))]
                with st.form("form_editar_interno"):
                    int_edit_val = st.text_input("Dirección", value=int_data['email'])
                    estado_int_edit = st.checkbox("Activo", value=bool(int_data['estado']))
                    if st.form_submit_button("Actualizar"):
                        DBManager.execute("UPDATE correo_interno_cc SET email=%s, estado=%s WHERE id=%s", (int_edit_val.strip().lower(), estado_int_edit, int_data['id']))
                        st.session_state['toasts'].append({"msg": "Actualizado.", "icon": "✔️"})
                        st.rerun()

    elif admin_menu == "Usuarios":
        todos_analistas = DBManager.fetch_all("SELECT id, nombre, apellido, correo, rol, estado, password FROM analista")
        roles_disponibles = ["Monitoreo", "Corporate", "Lider", "Administrador"]
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            with st.form("form_nuevo_usuario", clear_on_submit=True):
                st.markdown("**Crear Usuario**")
                nuevo_nom, nuevo_ape = st.text_input("Nombre"), st.text_input("Apellido")
                nuevo_correo, nuevo_pass = st.text_input("Correo"), st.text_input("Contraseña", type="password")
                nuevo_rol = st.selectbox("Rol", roles_disponibles)
                if st.form_submit_button("Crear", type="primary"):
                    if DBManager.execute("INSERT INTO analista (nombre, apellido, correo, password, rol, estado) VALUES (%s, %s, %s, %s, %s, TRUE)", (nuevo_nom.strip(), nuevo_ape.strip(), nuevo_correo.strip().lower(), hash_password(nuevo_pass), nuevo_rol)):
                        st.session_state['toasts'].append({"msg": "Creado.", "icon": "✔️"})
                        st.cache_data.clear()
                        st.rerun()
        with col_u2:
            if todos_analistas:
                dic_analistas = {f"{u['nombre']} {u['apellido']} ({u['correo']})": u for u in todos_analistas}
                usr_data = dic_analistas[st.selectbox("Seleccionar Usuario", list(dic_analistas.keys()))]
                with st.form("form_editar_usuario"):
                    edit_nom, edit_ape, edit_correo = st.text_input("Nombre", value=usr_data['nombre']), st.text_input("Apellido", value=usr_data['apellido']), st.text_input("Correo", value=usr_data['correo'])
                    edit_pass = st.text_input("Nueva Contraseña (dejar vacío si no cambia)", type="password")
                    edit_rol = st.selectbox("Rol", roles_disponibles, index=roles_disponibles.index(usr_data['rol']) if usr_data['rol'] in roles_disponibles else 0)
                    edit_estado = st.checkbox("Activo", value=bool(usr_data['estado']))
                    if st.form_submit_button("Actualizar"):
                        pass_a_guardar = hash_password(edit_pass) if edit_pass else usr_data['password']
                        if bool(usr_data['estado']) and not edit_estado: registrar_auditoria(st.session_state.user_info['id'], 'ADMIN_CRITICO', f"Desactivó: {usr_data['correo']}")
                        DBManager.execute("UPDATE analista SET nombre=%s, apellido=%s, correo=%s, password=%s, rol=%s, estado=%s WHERE id=%s", (edit_nom.strip(), edit_ape.strip(), edit_correo.strip().lower(), pass_a_guardar, edit_rol, edit_estado, usr_data['id']))
                        st.session_state['toasts'].append({"msg": "Actualizado.", "icon": "✔️"})
                        st.cache_data.clear()
                        st.rerun()


# ==========================================
# MOTOR PRINCIPAL DE NAVEGACIÓN (st.navigation)
# ==========================================

pg_login = st.Page(view_login, title="Iniciar Sesión", icon="🔒", url_path="login")

def secure_page(func):
    def wrapper():
        if not st.session_state.get('logged_in'):
            st.switch_page(pg_login)
        else:
            func()
    return wrapper

pg_dashboard = st.Page(secure_page(view_dashboard), title="Centro Operativo", icon="🌐", url_path="centro-operativo")
pg_autorizaciones = st.Page(secure_page(view_autorizaciones), title="Autorizaciones", icon="🛡️", url_path="autorizaciones")
pg_novedad = st.Page(secure_page(view_nueva_novedad), title="Nueva Novedad", icon="📝", url_path="nueva-novedad")
pg_cierre = st.Page(secure_page(view_cerrar_novedad), title="Cerrar Novedad", icon="🏁", url_path="cerrar-novedad")
pg_mantenimiento = st.Page(secure_page(view_mantenimientos), title="Mantenimientos", icon="🔧", url_path="mantenimientos")
pg_historial = st.Page(secure_page(view_historial), title="Historial y Edición", icon="🕰️", url_path="historial")
pg_reportes = st.Page(secure_page(view_reportes), title="Informes y Métricas", icon="📊", url_path="informes")
pg_admin = st.Page(secure_page(view_admin), title="Administración", icon="⚙️", url_path="administracion")

todas_las_paginas = [pg_login, pg_dashboard, pg_autorizaciones, pg_novedad, pg_cierre, pg_mantenimiento, pg_historial, pg_reportes, pg_admin]

if not st.session_state.get('logged_in'):
    pg = st.navigation(todas_las_paginas, position="hidden")
    pg.run()
else:
    rol_str = st.session_state['user_info']['rol']
    permisos_usuario = DBManager.fetch_one("SELECT * FROM rol_permisos WHERE LOWER(rol_nombre) = LOWER(%s)", (rol_str,))
    
    if not permisos_usuario:
        if rol_str.lower() == 'administrador':
            permisos_usuario = {'ver_aprobaciones': True, 'ver_apertura': True, 'ver_cierre': True, 'ver_mantenimiento': True, 'ver_edicion': True, 'ver_reportes': True, 'ver_admin': True, 'puede_aprobar': True, 'ver_solo_propios': False, 'exige_aprobacion': False}
        elif rol_str.lower() == 'lider':
            permisos_usuario = {'ver_aprobaciones': True, 'ver_apertura': True, 'ver_cierre': True, 'ver_mantenimiento': True, 'ver_edicion': True, 'ver_reportes': True, 'ver_admin': False, 'puede_aprobar': True, 'ver_solo_propios': False, 'exige_aprobacion': False}
        else:
            permisos_usuario = {'ver_aprobaciones': False, 'ver_apertura': True, 'ver_cierre': True, 'ver_mantenimiento': True, 'ver_edicion': False, 'ver_reportes': False, 'ver_admin': False, 'puede_aprobar': False, 'ver_solo_propios': False, 'exige_aprobacion': True}

    st.session_state.PUEDE_APROBAR = bool(permisos_usuario.get('puede_aprobar', False))
    st.session_state.ES_PUEDE_EDITAR = bool(permisos_usuario.get('ver_edicion', False))
    st.session_state.ES_ADMIN = bool(permisos_usuario.get('ver_admin', False))
    st.session_state.VER_SOLO_PROPIOS = bool(permisos_usuario.get('ver_solo_propios', False))
    st.session_state.EXIGE_APROBACION = bool(permisos_usuario.get('exige_aprobacion', False))

    res_servicios = DBManager.fetch_all("SELECT servicio_id FROM rol_servicios WHERE LOWER(rol_nombre) = LOWER(%s)", (rol_str,))
    st.session_state.SERV_IDS_RESTRINGIDOS = [r['servicio_id'] for r in res_servicios] if res_servicios else []

    st.session_state.analistas, st.session_state.plataformas, st.session_state.tipos, st.session_state.servicios = cargar_catalogos()
    st.session_state.plantillas = cargar_plantillas()
    
    abiertos_db = cargar_comunicados_abiertos()
    st.session_state.inci_abiertos = [c for c in abiertos_db if not c.get('tipo_comunicado_nom') or "mantenimiento" not in str(c.get('tipo_comunicado_nom')).lower()]
    st.session_state.mant_abiertos = [c for c in abiertos_db if c.get('tipo_comunicado_nom') and "mantenimiento" in str(c.get('tipo_comunicado_nom')).lower()]
    st.session_state.config_sis = get_system_config()

    pages_dict = {"General": [pg_dashboard]}
    
    if permisos_usuario.get('ver_aprobaciones'): pages_dict["General"].append(pg_autorizaciones)
        
    ops = []
    if permisos_usuario.get('ver_apertura'): ops.append(pg_novedad)
    if permisos_usuario.get('ver_cierre'): ops.append(pg_cierre)
    if permisos_usuario.get('ver_mantenimiento'): ops.append(pg_mantenimiento)
    if permisos_usuario.get('ver_edicion'): ops.append(pg_historial)
    if ops: pages_dict["Operaciones"] = ops
        
    config_pages = []
    if permisos_usuario.get('ver_reportes'): config_pages.append(pg_reportes)
    if permisos_usuario.get('ver_admin'): config_pages.append(pg_admin)
    if config_pages: pages_dict["Administración & Informes"] = config_pages

    st.sidebar.image("https://res.cloudinary.com/bayehcompany/image/upload/v1778112472/dozewlylntjhfklp2bwj.png", use_container_width=True)
    iniciales = f"{st.session_state['user_info']['nombre'][0].upper()}{st.session_state['user_info']['apellido'][0].upper()}"
    st.sidebar.markdown(f"""
    <div style="background: linear-gradient(135deg, #10004F 0%, #1a0080 100%); padding: 18px; border-radius: 16px; margin-top: 10px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(16,0,79,0.15); color: white;">
        <div style="display: flex; align-items: center; gap: 14px;">
            <div style="width: 42px; height: 42px; background-color: #d51b5d; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: bold; border: 2px solid rgba(255,255,255,0.8); box-shadow: 0 2px 6px rgba(0,0,0,0.2);">
                {iniciales}
            </div>
            <div style="overflow: hidden;">
                <p style="margin:0; font-size:15px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{st.session_state['user_info']['nombre']} {st.session_state['user_info']['apellido']}</p>
                <p style="margin:0; font-size:11px; opacity: 0.85; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">{st.session_state['user_info']['rol']}</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.sidebar.button("Cerrar Sesión 🚪", use_container_width=True):
        registrar_auditoria(st.session_state['user_info']['id'], 'LOGOUT', 'Cierre de sesión')
        st.session_state['logged_in'] = False
        st.session_state['user_info'] = None
        st.query_params.clear()
        st.rerun()

    st.sidebar.markdown("<br>", unsafe_allow_html=True)

    pg = st.navigation(pages_dict, position="sidebar")
    pg.run()
    
    revisar_y_escalar_slas()