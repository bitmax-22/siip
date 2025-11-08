# c:\Users\Administrator\Desktop\SIIP CON FOTO\config.py
import os
from dotenv import load_dotenv

load_dotenv() # Cargar variables de .env

# Obtener la ruta base del proyecto (la carpeta SIIP)
basedir = os.path.abspath(os.path.dirname(__file__))
app_dir = os.path.join(basedir, 'app') # Ruta a la carpeta 'app'

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tu_clave_secreta_aqui_super_segura_y_aleatoria_12345' # ¡Mejor si está en .env!
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'siip_database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SEND_FILE_MAX_AGE_DEFAULT = 0
    TEMPLATES_AUTO_RELOAD = True

    # Rutas a carpetas
    REPORTS_FOLDER = os.path.join(basedir, 'reports') # Fuera de 'app'
    RESOURCES_FOLDER = os.path.join(app_dir, 'resources')
    PHOTOS_FOLDER = os.path.join(app_dir, 'photos') # For inmates
    FUNCIONARIOS_FOTOS_FOLDER = os.path.join(app_dir, 'static', 'fotos_funcionarios') # For officers
    REPOSOS_FOLDER = os.path.join(app_dir, 'static', 'reposos_funcionarios') # Para documentos de reposo
    # Ruta actualizada para los documentos legales
    LEGAL_DOCS_FOLDER = r'C:\Users\Administrator\Desktop\SIIP CON FOTO\documentos_legales'

    # Configuración Google / Gemini
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    SERVICE_ACCOUNT_FILE = os.environ.get('SERVICE_ACCOUNT_FILE') or os.path.join(basedir, 'credentials.json') # Ajusta si el nombre es diferente
    SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
    SHEET_RANGE = os.environ.get('SHEET_RANGE')
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

    # SQLAlchemy engine options for SQLite timeout
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'timeout': 30}  # Wait 30 seconds if DB is locked
    }

    # Configuración de Backup Automático
    BACKUP_ENABLED = True  # Habilitar o deshabilitar backups automáticos
    BACKUP_INTERVAL_HOURS = 24  # Frecuencia de backups (en horas)
    BACKUP_LOCAL_DIR = os.path.join(app_dir, 'chat', 'temp_backups')
    BACKUP_DRIVE_SERVICE_ACCOUNT_FILE = os.path.join('C:\\KEYS', 'proyecto-excel-cfhn-ef8feac76292.json')
    BACKUP_DRIVE_FOLDER_ID = '1me9w0CtF_YhvFSjIcEh2CEOBv38qGeON'
    
    # Configuración de Email para Notificaciones de Backup
    BACKUP_SMTP_SERVER = 'smtp.gmail.com'
    BACKUP_SMTP_PORT = 587
    BACKUP_SMTP_USER = 'americovargas22@gmail.com'
    
    # Configuración de Impresión Térmica para Pedidos
    IMPRESORA_HABILITADA = os.environ.get('IMPRESORA_HABILITADA', 'True').lower() == 'true'
    IMPRESORA_IP = os.environ.get('IMPRESORA_IP', '192.168.88.128')
    IMPRESORA_PUERTO = int(os.environ.get('IMPRESORA_PUERTO', '9100'))
    IMPRESORA_ANCHO_MM = int(os.environ.get('IMPRESORA_ANCHO_MM', '80'))
    BACKUP_SMTP_PASSWORD = 'oiqs iugt bald egsk'
    BACKUP_EMAIL_TO = 'americovargas22@gmail.com'