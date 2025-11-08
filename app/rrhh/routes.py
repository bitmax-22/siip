import os
import base64
from datetime import date
from io import BytesIO
import pandas as pd
from flask import render_template, request, redirect, url_for, flash, current_app, send_file
from werkzeug.utils import secure_filename
from . import rrhh_bp
from ..models import Funcionario, User, Reposo
from ..extensions import db
from ..auth import admin_required
from flask_login import login_required # Importar de flask_login directamente
from .forms import RegistrarFuncionarioForm, ActualizarEstatusForm, CargarReposoForm

@rrhh_bp.route('/')
@login_required
def index():
    """Página principal del módulo de Gestión RRHH."""
    return render_template('rrhh_dashboard.html')

@rrhh_bp.route('/seguridad-custodia')
@login_required
def listar_seguridad_custodia():
    # Estatus que no se mostrarán en la lista principal de activos
    estatus_inactivos = ['Pasivo', 'Egresado', 'Jubilado']
    funcionarios = Funcionario.query.filter(
        Funcionario.tipo_personal == 'Seguridad y Custodia',
        Funcionario.estatus_actual.notin_(estatus_inactivos)
    ).order_by(Funcionario.apellidos, Funcionario.nombres).all()
    form = ActualizarEstatusForm()
    return render_template('listar_funcionarios.html', funcionarios=funcionarios, titulo="Personal de Seguridad y Custodia", form=form)

@rrhh_bp.route('/administrativos')
@login_required
def listar_administrativos():
    estatus_inactivos = ['Pasivo', 'Egresado', 'Jubilado']
    funcionarios = Funcionario.query.filter(
        Funcionario.tipo_personal == 'Administrativo',
        Funcionario.estatus_actual.notin_(estatus_inactivos)
    ).order_by(Funcionario.apellidos, Funcionario.nombres).all()
    form = ActualizarEstatusForm()
    return render_template('listar_funcionarios.html', funcionarios=funcionarios, titulo="Personal Administrativo", form=form)

def _guardar_foto_funcionario(form, cedula, funcionario_existente=None):
    """
    Guarda la foto de perfil de un funcionario y elimina la anterior si existe.
    Maneja tanto la foto subida como la tomada con la cámara.
    Devuelve el nombre del archivo o None si no hay foto nueva.
    """
    foto_filename = None
    fotos_folder = current_app.config['FUNCIONARIOS_FOTOS_FOLDER']
    os.makedirs(fotos_folder, exist_ok=True)
    
    cedula_str = str(cedula)
    random_hex = os.urandom(8).hex()

    # Determinar si hay una nueva foto y de qué fuente
    if form.foto_tomada.data:
        try:
            foto_filename = secure_filename(f"{cedula_str}_{random_hex}.png")
            image_data = base64.b64decode(form.foto_tomada.data.split(',')[1])
            with open(os.path.join(fotos_folder, foto_filename), 'wb') as f:
                f.write(image_data)
        except Exception as e:
            flash(f'Error al procesar la foto tomada: {e}', 'danger')
            return None
    elif form.foto_subida.data:
        try:
            _, f_ext = os.path.splitext(form.foto_subida.data.filename)
            foto_filename = secure_filename(f"{cedula_str}_{random_hex}{f_ext}")
            form.foto_subida.data.save(os.path.join(fotos_folder, foto_filename))
        except Exception as e:
            flash(f'Error al procesar la foto subida: {e}', 'danger')
            return None

    # Si se guardó una nueva foto y es una edición, eliminar la foto anterior
    if foto_filename and funcionario_existente and funcionario_existente.foto_path:
        try:
            os.remove(os.path.join(fotos_folder, funcionario_existente.foto_path))
        except OSError:
            # El archivo no existía, no hay problema.
            pass
            
    return foto_filename

def _calculate_years_of_service(start_date):
    """Calcula los años de servicio completos basados en una fecha de inicio."""
    if not start_date:
        return None
    today = date.today()
    # Resta los años y luego ajusta si aún no se ha cumplido el aniversario este año.
    # Esto da los años completos de servicio.
    return today.year - start_date.year - ((today.month, today.day) < (start_date.month, start_date.day))

