from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_login import login_user, logout_user, current_user, login_required # Importar de flask_login
from .models import User, Conversation # Importar Conversation
from .extensions import db

# Crear Blueprint para autenticación y gestión de usuarios
bp = Blueprint('auth', __name__)

# --- Decoradores para proteger rutas ---

def admin_required(f):
    """Decorador para rutas que requieren permisos de administrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acceso no autorizado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('chat.chat_route'))
        return f(*args, **kwargs)
    return decorated_function

def permiso_required(permiso_name):
    """Decorador genérico para verificar permisos específicos de módulos"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Debes iniciar sesión para acceder a este módulo.', 'warning')
                return redirect(url_for('auth.login'))
            
            # Verificar si el usuario tiene el permiso específico
            if not getattr(current_user, permiso_name, False):
                flash(f'No tienes permisos para acceder a este módulo.', 'danger')
                return redirect(url_for('chat.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Decoradores específicos para cada módulo
def chat_required(f):
    return permiso_required('permiso_chat')(f)

def dashboard_required(f):
    return permiso_required('permiso_dashboard')(f)

def resena_required(f):
    return permiso_required('permiso_resena')(f)

def usuarios_required(f):
    return permiso_required('permiso_usuarios')(f)

def familiares_required(f):
    return permiso_required('permiso_familiares')(f)

def rrhh_required(f):
    return permiso_required('permiso_rrhh')(f)

def panaderia_required(f):
    return permiso_required('permiso_panaderia')(f)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: # Usar current_user
        # Redirigir a la ruta del chat dentro del blueprint 'chat'
        return redirect(url_for('chat.chat_route'))
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        # Mover la importación aquí para evitar la importación circular
        from .chat.message_logic import initialize_conversation_history
        if user and check_password_hash(user.password_hash, password):
            login_user(user) # Usar login_user de Flask-Login
            session['user_id'] = user.username

            # Crear o recuperar la conversación del usuario
            # Por simplicidad, crearemos una nueva conversación en cada login.
            # Se podría buscar una existente si se desea continuar conversaciones previas.
            db_user = User.query.filter_by(username=username).first()
            if db_user:
                # Crear una nueva conversación para esta sesión de login
                # Usar la función initialize_conversation_history para el saludo personalizado
                initial_history = initialize_conversation_history(db_user) # db_user es el objeto User completo
                new_conversation = Conversation(user_id=db_user.id, history_data=initial_history)
                db.session.add(new_conversation)
                db.session.commit()
                # Guardar el ID de la nueva conversación en la sesión
                session['conversation_id'] = new_conversation.id
                current_app.logger.info(f"[CHAT_INTERACTION] Sucre (Bienvenida para {db_user.username}): {initial_history[0][:200]}{'...' if len(initial_history[0]) > 200 else ''}")
            else: # No debería ocurrir si el login fue exitoso
                flash('Error al encontrar el usuario en la base de datos.', 'danger')
                return redirect(url_for('auth.login'))

            print(f"Usuario '{username}' ha iniciado sesión.")
            return redirect(url_for('chat.chat_route')) # Redirigir a la ruta del chat
        else:
            error = "Usuario o contraseña incorrectos."
            print(f"Intento de login fallido para usuario: {username}")
    return render_template('login.html', error=error)

@bp.route('/logout')
@login_required # Asegurarse de que solo usuarios logueados puedan hacer logout
def logout():
    user_username = current_user.username # Obtener el nombre de usuario antes de desloguear
    logout_user() # Usar logout_user de Flask-Login
    # Limpiar otros datos de contexto que aún residen en la sesión de Flask si es necesario
    # Considerar si estos datos deben ser persistentes o asociados al usuario en la DB
    # session.pop('last_person_context_cedula', None)
    # session.pop('last_person_context_name', None)
    # session.pop('last_name_search_results', None)
    # session.pop('similar_name_suggestions', None)
    # session.pop('awaiting_follow_up_authorization', None)
    # session.pop('last_tribunal_context', None)
    print(f"Usuario '{user_username}' ha cerrado sesión.")
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('auth.login')) # Redirigir a la propia ruta de login

@bp.route('/admin/users', methods=['GET', 'POST'])
@admin_required # Usar el decorador definido en este mismo archivo
def manage_users():
    print("DEBUG: Accediendo a /admin/users")
    if request.method == 'POST': # Esto es para CREAR un nuevo usuario
        username = request.form['username']
        password = request.form['password']
        nombre_completo = request.form.get('nombre_completo') # Obtener nombre_completo
        cargo = request.form.get('cargo')                     # Obtener cargo (opcional)
        is_admin = 'is_admin' in request.form
        
        # Obtener permisos granulares del formulario
        permiso_chat = 'permiso_chat' in request.form
        permiso_dashboard = 'permiso_dashboard' in request.form
        permiso_resena = 'permiso_resena' in request.form
        permiso_usuarios = 'permiso_usuarios' in request.form
        permiso_familiares = 'permiso_familiares' in request.form
        permiso_rrhh = 'permiso_rrhh' in request.form
        permiso_panaderia = 'permiso_panaderia' in request.form

        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            flash(f'El nombre de usuario "{username}" ya existe.', 'warning')
        elif not password:
             flash('La contraseña no puede estar vacía.', 'warning')
        elif not nombre_completo: # nombre_completo es obligatorio
            flash('El campo "Nombre Completo" no puede estar vacío.', 'warning')
        else:
            try:
                hashed_password = generate_password_hash(password)
                new_user = User(
                    username=username,
                    password_hash=hashed_password,
                    nombre_completo=nombre_completo,
                    cargo=cargo,
                    is_admin=is_admin,
                    # Permisos granulares
                    permiso_chat=permiso_chat,
                    permiso_dashboard=permiso_dashboard,
                    permiso_resena=permiso_resena,
                    permiso_usuarios=permiso_usuarios,
                    permiso_familiares=permiso_familiares,
                    permiso_rrhh=permiso_rrhh,
                    permiso_panaderia=permiso_panaderia
                )
                db.session.add(new_user)
                db.session.commit()
                flash(f'Usuario "{username}" creado exitosamente.', 'success')
                return redirect(url_for('auth.manage_users'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error al crear usuario: {e}', 'danger')
    all_users = User.query.all()
    return render_template('admin_users.html', users=all_users)

@bp.route('/admin/user/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user_to_edit = db.session.get(User, user_id) # Forma moderna de obtener por PK
    if not user_to_edit:
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('auth.manage_users'))

    if request.method == 'POST':
        # Proceso de actualización
        new_username = request.form.get('username')
        nombre_completo = request.form.get('nombre_completo')
        cargo = request.form.get('cargo')
        is_admin = 'is_admin' in request.form
        new_password = request.form.get('password')
        
        # Obtener permisos granulares del formulario
        permiso_chat = 'permiso_chat' in request.form
        permiso_dashboard = 'permiso_dashboard' in request.form
        permiso_resena = 'permiso_resena' in request.form
        permiso_usuarios = 'permiso_usuarios' in request.form
        permiso_familiares = 'permiso_familiares' in request.form
        permiso_rrhh = 'permiso_rrhh' in request.form
        permiso_panaderia = 'permiso_panaderia' in request.form

        # Validar que el nuevo username no exista ya (si se cambió)
        if new_username != user_to_edit.username:
            existing_user_with_new_name = User.query.filter_by(username=new_username).first()
            if existing_user_with_new_name:
                flash(f'El nombre de usuario "{new_username}" ya está en uso por otro usuario.', 'warning')
                # Volver a renderizar el formulario de edición con los datos actuales y el error
                return render_template('admin_users.html', users=User.query.all(), user_to_edit=user_to_edit)

        user_to_edit.username = new_username
        user_to_edit.nombre_completo = nombre_completo
        user_to_edit.cargo = cargo if cargo else None
        user_to_edit.is_admin = is_admin
        
        # Actualizar permisos granulares
        user_to_edit.permiso_chat = permiso_chat
        user_to_edit.permiso_dashboard = permiso_dashboard
        user_to_edit.permiso_resena = permiso_resena
        user_to_edit.permiso_usuarios = permiso_usuarios
        user_to_edit.permiso_familiares = permiso_familiares
        user_to_edit.permiso_rrhh = permiso_rrhh
        user_to_edit.permiso_panaderia = permiso_panaderia

        if new_password: # Solo actualizar contraseña si se proporcionó una nueva
            user_to_edit.set_password(new_password)

        db.session.commit()
        flash(f'Usuario "{user_to_edit.username}" actualizado exitosamente.', 'success')
        return redirect(url_for('auth.manage_users'))

    # Método GET: Mostrar el formulario de edición con los datos del usuario
    return render_template('admin_users.html', users=User.query.all(), user_to_edit=user_to_edit)