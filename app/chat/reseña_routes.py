# c:\Users\Equipo z\Desktop\SIIP\app\chat\reseña_routes.py
from flask import render_template, request, jsonify, session, current_app, flash, send_from_directory, make_response, url_for
import os
import base64
import re
import time

from . import chat_bp
from flask_login import login_required
from ..extensions import db
from ..models import PDL
from ..reports import generar_reporte_pdf_pdl_sin_foto
import pandas as pd

def sanitize_filename(filename):
    """Limpia un nombre de archivo para evitar problemas de ruta."""
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)

@chat_bp.route('/reseña_fotografica')
@login_required
def reseña_fotografica_route():
    return render_template('reseña_fotografica.html', username=session.get('user_id'))

@chat_bp.route('/upload_reseña_photo', methods=['POST'])
@login_required
def upload_reseña_photo_route():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data received"}), 400

    cedula = data.get('cedula')
    photo_type = data.get('photo_type') # 'frontal', 'derecho', 'izquierdo'
    image_data_url = data.get('image_data_url')

    if not all([cedula, photo_type, image_data_url]):
        return jsonify({"success": False, "error": "Missing data (cedula, photo_type, or image_data_url)"}), 400

    try:
        # Limpiar la cédula para usarla en el nombre del archivo
        cedula_filename_safe = sanitize_filename(cedula.upper().replace('-', '').replace(' ', ''))

        # Decodificar la imagen base64
        # Formato esperado: "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."
        header, encoded = image_data_url.split(",", 1)
        image_data = base64.b64decode(encoded)
        
        # Determinar la extensión (asumimos jpeg por simplicidad, podrías extraerla del header)
        extension = "jpg"
        if "image/png" in header:
            extension = "png"

        # Definir la carpeta base de fotos
        photos_folder = current_app.config['PHOTOS_FOLDER']
        
        filename = ""
        save_path_folder = photos_folder

        if photo_type == 'frontal':
            filename = f"{cedula_filename_safe}.{extension}"
        elif photo_type == 'derecho':
            filename = f"{cedula_filename_safe}_DERECHO.{extension}"
            save_path_folder = os.path.join(photos_folder, 'DERECHA')
        elif photo_type == 'izquierdo':
            filename = f"{cedula_filename_safe}_IZQUIERDO.{extension}"
            save_path_folder = os.path.join(photos_folder, 'IZQUIERDA')
        else:
            return jsonify({"success": False, "error": "Invalid photo_type"}), 400

        # Crear subcarpetas si no existen
        if not os.path.exists(save_path_folder):
            os.makedirs(save_path_folder)
            current_app.logger.info(f"Carpeta creada: {save_path_folder}")

        full_save_path = os.path.join(save_path_folder, filename)

        with open(full_save_path, 'wb') as f:
            f.write(image_data)
        
        current_app.logger.info(f"Foto de reseña guardada: {full_save_path}")
        return jsonify({"success": True, "message": f"Foto '{photo_type}' guardada como '{filename}'"}), 200

    except Exception as e:
        current_app.logger.error(f"Error guardando foto de reseña: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Error interno del servidor: {str(e)}"}), 500

# Nueva ruta para servir fotos con cabeceras anti-caché
@chat_bp.route('/serve_reseña_photo_no_cache/<path:filename>')
# @login_required # Descomenta si las fotos deben ser protegidas por login
def serve_reseña_photo_no_cache(filename):
    try:
        directory = current_app.config['PHOTOS_FOLDER']
        # Usar la función sanitize_filename que ya tienes para mayor seguridad
        # Aunque send_from_directory ya hace algo de sanitización, es una capa extra.
        # Sin embargo, si el filename ya incluye subdirectorios como 'DERECHA/archivo.jpg',
        # sanitizarlo aquí podría romper la ruta. Es mejor confiar en send_from_directory
        # para manejar la parte del path y solo sanitizar si fuera un nombre de archivo simple.
        # Por ahora, lo pasaremos tal cual, asumiendo que `filename` viene de `url_for`
        # y ya está correctamente formateado.
        
        response = make_response(send_from_directory(directory, filename))
        
        # Cabeceras para evitar el caché del navegador
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache' # HTTP 1.0
        response.headers['Expires'] = '0' # Proxies
        
        current_app.logger.debug(f"Sirviendo foto (no-cache): {filename} desde {directory}")
        return response
    except FileNotFoundError:
        current_app.logger.warning(f"No se encontró el archivo de foto al servir (no-cache): {filename}")
        return jsonify(error="Archivo no encontrado"), 404
    except Exception as e:
        current_app.logger.error(f"Error sirviendo foto (no-cache) {filename}: {e}", exc_info=True)
        return jsonify(error="Error interno al servir archivo"), 500

