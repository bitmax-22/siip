from flask import Blueprint

panaderia_bp = Blueprint('panaderia', __name__, template_folder='templates', static_folder='static', url_prefix='/panaderia')

from . import routes, forms