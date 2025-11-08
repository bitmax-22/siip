# c:\Users\Administrator\Desktop\SIIP CON FOTO\app\pdl_management.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from .models import PDL, Familiar
from .extensions import db
from .auth import admin_required
from flask_login import login_required # Importar de flask_login directamente
import datetime

pdl_bp = Blueprint('pdl_management', __name__, url_prefix='/pdl_admin')

# --- Rutas para gestión de PDL y Familiares ---

@pdl_bp.route('/')
@login_required # O @admin_required si solo admins pueden ver la lista de PDL
def list_pdls():
    """Muestra una lista paginada de PDLs con opción de búsqueda."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()

    query = PDL.query
    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(
            (PDL.nombre_completo.ilike(search_term)) |
            (PDL.cedula.ilike(search_term))
        )
    
    pdls = query.order_by(PDL.nombre_completo).paginate(page=page, per_page=15, error_out=False)
    return render_template('pdl_management/list_pdls.html', pdls=pdls, search_query=search_query)

@pdl_bp.route('/<int:pdl_id>/familiares', methods=['GET'])
@login_required # O @admin_required
def manage_familiares(pdl_id):
    """Muestra y permite gestionar los familiares de un PDL específico."""
    pdl = db.session.get(PDL, pdl_id)
    if not pdl:
        flash('PDL no encontrado.', 'danger')
        return redirect(url_for('pdl_management.list_pdls'))
    
    return render_template('pdl_management/manage_familiares.html', pdl=pdl)

@pdl_bp.route('/<int:pdl_id>/familiares/agregar', methods=['GET', 'POST'])
@admin_required # Asumimos que solo administradores pueden agregar familiares
def agregar_familiar(pdl_id):
    pdl = db.session.get(PDL, pdl_id)
    if not pdl:
        flash('PDL no encontrado.', 'danger')
        return redirect(url_for('pdl_management.list_pdls'))

    if pdl.familiares.count() >= 5:
        flash('Este PDL ya tiene el máximo de 5 familiares registrados.', 'warning')
        return redirect(url_for('pdl_management.manage_familiares', pdl_id=pdl_id))

    if request.method == 'POST':
        nombre_completo = request.form.get('nombre_completo')
        cedula_familiar = request.form.get('cedula_familiar')
        parentesco = request.form.get('parentesco')
        telefono = request.form.get('telefono')
        direccion = request.form.get('direccion')
        ultima_visita_str = request.form.get('ultima_visita_fecha')

        if not nombre_completo or not parentesco:
            flash('Nombre completo y parentesco son campos obligatorios.', 'warning')
        else:
            ultima_visita_obj = None
            if ultima_visita_str:
                try:
                    ultima_visita_obj = datetime.datetime.strptime(ultima_visita_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de fecha de última visita inválido. Use YYYY-MM-DD.', 'warning')
                    return render_template('pdl_management/agregar_editar_familiar.html',
                                           pdl=pdl, familiar=None, form_data=request.form,
                                           action_url=url_for('pdl_management.agregar_familiar', pdl_id=pdl_id))
            
            nuevo_familiar = Familiar(
                pdl_id=pdl.id, nombre_completo=nombre_completo,
                cedula_familiar=cedula_familiar if cedula_familiar else None,
                parentesco=parentesco, telefono=telefono if telefono else None,
                direccion=direccion if direccion else None, ultima_visita_fecha=ultima_visita_obj
            )
            db.session.add(nuevo_familiar)
            try:
                db.session.commit()
                flash('Familiar agregado exitosamente.', 'success')
                return redirect(url_for('pdl_management.manage_familiares', pdl_id=pdl_id))
            except Exception as e:
                db.session.rollback()
                flash(f'Error al agregar familiar: {str(e)}', 'danger')
                current_app.logger.error(f"Error agregando familiar para PDL {pdl_id}: {e}")
    
    return render_template('pdl_management/agregar_editar_familiar.html', pdl=pdl, familiar=None, action_url=url_for('pdl_management.agregar_familiar', pdl_id=pdl_id))

@pdl_bp.route('/familiar/<int:familiar_id>/editar', methods=['GET', 'POST'])
@admin_required
def editar_familiar(familiar_id):
    familiar = db.session.get(Familiar, familiar_id)
    if not familiar:
        flash('Familiar no encontrado.', 'danger')
        return redirect(url_for('pdl_management.list_pdls')) 
    
    pdl = familiar.pdl_asociado

    if request.method == 'POST':
        familiar.nombre_completo = request.form.get('nombre_completo')
        familiar.cedula_familiar = request.form.get('cedula_familiar')
        familiar.parentesco = request.form.get('parentesco')
        familiar.telefono = request.form.get('telefono')
        familiar.direccion = request.form.get('direccion')
        ultima_visita_str = request.form.get('ultima_visita_fecha')

        if not familiar.nombre_completo or not familiar.parentesco:
            flash('Nombre completo y parentesco son campos obligatorios.', 'warning')
        else:
            if ultima_visita_str:
                try:
                    familiar.ultima_visita_fecha = datetime.datetime.strptime(ultima_visita_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de fecha de última visita inválido. Use YYYY-MM-DD.', 'warning')
                    return render_template('pdl_management/agregar_editar_familiar.html',
                                           pdl=pdl, familiar=familiar, form_data=request.form,
                                           action_url=url_for('pdl_management.editar_familiar', familiar_id=familiar_id))
            else:
                familiar.ultima_visita_fecha = None

            db.session.add(familiar)
            try:
                db.session.commit()
                flash('Familiar actualizado exitosamente.', 'success')
                return redirect(url_for('pdl_management.manage_familiares', pdl_id=pdl.id))
            except Exception as e:
                db.session.rollback()
                flash(f'Error al actualizar familiar: {str(e)}', 'danger')
                current_app.logger.error(f"Error editando familiar {familiar_id}: {e}")

    form_data = {
        'nombre_completo': familiar.nombre_completo, 'cedula_familiar': familiar.cedula_familiar,
        'parentesco': familiar.parentesco, 'telefono': familiar.telefono, 'direccion': familiar.direccion,
        'ultima_visita_fecha': familiar.ultima_visita_fecha.strftime('%Y-%m-%d') if familiar.ultima_visita_fecha else ''
    }
    return render_template('pdl_management/agregar_editar_familiar.html', pdl=pdl, familiar=familiar, form_data=form_data, action_url=url_for('pdl_management.editar_familiar', familiar_id=familiar_id))

@pdl_bp.route('/familiar/<int:familiar_id>/eliminar', methods=['POST'])
@admin_required
def eliminar_familiar(familiar_id):
    familiar = db.session.get(Familiar, familiar_id)
    if familiar:
        pdl_id = familiar.pdl_id
        db.session.delete(familiar)
        db.session.commit()
        flash('Familiar eliminado exitosamente.', 'success')
        return redirect(url_for('pdl_management.manage_familiares', pdl_id=pdl_id))
    else:
        flash('Familiar no encontrado.', 'danger')
        return redirect(url_for('pdl_management.list_pdls'))