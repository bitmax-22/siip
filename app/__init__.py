# c:\Users\Equipo z\Desktop\SIIP\app\__init__.py
import os
import time
from flask import Flask, session # Import session here if needed by decorators in blueprints

from werkzeug.security import generate_password_hash
import google.generativeai as genai
import datetime # Importar datetime

# Para tareas programadas
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import logging # Para logs del scheduler
import pandas as pd # <--- AÑADIR ESTA LÍNEA

from config import Config # Importar configuración
from .extensions import db # Importar solo db aquí, gemini_model se maneja en config
from .models import User, PDL, Familiar, Funcionario # Importar el nuevo modelo Funcionario
from .data_loader import cargar_datos_google_sheet # Importar cargador de datos
from .legal_rag_service import LegalRAGService # Importar el nuevo servicio RAG

# Configurar un logger básico si no existe uno para APScheduler
scheduler_logger = logging.getLogger('apscheduler')
if not scheduler_logger.handlers:
    scheduler_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    scheduler_logger.addHandler(handler)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicializar extensiones
    db.init_app(app)

    from flask_migrate import Migrate # Importar Migrate
    migrate = Migrate(app, db) # Inicializar Flask-Migrate

    from flask_login import LoginManager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login' # Redirige a la página de login si no está autenticado

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User # Importar aquí para evitar circular imports
        return User.query.get(int(user_id))

    

    # Configurar Gemini
    try:
        if not app.config['GOOGLE_API_KEY']:
            print("Advertencia: La variable de entorno GOOGLE_API_KEY no está configurada.")
            # No establecer gemini_model aquí, se hará referencia desde extensions
        else:
            genai.configure(api_key=app.config['GOOGLE_API_KEY'])
            # Acceder a la variable global gemini_model desde extensions
            from .extensions import gemini_model as gemini_model_global
            gemini_model_global = genai.GenerativeModel('models/gemini-2.5-pro')
            app.config['GEMINI_MODEL'] = gemini_model_global # Guardar referencia en config si es necesario
            print("-" * 30)
            print("Modelos de Gemini disponibles que soportan 'generateContent':")
            for m in genai.list_models():
              if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
            print("-" * 30)
            print("Gemini configurado exitosamente.")
    except Exception as e:
        print(f"Error configurando Gemini: {e}.")
        # app.config['GEMINI_MODEL'] = None # No es necesario si se accede desde extensions

    # Inicializar el servicio RAG Legal
    # Esto se hará una vez cuando la aplicación se inicie.
    # La ingesta de documentos puede tomar tiempo si hay muchos.
    try:
        with app.app_context(): # Asegurar que estamos en el contexto de la aplicación
            app.legal_rag_service = LegalRAGService(app.config)
            print("Servicio Legal RAG inicializado.")
    except Exception as e:
        print(f"Error inicializando LegalRAGService: {e}")
        app.legal_rag_service = None

    # --- Función para la tarea programada de actualización de datos ---
    def update_siip_data_job():
        # Necesitamos el contexto de la aplicación para acceder a app.config
        # y para que current_app funcione dentro de cargar_datos_google_sheet
        with app.app_context():
            scheduler_logger.info("Iniciando tarea programada: Actualización de datos SIIP desde Google Sheet.")
            try:
                datos_siip_nuevos = cargar_datos_google_sheet()
                if datos_siip_nuevos is not None:
                    app.config['DATOS_SIIP'] = datos_siip_nuevos
                    # Log para verificar las primeras filas y columnas del DataFrame
                    if not datos_siip_nuevos.empty:
                        scheduler_logger.info(f"Primeras filas de datos_siip_nuevos:\n{datos_siip_nuevos.head().to_string()}")
                        scheduler_logger.info(f"Columnas en datos_siip_nuevos: {datos_siip_nuevos.columns.tolist()}")
                    else:
                        scheduler_logger.warning("datos_siip_nuevos está vacío después de cargar desde Google Sheet.")
                    scheduler_logger.info(f"Tarea programada: {len(datos_siip_nuevos)} filas cargadas y actualizadas en app.config.")

                    # --- Sincronizar PDLs con la base de datos ---
                    try:
                        scheduler_logger.info("Iniciando sincronización de PDLs con la base de datos.")
                        pdls_actualizados = 0
                        pdls_creados = 0
                        # Asegúrate de que los nombres de columna 'CEDULA' y 'NOMBRES Y APELLIDOS'
                        # coincidan exactamente con tu Google Sheet.
                        for index, row in datos_siip_nuevos.iterrows():
                            # Log para ver la fila que se está procesando (puede ser muy verboso, usar con cuidado)
                            # scheduler_logger.debug(f"Procesando fila {index}: {row.to_dict()}")

                            cedula_pdl_raw = row.get('CEDULA')
                            nombre_pdl = row.get('NOMBRES Y APELLIDOS')

                            if pd.isna(cedula_pdl_raw) or not nombre_pdl:
                                scheduler_logger.warning(f"Fila {index} sin Cédula o Nombre, omitiendo sincronización de PDL.")
                                continue
                            
                            cedula_pdl = str(cedula_pdl_raw).strip()

                            pdl_existente = PDL.query.filter_by(cedula=cedula_pdl).first()
                            if pdl_existente:
                                if pdl_existente.nombre_completo != nombre_pdl:
                                    pdl_existente.nombre_completo = nombre_pdl
                                # Aquí puedes actualizar otros campos del PDL si los tienes en el modelo
                                db.session.add(pdl_existente)
                                pdls_actualizados +=1
                            else:
                                nuevo_pdl = PDL(cedula=cedula_pdl, nombre_completo=nombre_pdl)
                                db.session.add(nuevo_pdl)
                                pdls_creados +=1
                        db.session.commit()
                        scheduler_logger.info(f"Sincronización de PDLs completada. Creados: {pdls_creados}, Actualizados (potencialmente): {pdls_actualizados}.")
                    except Exception as e_sync:
                        scheduler_logger.error(f"Error durante la sincronización de PDLs: {e_sync}", exc_info=True)
                        db.session.rollback()
                    # --- Fin de Sincronización de PDLs ---

                    # Opcional: Guardar reporte CSV de la actualización programada
                    try:
                        timestamp = time.strftime("%Y%m%d-%H%M%S")
                        report_filename = f"datos_actualizados_auto_{timestamp}.csv"
                        report_filepath = os.path.join(app.config['REPORTS_FOLDER'], report_filename)
                        datos_siip_nuevos.to_csv(report_filepath, index=False, encoding='utf-8-sig')
                        scheduler_logger.info(f"Tarea programada: Reporte de datos actualizados guardado en: {report_filepath}")
                    except Exception as e_csv:
                        scheduler_logger.warning(f"Tarea programada: No se pudo guardar el reporte CSV de datos actualizados: {e_csv}")
                else:
                    scheduler_logger.warning("Tarea programada: cargar_datos_google_sheet devolvió None. Los datos no fueron actualizados.")
            except Exception as e:
                scheduler_logger.error(f"Tarea programada: Error durante la actualización de datos SIIP: {e}", exc_info=True)

    # Carga inicial de datos al iniciar la aplicación
    update_siip_data_job() # Llamamos a la función que ahora tiene el app.app_context() dentro

    # Registrar Blueprints
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from .chat import chat_bp # Import the main chat blueprint from app.chat package
    app.register_blueprint(chat_bp) # Register it

    from .pdl_management import pdl_bp # NUEVO: Importar blueprint de gestión de PDL
    app.register_blueprint(pdl_bp)     # NUEVO: Registrar el blueprint

    # NUEVO: Registrar el blueprint de RRHH
    from .rrhh import rrhh_bp
    app.register_blueprint(rrhh_bp)

    # NUEVO: Registrar el blueprint de Panadería
    from .panaderia import panaderia_bp
    app.register_blueprint(panaderia_bp)

    # La creación del admin se puede mover a un comando CLI o mantener aquí
    # Si se mantiene aquí, asegurarse que db.create_all() se llame antes
    with app.app_context():
        db.create_all() # Asegurarse que las tablas existan
        if not User.query.filter_by(username='admin').first():
            # Considera usar una contraseña más segura y/o gestionarla a través de variables de entorno.
            admin_password_default = '2308' # Contraseña por defecto
            hashed_password = generate_password_hash(admin_password_default)
            new_admin = User(
                username='admin',
                password_hash=hashed_password,
                nombre_completo='Administrador del Sistema', # Campo obligatorio añadido
                cargo='Administrador', # Campo opcional añadido
                is_admin=True
            )
            db.session.add(new_admin)
            db.session.commit()
            print("Usuario 'admin' creado por defecto con nombre_completo y cargo.")
        
        # NUEVO: Añadir funcionario de ejemplo si no existe
        if not Funcionario.query.filter_by(cedula='14391754').first():
            funcionario_ejemplo = Funcionario(
                nombres='YHOVANNY JOSE',
                apellidos='GARCIA GONZALEZ',
                cedula='14391754',
                tipo_personal='Seguridad y Custodia',
                cargo_adscripcion='Jefe de Régimen',
                estatus_actual='Activo'
            )
            db.session.add(funcionario_ejemplo)
            db.session.commit()
            print("Funcionario de ejemplo 'YHOVANNY JOSE GARCIA GONZALEZ' creado.")



    # Context processor para inyectar variables globales a las plantillas
    @app.context_processor
    def inject_now():
        return {'now_year': datetime.datetime.now().year}
        # Si prefieres pasar la función para llamarla como now_year() en la plantilla:
        # return {'now_year': lambda: datetime.datetime.now().year}

    # --- Función para la tarea programada de backup automático ---
    def backup_job():
        """Ejecuta la rutina de backup automático."""
        try:
            with app.app_context():
                scheduler_logger.info("Iniciando tarea programada: Backup automático del sistema SIIP.")
                # Importar aquí para evitar importaciones circulares
                from .chat.backup_routine import run_backup_with_config
                # Ejecutar backup con la configuración de la app
                run_backup_with_config(app.config)
                scheduler_logger.info("Tarea de backup completada exitosamente.")
        except Exception as e:
            scheduler_logger.error(f"Error en la tarea de backup automático: {e}", exc_info=True)

    # Configurar y iniciar APScheduler
    # Solo iniciar el scheduler si no estamos en modo de recarga de Flask (para evitar múltiples schedulers)
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        scheduler = BackgroundScheduler(daemon=True, logger=scheduler_logger)
        scheduler.add_job(func=update_siip_data_job, trigger="interval", hours=1)
        
        # Agregar tarea de backup automático si está habilitada
        if app.config.get('BACKUP_ENABLED', False):
            backup_interval = app.config.get('BACKUP_INTERVAL_HOURS', 24)
            scheduler.add_job(func=backup_job, trigger="interval", hours=backup_interval)
            print(f"APScheduler configurado para backups automáticos cada {backup_interval} horas.")
        else:
            print("Backups automáticos deshabilitados (BACKUP_ENABLED=False).")
        
        scheduler.start()
        # Asegurarse de que el scheduler se apague cuando la app se cierre
        atexit.register(lambda: scheduler.shutdown())
        print("APScheduler configurado para actualizar datos cada hora.")

    return app
