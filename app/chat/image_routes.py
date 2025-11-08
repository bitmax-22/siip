import os
from flask import current_app, send_from_directory, abort
from . import chat_bp
from flask_login import login_required

@chat_bp.route('/pdl-photo/<cedula>/<photo_type>')
@login_required
def pdl_photo(cedula, photo_type):
    """
    Sirve de forma segura las fotos de los privados de libertad.
    photo_type puede ser: 'frente', 'perfil_derecho', 'perfil_izquierdo'.
    """
    base_photos_folder = current_app.config['PHOTOS_FOLDER']
    filename = None
    directory = base_photos_folder

    # Adaptar a la estructura de guardado de reseña_routes.py
    if photo_type == 'frente':
        # La foto de frente no tiene sufijo y está en la carpeta raíz de fotos
        for ext in ['.jpg', '.jpeg', '.png']:
            potential_filename = f"{cedula}{ext}"
            if os.path.exists(os.path.join(directory, potential_filename)):
                filename = potential_filename
                break
    elif photo_type == 'perfil_derecho':
        directory = os.path.join(base_photos_folder, 'DERECHA')
        for ext in ['.jpg', '.jpeg', '.png']:
            potential_filename = f"{cedula}_DERECHO{ext}"
            if os.path.exists(os.path.join(directory, potential_filename)):
                filename = potential_filename
                break
    elif photo_type == 'perfil_izquierdo':
        directory = os.path.join(base_photos_folder, 'IZQUIERDA')
        for ext in ['.jpg', '.jpeg', '.png']:
            potential_filename = f"{cedula}_IZQUIERDO{ext}"
            if os.path.exists(os.path.join(directory, potential_filename)):
                filename = potential_filename
                break
    
    if filename and os.path.exists(os.path.join(directory, filename)):
        return send_from_directory(directory, filename)

    return send_from_directory(os.path.join(current_app.static_folder, 'resources'), 'default_avatar.png')