def _obtener_pdls_sin_foto_filtrado():
    """Función auxiliar para obtener y filtrar PDLs sin foto. Retorna DataFrame."""
    # Obtener todos los PDLs
    pdls = PDL.query.all()
    
    # Verificar cada PDL para ver si tiene foto frontal
    pdls_sin_foto = []
    photos_folder = current_app.config['PHOTOS_FOLDER']
    
    for pdl in pdls:
        # Buscar foto frontal (CÉDULA.jpg, V-CÉDULA.jpg, E-CÉDULA.jpg)
        cedula_filename_safe = pdl.cedula.upper().replace('-', '').replace(' ', '')
        foto_encontrada = False
        
        for ext in ['.jpg', '.jpeg', '.png']:
            posible_nombres = [
                f"{cedula_filename_safe}{ext}",
                f"V-{cedula_filename_safe}{ext}",
                f"E-{cedula_filename_safe}{ext}"
            ]
            
            for nombre in posible_nombres:
                if os.path.exists(os.path.join(photos_folder, nombre)):
                    foto_encontrada = True
                    break
            
            if foto_encontrada:
                break
        
        if not foto_encontrada:
            pdls_sin_foto.append({
                'CEDULA': pdl.cedula,
                'NOMBRES Y APELLIDOS': pdl.nombre_completo
            })
    
    if not pdls_sin_foto:
        return pd.DataFrame()
    
    # Crear DataFrame con los PDLs sin fotos
    df_pdls_sin_foto = pd.DataFrame(pdls_sin_foto)
    
    # Obtener datos de SIIP para agregar UBICACION y filtrar por ESTATUS
    datos_siip = current_app.config.get('DATOS_SIIP')
    if datos_siip is not None and not datos_siip.empty:
        # Columnas a obtener de datos_siip
        cols_a_obtener = ['CEDULA']
        if 'UBICACION' in datos_siip.columns:
            cols_a_obtener.append('UBICACION')
        if 'ESTATUS' in datos_siip.columns:
            cols_a_obtener.append('ESTATUS')
        
        # Hacer merge CON inner join para solo obtener PDLs que existan en datos_siip
        df_pdls_sin_foto = df_pdls_sin_foto.merge(
            datos_siip[cols_a_obtener], 
            on='CEDULA', 
            how='inner'  # Solo incluir PDLs que estén en datos_siip
        )
        
        # Filtrar solo los PDLs que no sean PASIVO
        if 'ESTATUS' in df_pdls_sin_foto.columns:
            df_pdls_sin_foto = df_pdls_sin_foto[
                df_pdls_sin_foto['ESTATUS'].fillna('').str.upper() != 'PASIVO'
            ]
        
        # Ordenar por UBICACION si existe la columna
        if 'UBICACION' in df_pdls_sin_foto.columns:
            df_pdls_sin_foto = df_pdls_sin_foto.sort_values('UBICACION', na_position='last')
    
    # Agregar columna de conteo (#)
    df_pdls_sin_foto.insert(0, '#', range(1, len(df_pdls_sin_foto) + 1))
    
    # Reordenar columnas: #, CEDULA, NOMBRES Y APELLIDOS, UBICACION (si existe)
    column_order = ['#', 'CEDULA', 'NOMBRES Y APELLIDOS']
    if 'UBICACION' in df_pdls_sin_foto.columns:
        column_order.append('UBICACION')
    df_pdls_sin_foto = df_pdls_sin_foto[column_order]
    
    return df_pdls_sin_foto

@chat_bp.route('/listar_pdls_sin_foto')
@login_required
def listar_pdls_sin_foto():
    """Retorna la lista de PDLs que no tienen fotos en formato JSON."""
    try:
        df_pdls_sin_foto = _obtener_pdls_sin_foto_filtrado()
        
        if df_pdls_sin_foto.empty:
            return jsonify({
                "success": True,
                "count": 0,
                "data": [],
                "message": "Todos los PDLs activos tienen fotografías registradas."
            })
        
        # Convertir DataFrame a lista de diccionarios
        data_list = df_pdls_sin_foto.to_dict('records')
        
        return jsonify({
            "success": True,
            "count": len(data_list),
            "data": data_list,
            "message": f"Se encontraron {len(data_list)} PDLs activos sin fotografías."
        })
            
    except Exception as e:
        current_app.logger.error(f"Error listando PDLs sin foto: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Error al listar PDLs: {str(e)}"
        })

@chat_bp.route('/generar_pdf_pdls_sin_foto')
@login_required
def generar_pdf_pdls_sin_foto():
    """Genera un reporte PDF con los PDLs que no tienen fotos."""
    try:
        df_pdls_sin_foto = _obtener_pdls_sin_foto_filtrado()
        
        if df_pdls_sin_foto.empty:
            return jsonify({
                "success": False,
                "error": "No hay PDLs activos sin fotografías para generar el reporte."
            })
        
        # Generar nombre del archivo con timestamp
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        pdf_filename = f"PDLs_sin_foto_{timestamp}.pdf"
        
        # Generar el PDF
        generar_reporte_pdf_pdl_sin_foto(df_pdls_sin_foto, "Reporte de PDLs sin Fotografia", pdf_filename)
        
        # Retornar URL de descarga
        download_url = url_for('chat.download_report', filename=pdf_filename, _external=False)
        return jsonify({
            "success": True,
            "url": download_url,
            "count": len(df_pdls_sin_foto),
            "message": f"Se generó el reporte con {len(df_pdls_sin_foto)} PDLs activos sin fotografías."
        })
            
    except Exception as e:
        current_app.logger.error(f"Error generando reporte de PDLs sin foto: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Error al generar el reporte: {str(e)}"
        }), 500
