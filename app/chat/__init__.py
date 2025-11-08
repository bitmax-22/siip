# __init__.py
from flask import Blueprint

# Define el blueprint para el módulo de chat
chat_bp = Blueprint('chat', __name__, template_folder='templates')

# Importa las rutas asociadas a este blueprint para que se registren
from . import general_routes, routes, dashboard_routes, reseña_routes, image_routes