def _calculate_age(birth_date):
    """Calcula la edad actual a partir de una fecha de nacimiento."""
    if not birth_date:
        return None
    today = date.today()
    # Misma lógica que para años de servicio
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

@rrhh_bp.route('/registrar', methods=['GET', 'POST'])
@login_required
# @admin_required # Descomentar si solo admins pueden registrar
def registrar_funcionario():
    form = RegistrarFuncionarioForm()
    if form.validate_on_submit():
        # Verificar si la cédula ya existe
        if Funcionario.query.filter_by(cedula=form.cedula.data).first():
            flash('Un funcionario con esta cédula ya está registrado.', 'warning')
            return render_template('registrar_funcionario.html', form=form, titulo="Registrar Nuevo Funcionario")

        # Usar la nueva función auxiliar para guardar la foto
        foto_filename = _guardar_foto_funcionario(form, form.cedula.data)

        # Calcular años de servicio a partir de la fecha de ingreso al MPPSP
        anos_servicio = _calculate_years_of_service(form.fecha_ingreso_mppsp.data)

        nuevo_funcionario = Funcionario(
            # Asignar datos del formulario al modelo
            region=form.region.data, estado_establecimiento=form.estado_establecimiento.data,
            nombre_establecimiento=form.nombre_establecimiento.data, direccion_adscripcion=form.direccion_adscripcion.data,
            fecha_ingreso_admon_publica=form.fecha_ingreso_admon_publica.data, fecha_ingreso_mppsp=form.fecha_ingreso_mppsp.data,
            anos_servicio=anos_servicio, cargo_adscripcion=form.cargo_adscripcion.data,
            cargo_funcional=form.cargo_funcional.data, tipo_personal=form.tipo_personal.data,
            grado_instruccion=form.grado_instruccion.data, profesion=form.profesion.data,
            nombres=form.nombres.data, apellidos=form.apellidos.data, cedula=form.cedula.data,
            sexo=form.sexo.data, fecha_nacimiento=form.fecha_nacimiento.data,
            direccion_habitacion=form.direccion_habitacion.data, estado_residencia=form.estado_residencia.data,
            telefono=form.telefono.data, correo_electronico=form.correo_electronico.data,
            talla_camisa=form.talla_camisa.data, talla_pantalon=form.talla_pantalon.data,
            foto_path=foto_filename, # Guardar el nombre del archivo de la foto
            talla_zapatos=form.talla_zapatos.data, numero_cuenta=form.numero_cuenta.data,
            pago_movil_cedula=form.pago_movil_cedula.data, pago_movil_banco=form.pago_movil_banco.data,
            pago_movil_telefono=form.pago_movil_telefono.data,
            observaciones_estatus=form.observaciones_estatus.data
        )
        db.session.add(nuevo_funcionario)
        db.session.commit()
        flash('Funcionario registrado exitosamente.', 'success')
        # Redirigir a la lista correspondiente según el tipo de personal
        if nuevo_funcionario.tipo_personal == 'Administrativo':
            return redirect(url_for('rrhh.listar_administrativos'))
        else:
            return redirect(url_for('rrhh.listar_seguridad_custodia'))
    
    return render_template('registrar_funcionario.html', form=form, titulo="Registrar Nuevo Funcionario")

@rrhh_bp.route('/funcionario/<int:funcionario_id>')
@login_required
def ver_funcionario(funcionario_id):
    """Muestra la página de detalles de un funcionario específico."""
    funcionario = db.session.get(Funcionario, funcionario_id)
    if not funcionario:
        flash('Funcionario no encontrado.', 'danger')
        return redirect(url_for('rrhh.index'))
    
    # Calcular la edad para mostrarla en la vista
    edad = _calculate_age(funcionario.fecha_nacimiento)
    
    estatus_form = ActualizarEstatusForm()
    reposo_form = CargarReposoForm()

    # Verificar si el funcionario ya tiene un usuario en el sistema
    usuario_existente = User.query.filter_by(username=funcionario.cedula).first()

    # Obtener los documentos de reposo
    reposos = Reposo.query.filter_by(funcionario_id=funcionario.id).order_by(Reposo.fecha_carga.desc()).all()

    return render_template('ver_funcionario.html', funcionario=funcionario, usuario_existente=usuario_existente, edad=edad, form=estatus_form, reposo_form=reposo_form, reposos=reposos)

