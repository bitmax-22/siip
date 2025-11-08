from flask import Blueprint

# Define el blueprint para el módulo de RRHH
rrhh_bp = Blueprint('rrhh', __name__, template_folder='templates', url_prefix='/rrhh')

# Importa las rutas asociadas a este blueprint para que se registren
from . import routes

