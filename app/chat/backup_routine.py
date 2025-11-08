# c:\Users\Administrator\Desktop\SIIP CON FOTO\backup_routine.py
import os
import shutil
import zipfile
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- Configuración ---
# Directorio donde se encuentra este script
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))

# Directorio raíz del proyecto SIIP que se desea respaldar
PROJECT_TO_BACKUP_DIR = r'C:\Users\Administrator\Desktop\SIIP CON FOTO'

DB_NAME = 'siip_database.db'
DB_PATH = os.path.join(PROJECT_TO_BACKUP_DIR, DB_NAME) # Asume que la DB está en la raíz de PROJECT_TO_BACKUP_DIR

# Carpeta temporal para los respaldos locales, relativa al directorio del script
LOCAL_BACKUP_DIR_BASE = os.path.join(SCRIPT_DIR, 'temp_backups')

# Configuración de Google Drive
# La ruta al archivo de credenciales ahora apunta a C:\KEYS\proyecto-excel-cfhn-ef8feac76292.json
DRIVE_SERVICE_ACCOUNT_FILE = os.path.join('C:\\KEYS', 'proyecto-excel-cfhn-ef8feac76292.json')
# ID de la carpeta de Google Drive para los respaldos
GOOGLE_DRIVE_FOLDER_ID = '1me9w0CtF_YhvFSjIcEh2CEOBv38qGeON'

# Configuración de Correo Electrónico
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587 # o 465 para SSL
SMTP_USER = 'americovargas22@gmail.com' # Correo desde el que se enviará
SMTP_PASSWORD = 'oiqs iugt bald egsk' # Contraseña de aplicación actualizada
EMAIL_TO = 'americovargas22@gmail.com'
EMAIL_SUBJECT_PREFIX = '[SIIP Backup]'

# --- Fin Configuración ---

# Función para ejecutar backup con configuración externa (para APScheduler)
def run_backup_with_config(config):
    """Ejecuta la rutina de backup usando configuración proporcionada."""
    global LOCAL_BACKUP_DIR_BASE, DRIVE_SERVICE_ACCOUNT_FILE, GOOGLE_DRIVE_FOLDER_ID
    global SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_TO
    
    # Actualizar configuración global si se proporciona
    if hasattr(config, 'BACKUP_LOCAL_DIR'):
        LOCAL_BACKUP_DIR_BASE = config.BACKUP_LOCAL_DIR
    if hasattr(config, 'BACKUP_DRIVE_SERVICE_ACCOUNT_FILE'):
        DRIVE_SERVICE_ACCOUNT_FILE = config.BACKUP_DRIVE_SERVICE_ACCOUNT_FILE
    if hasattr(config, 'BACKUP_DRIVE_FOLDER_ID'):
        GOOGLE_DRIVE_FOLDER_ID = config.BACKUP_DRIVE_FOLDER_ID
    if hasattr(config, 'BACKUP_SMTP_SERVER'):
        SMTP_SERVER = config.BACKUP_SMTP_SERVER
    if hasattr(config, 'BACKUP_SMTP_PORT'):
        SMTP_PORT = config.BACKUP_SMTP_PORT
    if hasattr(config, 'BACKUP_SMTP_USER'):
        SMTP_USER = config.BACKUP_SMTP_USER
    if hasattr(config, 'BACKUP_SMTP_PASSWORD'):
        SMTP_PASSWORD = config.BACKUP_SMTP_PASSWORD
    if hasattr(config, 'BACKUP_EMAIL_TO'):
        EMAIL_TO = config.BACKUP_EMAIL_TO
    
    # Ejecutar main
    main()

# Importaciones de Google API (solo si están disponibles)
try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False
    print("ADVERTENCIA: Librerías de Google no encontradas. La subida a Google Drive no funcionará.")
    print("Instálalas con: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")


def create_timestamped_name(base_name, extension):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}.{extension}"

def backup_database(db_path, backup_dir):
    """Copia el archivo de la base de datos a la carpeta de respaldo."""
    if not os.path.exists(db_path):
        print(f"Error: Archivo de base de datos no encontrado en {db_path}")
        return None
    
    db_backup_name = create_timestamped_name(os.path.basename(db_path).replace('.db', ''), 'db')
    db_backup_path = os.path.join(backup_dir, db_backup_name)
    try:
        shutil.copy2(db_path, db_backup_path)
        print(f"Base de datos respaldada en: {db_backup_path}")
        return db_backup_path
    except Exception as e:
        print(f"Error al respaldar la base de datos: {e}")
        return None

