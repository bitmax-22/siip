# c:\Users\Administrator\Desktop\SIIP\app\chat\general_routes.py
from flask import render_template, redirect, url_for, session, jsonify, send_from_directory, current_app

from . import chat_bp  # Import the blueprint from app/chat/__init__.py
from flask_login import login_required
from ..models import Conversation # Importar Conversation
from ..extensions import db # Importar db


@chat_bp.route('/')
@login_required
def index():
    return redirect(url_for('chat.chat_route'))


@chat_bp.route('/chat')
@login_required
def chat_route():
    return render_template('chat.html', username=session['user_id'])


@chat_bp.route('/get_history')
@login_required
def get_history():
    conversation_id = session.get('conversation_id')
    if not conversation_id:
        return jsonify({"history": ["Error: Sesión de conversación no encontrada."]})

    conversation = db.session.get(Conversation, conversation_id) # Usar db.session.get
    if not conversation:
        return jsonify({"history": ["Error: No se pudo cargar la conversación."]})

    # Podrías limitar el historial devuelto al frontend si es muy largo,
    # por ejemplo: conversation.get_history()[-20:]
    return jsonify({"history": conversation.get_history()})


@chat_bp.route('/static/resources/<path:filename>')
def serve_resource(filename):
    resources_folder_abs = current_app.config['RESOURCES_FOLDER']
    return send_from_directory(resources_folder_abs, filename)


@chat_bp.route('/static/photos/<path:filename>')
def serve_photo(filename):
    photos_folder_abs = current_app.config['PHOTOS_FOLDER']
    return send_from_directory(photos_folder_abs, filename)