@rrhh_bp.route('/funcionario/<int:funcionario_id>/editar', methods=['GET', 'POST'])
@login_required
# @admin_required
def editar_funcionario(funcionario_id):
    """Muestra el formulario para editar un funcionario existente."""
    funcionario = db.session.get(Funcionario, funcionario_id)
    if not funcionario:
        flash('Funcionario no encontrado.', 'danger')
        return redirect(url_for('rrhh.index'))

    # Usamos el mismo formulario de registro, pero lo poblamos con los datos existentes
    form = RegistrarFuncionarioForm(obj=funcionario)

    if form.validate_on_submit():
        # Verificar que la nueva cédula no pertenezca a otro funcionario
        cedula_existente = Funcionario.query.filter(Funcionario.cedula == form.cedula.data, Funcionario.id != funcionario_id).first()
        if cedula_existente:
            flash('La cédula ingresada ya pertenece a otro funcionario.', 'warning')
            return render_template('registrar_funcionario.html', form=form, titulo="Editar Funcionario", funcionario_id=funcionario_id)

        # Manejo de la foto
        nueva_foto_filename = _guardar_foto_funcionario(form, form.cedula.data, funcionario_existente=funcionario)
        if nueva_foto_filename:
            funcionario.foto_path = nueva_foto_filename

        # Actualizar los datos del objeto funcionario con los datos del formulario
        form.populate_obj(funcionario)
        
        # Recalcular y establecer los años de servicio al editar
        funcionario.anos_servicio = _calculate_years_of_service(form.fecha_ingreso_mppsp.data)
        
        try:
            db.session.commit()
            flash('Datos del funcionario actualizados exitosamente.', 'success')
            return redirect(url_for('rrhh.ver_funcionario', funcionario_id=funcionario.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el funcionario: {e}', 'danger')

    # Para el método GET, mostrar el formulario con los datos actuales
    # El título se cambia para reflejar que es una edición
    return render_template('registrar_funcionario.html', form=form, titulo="Editar Funcionario", funcionario_id=funcionario_id)

@rrhh_bp.route('/cargar-excel', methods=['GET', 'POST'])
@login_required
@admin_required
def cargar_excel():
    if request.method == 'POST':
        if 'excel_file' not in request.files:
            flash('No se encontró el archivo en la solicitud.', 'danger')
            return redirect(request.url)
        
        file = request.files['excel_file']
        
        if file.filename == '':
            flash('No se seleccionó ningún archivo.', 'warning')
            return redirect(request.url)
        
        if file and file.filename.endswith('.xlsx'):
            try:
                # Leer el excel, asegurando que las cédulas y teléfonos se traten como texto
                df = pd.read_excel(file, dtype={'cedula': str, 'telefono': str, 'numero_cuenta': str, 'pago_movil_cedula': str, 'pago_movil_telefono': str, 'pago_movil_banco': str})

                # Limpiar espacios en blanco de los nombres de las columnas
                df.columns = df.columns.str.strip()

                # Convertir columnas de fecha, manejando errores y el formato DD/MM/AAAA
                date_columns = ['fecha_nacimiento', 'fecha_ingreso_admon_publica', 'fecha_ingreso_mppsp']
                for col in date_columns:
                    if col in df.columns:
                        # 'dayfirst=True' es crucial para el formato DD/MM/AAAA. 'coerce' convierte errores en NaT (Not a Time).
                        # .dt.date convierte a objetos date de Python, que es lo que espera la BD.
                        df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True).dt.date
                
                registros_creados = 0
                registros_actualizados = 0
                
                for index, row in df.iterrows():
                    cedula = row.get('cedula')
                    if not cedula or pd.isna(cedula):
                        continue # Omitir filas sin cédula
                    
                    funcionario = Funcionario.query.filter_by(cedula=str(cedula).strip()).first()
                    
                    if not funcionario:
                        funcionario = Funcionario(cedula=str(cedula).strip())
                        db.session.add(funcionario)
                        registros_creados += 1
                    else:
                        registros_actualizados += 1
                        
                    # Actualizar/asignar datos dinámicamente
                    for col_name in df.columns:
                        if hasattr(funcionario, col_name):
                            value = row[col_name]
                            # No asignar valores nulos de pandas (NaT para fechas, NaN para números).
                            # pd.isna maneja ambos casos.
                            if not pd.isna(value):
                                # Si el valor es texto, limpiar espacios en blanco
                                if isinstance(value, str):
                                    value = value.strip()
                                
                                # Normalización específica para el campo 'tipo_personal' para asegurar la consistencia
                                if col_name == 'tipo_personal' and isinstance(value, str):
                                    tipo_lower = value.lower()
                                    if 'seguridad' in tipo_lower:
                                        value = 'Seguridad y Custodia'
                                    elif 'administrativo' in tipo_lower:
                                        value = 'Administrativo'

                                setattr(funcionario, col_name, value)
                    
                    # Calcular años de servicio
                    if funcionario.fecha_ingreso_mppsp:
                        funcionario.anos_servicio = _calculate_years_of_service(funcionario.fecha_ingreso_mppsp)

                db.session.commit()
                flash(f'Carga completada: {registros_creados} funcionarios creados, {registros_actualizados} actualizados.', 'success')
                return redirect(url_for('rrhh.index'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Ocurrió un error al procesar el archivo: {e}', 'danger')
                return redirect(request.url)
        else:
            flash('Formato de archivo no válido. Por favor, suba un archivo .xlsx', 'danger')
            return redirect(request.url)
            
    return render_template('cargar_excel.html')

@rrhh_bp.route('/descargar-plantilla')
@login_required
def descargar_plantilla():
    try:
        columnas = [
            'cedula', 'nombres', 'apellidos', 'sexo', 'fecha_nacimiento', 'telefono', 'correo_electronico',
            'direccion_habitacion', 'estado_residencia', 'region', 'estado_establecimiento', 'nombre_establecimiento',
            'direccion_adscripcion', 'fecha_ingreso_admon_publica', 'fecha_ingreso_mppsp', 'cargo_adscripcion',
            'cargo_funcional', 'tipo_personal', 'grado_instruccion', 'profesion', 'talla_camisa', 'talla_pantalon',
            'talla_zapatos', 'numero_cuenta', 'pago_movil_banco', 'pago_movil_cedula', 'pago_movil_telefono',
            'observaciones_estatus'
        ]
        df_plantilla = pd.DataFrame(columns=columnas)
        
        output = BytesIO()
        # Usar XlsxWriter como motor para aplicar formatos
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_plantilla.to_excel(writer, index=False, sheet_name='Plantilla Funcionarios')

            # Obtener los objetos de workbook y worksheet
            workbook  = writer.book
            worksheet = writer.sheets['Plantilla Funcionarios']

            # Definir formatos de celda
            text_format = workbook.add_format({'num_format': '@'})
            date_format = workbook.add_format({'num_format': 'dd/mm/yyyy', 'align': 'left'})
            
            # Columnas que deben tener formato de fecha
            date_columns = ['fecha_nacimiento', 'fecha_ingreso_admon_publica', 'fecha_ingreso_mppsp']

            # Aplicar formatos a las columnas
            for i, col_name in enumerate(columnas):
                if col_name in date_columns:
                    worksheet.set_column(i, i, 18, date_format)
                else:
                    worksheet.set_column(i, i, 25, text_format) # Ancho de 25 para las columnas de texto

        output.seek(0)
        
        return send_file(output, download_name='plantilla_carga_funcionarios.xlsx', as_attachment=True)
    except Exception as e:
        flash(f"Error al generar la plantilla: {e}", "danger")
        return redirect(url_for('rrhh.cargar_excel'))

@rrhh_bp.route('/funcionario/<int:funcionario_id>/actualizar-estatus', methods=['POST'])
@login_required
@admin_required
def actualizar_estatus(funcionario_id):
    """Actualiza el estatus de un funcionario."""
    funcionario = db.session.get(Funcionario, funcionario_id)
    if not funcionario:
        flash('Funcionario no encontrado.', 'danger')
        return redirect(url_for('rrhh.index'))
    
    form = ActualizarEstatusForm()
    if form.validate_on_submit():
        funcionario.estatus_actual = form.estatus_actual.data
        funcionario.observaciones_estatus = form.observaciones_estatus.data
        try:
            db.session.commit()
            flash('Estatus del funcionario actualizado exitosamente.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el estatus: {e}', 'danger')
    else:
        # Si la validación falla, mostrar los errores.
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error en el campo '{getattr(form, field).label.text}': {error}", 'danger')

    return redirect(request.referrer or url_for('rrhh.ver_funcionario', funcionario_id=funcionario_id))

@rrhh_bp.route('/funcionario/<int:funcionario_id>/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar_funcionario(funcionario_id):
    """Elimina un funcionario y sus datos asociados."""
    funcionario = db.session.get(Funcionario, funcionario_id)
    if not funcionario:
        flash('Funcionario no encontrado.', 'danger')
        return redirect(url_for('rrhh.index'))

    try:
        # Eliminar foto de perfil si existe
        if funcionario.foto_path:
            foto_path = os.path.join(current_app.config['FUNCIONARIOS_FOTOS_FOLDER'], funcionario.foto_path)
            if os.path.exists(foto_path):
                os.remove(foto_path)

        db.session.delete(funcionario)
        db.session.commit()
        flash('Funcionario eliminado exitosamente.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el funcionario: {e}', 'danger')
    
    return redirect(url_for('rrhh.index'))

@rrhh_bp.route('/funcionario/<int:funcionario_id>/cargar-reposo', methods=['POST'])
@login_required
@admin_required
def cargar_reposo(funcionario_id):
    """Carga un nuevo documento de reposo para un funcionario."""
    funcionario = db.session.get(Funcionario, funcionario_id)
    if not funcionario:
        flash('Funcionario no encontrado.', 'danger')
        return redirect(url_for('rrhh.index'))

    form = CargarReposoForm()
    if form.validate_on_submit():
        file = form.reposo_file.data
        cedula_str = str(funcionario.cedula)
        random_hex = os.urandom(8).hex()
        _, f_ext = os.path.splitext(file.filename)
        filename = secure_filename(f"reposo_{cedula_str}_{random_hex}{f_ext}")
        
        reposos_folder = current_app.config['REPOSOS_FOLDER']
        os.makedirs(reposos_folder, exist_ok=True)
        file.save(os.path.join(reposos_folder, filename))

        nuevo_reposo = Reposo(
            file_path=filename,
            descripcion=form.descripcion.data,
            funcionario_id=funcionario.id
        )
        db.session.add(nuevo_reposo)
        db.session.commit()
        flash('Documento de reposo cargado exitosamente.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error al cargar el documento: {error}", 'danger')

    return redirect(url_for('rrhh.ver_funcionario', funcionario_id=funcionario_id))

@rrhh_bp.route('/reposo/<int:reposo_id>/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar_reposo(reposo_id):
    """Elimina un documento de reposo."""
    reposo = db.session.get(Reposo, reposo_id)
    if reposo:
        funcionario_id = reposo.funcionario_id
        file_path = os.path.join(current_app.config['REPOSOS_FOLDER'], reposo.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(reposo)
        db.session.commit()
        flash('Documento de reposo eliminado.', 'success')
        return redirect(url_for('rrhh.ver_funcionario', funcionario_id=funcionario_id))
    
    flash('Documento no encontrado.', 'danger')
    return redirect(url_for('rrhh.index'))