def archive_project_files(project_dir, backup_dir):
    """Comprime la carpeta completa del proyecto."""
    project_archive_name = create_timestamped_name('SIIP_Project_Backup', 'zip')
    project_archive_path = os.path.join(backup_dir, project_archive_name)
    
    # Directorios a excluir del archivo ZIP (relativos a project_dir)
    # temp_backups es importante para no incluir respaldos anteriores en el nuevo respaldo.
    # .git si usas control de versiones y no quieres incluir el historial pesado.
    # __pycache__ y otros directorios de caché.
    # venv o cualquier entorno virtual que esté en la raíz del proyecto a respaldar.
    excluded_dirs = {
        os.path.join(project_dir, '.git'),
        os.path.join(project_dir, 'venv') # Asume que 'venv' está en la raíz de project_dir
    }
    # Excluir la carpeta de respaldos temporales que está dentro de la ubicación del script
    # project_dir es PROJECT_TO_BACKUP_DIR (ej: ...\SIIP CON FOTO)
    # SCRIPT_DIR es (ej: ...\SIIP CON FOTO\app\chat)
    # LOCAL_BACKUP_DIR_BASE es (ej: ...\SIIP CON FOTO\app\chat\temp_backups)
    # La ruta relativa de LOCAL_BACKUP_DIR_BASE desde project_dir es 'app/chat/temp_backups'
    excluded_dirs.add(os.path.join(project_dir, 'app', 'chat', 'temp_backups'))
    excluded_files = set() # El archivo de credenciales de Drive ya no está dentro del proyecto a zipear
    try:
        with zipfile.ZipFile(project_archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(project_dir):
                # Excluir directorios
                dirs[:] = [d for d in dirs if os.path.join(root, d) not in excluded_dirs and '__pycache__' not in d]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    if file_path not in excluded_files and not file.endswith('.pyc'):
                        arcname = os.path.relpath(file_path, project_dir)
                        zipf.write(file_path, arcname)
        print(f"Proyecto archivado en: {project_archive_path}")
        return project_archive_path
    except Exception as e:
        print(f"Error al archivar el proyecto: {e}")
        return None

def upload_to_google_drive(file_path, folder_id):
    """Sube un archivo a una carpeta específica en Google Drive."""
    if not GOOGLE_LIBS_AVAILABLE:
        print("Subida a Google Drive omitida (librerías no disponibles).")
        return None
    if not os.path.exists(DRIVE_SERVICE_ACCOUNT_FILE):
        print(f"Error: Archivo de credenciales de Google Drive no encontrado en {DRIVE_SERVICE_ACCOUNT_FILE}")
        return None
    if folder_id == 'TU_FOLDER_ID_DE_GOOGLE_DRIVE':
        print("Error: GOOGLE_DRIVE_FOLDER_ID no configurado. Por favor, edita el script.")
        return None

    try:
        creds = Credentials.from_service_account_file(
            DRIVE_SERVICE_ACCOUNT_FILE,
            scopes=['https://www.googleapis.com/auth/drive.file'] # Scope para subir archivos
        )
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        
        print(f"Subiendo {os.path.basename(file_path)} a Google Drive...")
        request = service.files().create(media_body=media, body=file_metadata, fields='id,name,webViewLink')
        response = None
        file_uploaded = None
        # Bucle para manejar la subida resumible
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Subido {int(status.progress() * 100)}%")
        file_uploaded = response

        print(f"Archivo '{file_uploaded.get('name')}' subido a Google Drive. ID: {file_uploaded.get('id')}")
        print(f"Enlace de visualización: {file_uploaded.get('webViewLink')}")
        return file_uploaded.get('webViewLink') # o file_uploaded.get('id')
    except Exception as e:
        print(f"Error al subir a Google Drive: {e}")
        return None

def send_email_notification(subject, body, files_backed_up_info):
    """Envía una notificación por correo electrónico."""
    if not SMTP_USER or SMTP_USER == 'tu_correo_gmail_para_enviar@gmail.com':
        print("Configuración de correo no completada. Email no enviado.")
        return

    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"{EMAIL_SUBJECT_PREFIX} {subject}"
    
    full_body = body
    if files_backed_up_info:
        full_body += "\n\nArchivos en este respaldo:\n"
        for item in files_backed_up_info:
            full_body += f"- {item['name']}"
            if item.get('drive_link'):
                full_body += f" (Drive: {item['drive_link']})"
            elif item.get('status') == 'Error en Drive':
                 full_body += " (Error al subir a Drive)"
            full_body += "\n"

    msg.attach(MIMEText(full_body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())
        server.quit()
        print(f"Correo de notificación enviado a {EMAIL_TO}")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")

def main():
    print(f"--- Iniciando rutina de respaldo SIIP: {datetime.datetime.now()} ---")
    
    # Crear directorio de respaldo local si no existe
    if not os.path.exists(LOCAL_BACKUP_DIR_BASE):
        os.makedirs(LOCAL_BACKUP_DIR_BASE)
    
    # Crear un subdirectorio con timestamp para este respaldo específico
    current_backup_run_dir = os.path.join(LOCAL_BACKUP_DIR_BASE, datetime.datetime.now().strftime("%Y%m%d_%H%M%S_run"))
    if not os.path.exists(current_backup_run_dir):
        os.makedirs(current_backup_run_dir)

    backed_up_files_info = [] # Para el cuerpo del email
    errors_occurred = False

    # 1. Respaldo de la base de datos
    print("\n--- Paso 1: Respaldo de Base de Datos ---")
    db_backup_file = backup_database(DB_PATH, current_backup_run_dir)
    if db_backup_file:
        drive_link_db = upload_to_google_drive(db_backup_file, GOOGLE_DRIVE_FOLDER_ID)
        backed_up_files_info.append({
            "name": os.path.basename(db_backup_file),
            "path": db_backup_file,
            "drive_link": drive_link_db,
            "status": "OK" if drive_link_db else "Error en Drive"
        })
        if not drive_link_db and GOOGLE_LIBS_AVAILABLE: errors_occurred = True
    else:
        errors_occurred = True
        backed_up_files_info.append({"name": DB_NAME, "status": "Error en respaldo local"})

    # 2. Respaldo de archivos del proyecto
    print("\n--- Paso 2: Respaldo de Archivos del Proyecto ---")
    project_archive_file = archive_project_files(PROJECT_TO_BACKUP_DIR, current_backup_run_dir)
    if project_archive_file:
        drive_link_project = upload_to_google_drive(project_archive_file, GOOGLE_DRIVE_FOLDER_ID)
        backed_up_files_info.append({
            "name": os.path.basename(project_archive_file),
            "path": project_archive_file,
            "drive_link": drive_link_project,
            "status": "OK" if drive_link_project else "Error en Drive"
        })
        if not drive_link_project and GOOGLE_LIBS_AVAILABLE: errors_occurred = True
    else:
        errors_occurred = True
        backed_up_files_info.append({"name": "Archivos del Proyecto", "status": "Error en archivado local"})

    # 3. Enviar notificación por correo
    print("\n--- Paso 3: Notificación por Correo ---")
    email_subject = ""
    email_body = ""
    if errors_occurred:
        email_subject = "Respaldo SIIP CON ERRORES"
        email_body = "La rutina de respaldo del SIIP finalizó con uno o más errores. Por favor, revisa los logs.\n"
        print("ERRORES DETECTADOS DURANTE EL RESPALDO.")
    else:
        email_subject = "Respaldo SIIP Completado Exitosamente"
        email_body = "La rutina de respaldo del SIIP se completó exitosamente.\n"
        print("RESPALDO COMPLETADO EXITOSAMENTE.")
    
    send_email_notification(email_subject, email_body, backed_up_files_info)

    # 4. Limpieza (opcional, podrías querer mantener los locales por un tiempo)
    # print("\n--- Paso 4: Limpieza ---")
    # try:
    #     shutil.rmtree(current_backup_run_dir)
    #     print(f"Directorio de respaldo local temporal eliminado: {current_backup_run_dir}")
    # except Exception as e:
    #     print(f"Error al eliminar el directorio de respaldo local: {e}")
    # Descomenta la limpieza si deseas eliminar los archivos locales después de subirlos.

    print(f"\n--- Rutina de respaldo SIIP finalizada: {datetime.datetime.now()} ---")

if __name__ == '__main__':
    main()
