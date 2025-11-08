# c:\Users\Administrator\Desktop\SIIP CON FOTO\app\chat\message_logic.py
import re
import os
import unicodedata
import pandas as pd
from fuzzywuzzy import fuzz
from flask import current_app, url_for
import time
import traceback
from ..reports import generar_ficha_jpg # Relative import
from ..utils import format_value_for_display, default_serializer # Relative import
import logging # Asegúrate de que logging esté importado

# Configuración del logger para este módulo
logger = logging.getLogger(__name__)


def initialize_conversation_history(user_object):
    # El saludo inicial del bot.
    saludo_personalizado = ""
    if user_object:
        if user_object.cargo and user_object.nombre_completo:
            saludo_personalizado = f"{user_object.cargo} {user_object.nombre_completo}"
        elif user_object.nombre_completo:
            saludo_personalizado = user_object.nombre_completo
        else: # Fallback al username si no hay nombre_completo
            saludo_personalizado = user_object.username
    
    initial_bot_message = f"Sucre: ¡Hola {saludo_personalizado}! Soy Sucre, tu asistente virtual del SIIP. ¿En qué puedo ayudarte hoy? Puedes preguntarme sobre un privado de libertad por su cédula o nombre, o solicitar un reporte."
    return [initial_bot_message]


def _validar_y_normalizar_cedula_capturada(cedula_text):
    """Valida si el texto capturado parece una cédula (tiene al menos 3 dígitos) y la normaliza."""
    if cedula_text and re.search(r'\d{3,}', cedula_text): # Debe tener al menos 3 dígitos
        return cedula_text.replace('-', '').replace(' ', '').upper()
    return None

def _buscar_por_nombre(df, nombre_parts):
    """Busca en el DataFrame por partes del nombre."""
    if not nombre_parts or 'NOMBRE_NORMALIZADO' not in df.columns:
        return pd.DataFrame()

    mask = pd.Series(True, index=df.index)
    for part in nombre_parts:
        mask &= df['NOMBRE_NORMALIZADO'].str.contains(part, na=False)
    return df[mask]

def _parse_user_choice(text, max_options):
    """Parsea la elección del usuario (número o palabra ordinal)."""
    text_lower = text.lower().strip()
    if text_lower.isdigit():
        num = int(text_lower)
        if 1 <= num <= max_options:
            return num - 1 # Retorna índice base 0
    else:
        ordinals = {"primera": 0, "segunda": 1, "tercera": 2, "cuarta": 3, "quinta": 4,
                    "sexta": 5, "séptima": 6, "octava": 7, "novena": 8, "décima": 9} # Ampliar si es necesario
        if text_lower in ordinals and ordinals[text_lower] < max_options:
            return ordinals[text_lower]
    return None

def _normalizar_partes_nombre(texto_nombre_completo):
    """Normaliza y divide un texto de nombre en partes para búsqueda."""
    if not texto_nombre_completo or not isinstance(texto_nombre_completo, str):
        return []
    nombre_parts_crudo = texto_nombre_completo.split()
    nombre_parts_filtrado = [
        unicodedata.normalize('NFKD', part.lower().strip()).encode('ascii', errors='ignore').decode('utf-8')
        # Considerar palabras de al menos 2 caracteres, a menos que sea la única palabra
        for part in nombre_parts_crudo if len(part.strip()) >= 2 or (len(nombre_parts_crudo) == 1 and len(part.strip()) >=1)
    ]
    return nombre_parts_filtrado

def _buscar_nombres_similares(df, nombre_buscado_str_original, umbral=75, max_sugerencias=5):
    if 'NOMBRE_NORMALIZADO' not in df.columns or not nombre_buscado_str_original:
        current_app.logger.debug("Fuzzy: NOMBRE_NORMALIZADO no existe o nombre_buscado_str_original está vacío.")
        return pd.DataFrame()
    
    nombre_buscado_normalizado = " ".join(_normalizar_partes_nombre(nombre_buscado_str_original))
    if not nombre_buscado_normalizado:
        current_app.logger.debug(f"Fuzzy: nombre_buscado_normalizado está vacío para original: {nombre_buscado_str_original}")
        return pd.DataFrame()
    
    current_app.logger.debug(f"Fuzzy: Buscando similitudes para '{nombre_buscado_normalizado}' (original: '{nombre_buscado_str_original}') con umbral {umbral}")

    df_copy = df.copy()
    df_copy['NOMBRE_NORMALIZADO_TEMP_FUZZY'] = df_copy['NOMBRE_NORMALIZADO'].fillna('').astype(str)

    df_copy['similarity_score'] = df_copy['NOMBRE_NORMALIZADO_TEMP_FUZZY'].apply(
        lambda nombre_en_db: fuzz.token_set_ratio(nombre_buscado_normalizado, nombre_en_db) if nombre_en_db else 0
    )
    
    sugerencias_df = df_copy[df_copy['similarity_score'] >= umbral].sort_values(
        by='similarity_score', ascending=False
    ).head(max_sugerencias)
    
    if sugerencias_df.empty:
        top_scores_below_threshold = df_copy.sort_values(by='similarity_score', ascending=False).head(5)
        current_app.logger.debug(f"Fuzzy: No se encontraron sugerencias >= {umbral}. Top 5 scores:")
        for index, row in top_scores_below_threshold.iterrows():
            current_app.logger.debug(f"  Score: {row['similarity_score']}, DB_Normalized: '{row['NOMBRE_NORMALIZADO_TEMP_FUZZY']}', Original_DB_Name: '{row.get('NOMBRES Y APELLIDOS', 'N/A')}'")
            
    current_app.logger.debug(f"Fuzzy: Encontradas {len(sugerencias_df)} sugerencias con umbral >= {umbral}.")
    return sugerencias_df.drop(columns=['similarity_score', 'NOMBRE_NORMALIZADO_TEMP_FUZZY'], errors='ignore')

def _check_photo_exists(cedula, photo_type):
    """
    Verifica si una foto de un tipo específico existe para una cédula.
    """
    base_photos_folder = current_app.config['PHOTOS_FOLDER']
    directory = base_photos_folder
    
    if photo_type == 'frente':
        for ext in ['.jpg', '.jpeg', '.png']:
            if os.path.exists(os.path.join(directory, f"{cedula}{ext}")):
                return True
    elif photo_type == 'perfil_derecho':
        directory = os.path.join(base_photos_folder, 'DERECHA')
        for ext in ['.jpg', '.jpeg', '.png']:
            if os.path.exists(os.path.join(directory, f"{cedula}_DERECHO{ext}")):
                return True
    elif photo_type == 'perfil_izquierdo':
        directory = os.path.join(base_photos_folder, 'IZQUIERDA')
        for ext in ['.jpg', '.jpeg', '.png']:
            if os.path.exists(os.path.join(directory, f"{cedula}_IZQUIERDO{ext}")):
                return True
    return False

def _procesar_solicitud_cedula(cedula_normalizada, datos_siip):
    """
    Procesa una solicitud para una cédula específica.
    Muestra la información del privado en el chat y ofrece la ficha jurídica como alternativa.
    Retorna: (bot_reply_html, accion_detectada, cedula_para_contexto, nombre_para_contexto)
    """
    resultados = pd.DataFrame()
    if 'CEDULA_NORMALIZADA' in datos_siip.columns:
        resultados = datos_siip[datos_siip['CEDULA_NORMALIZADA'] == cedula_normalizada]
    else:
        current_app.logger.warning("Columna 'CEDULA_NORMALIZADA' no encontrada. Realizando normalización on-the-fly de 'CEDULA'.")
        resultados = datos_siip[
            datos_siip['CEDULA'].astype(str).str.replace(r'[\s-]', '', regex=True).str.upper() == cedula_normalizada
        ]

    if resultados.empty:
        return f"No encontré información para la cédula {cedula_normalizada}.", "cedula_no_encontrada", cedula_normalizada, None

    datos_privado_dict = resultados.iloc[0].to_dict()
    nombre_completo = datos_privado_dict.get('NOMBRES Y APELLIDOS', 'N/A')
    cedula_display = datos_privado_dict.get('CEDULA', cedula_normalizada)

    # --- AJUSTE PARA TIEMPO FISICO CON REDENCIONES ---
    tiempo_fisico_original_str = datos_privado_dict.get("TIEMPO FISICO")
    redenciones_computadas_str = datos_privado_dict.get("REDENCIONES COMPUTADAS") # Nombre de la columna de redenciones

    # Función helper para parsear "X AÑOS Y MESES Z DIAS" y determinar si es cero
    def _parse_tiempo_str_to_components(tiempo_str_val):
        if pd.isna(tiempo_str_val) or not isinstance(tiempo_str_val, str) or str(tiempo_str_val).strip() == "":
            return {"anos": 0, "meses": 0, "dias": 0, "is_zero": True}
        
        s = str(tiempo_str_val).upper()
        anos, meses, dias = 0, 0, 0
        
        m_anos = re.search(r"(\d+)\s*(AÑO|AÑOS)", s)
        if m_anos: anos = int(m_anos.group(1))
        
        m_meses = re.search(r"(\d+)\s*(MES|MESES)", s)
        if m_meses: meses = int(m_meses.group(1))
        
        m_dias = re.search(r"(\d+)\s*(DIA|DIAS|DÍA|DÍAS)", s)
        if m_dias: dias = int(m_dias.group(1))
        
        is_zero_val = anos == 0 and meses == 0 and dias == 0
        return {"anos": anos, "meses": meses, "dias": dias, "is_zero": is_zero_val}

    parsed_redenciones = _parse_tiempo_str_to_components(redenciones_computadas_str)

    if parsed_redenciones["is_zero"]:
        # Si no hay redenciones o son cero, "TIEMPO FISICO CON REDENCIONES" debe ser igual a "TIEMPO FISICO"
        current_app.logger.debug(f"Ajuste TF+R para C.I. {cedula_display}: Redenciones ('{redenciones_computadas_str}') son cero. 'TIEMPO FISICO CON REDENCIONES' se iguala a 'TIEMPO FISICO' ('{tiempo_fisico_original_str}'). Original TF+R era '{datos_privado_dict.get('TIEMPO FISICO CON REDENCIONES')}'.")
        datos_privado_dict["TIEMPO FISICO CON REDENCIONES"] = tiempo_fisico_original_str
    # else:
        # Si hay redenciones, se usa el valor que viene del Google Sheet para "TIEMPO FISICO CON REDENCIONES".
        # Si ese valor también es incorrecto, el problema está en cómo se calcula *antes* de llegar al Sheet.
        # current_app.logger.debug(f"Ajuste TF+R para C.I. {cedula_display}: Redenciones ('{redenciones_computadas_str}') NO son cero. Se usa TF+R del Sheet: '{datos_privado_dict.get('TIEMPO FISICO CON REDENCIONES')}'.")
    # --- FIN AJUSTE ---

    # Construir la parte informativa del mensaje. El nombre y la cédula ya se incluyen aquí.
    bot_reply_info_html = f"Esta es la información que encontré para {nombre_completo} (C.I. {cedula_display}):<br><br>"
    
    # Campos que nunca se deben mostrar directamente en esta lista (ya sea porque se manejan diferente o son internos)
    campos_a_omitir_display = ['NOMBRES Y APELLIDOS', 'N_CEDULA_NUMERIC', 'CEDULA_NORMALIZADA', 'NOMBRE_NORMALIZADO', 'FOTO']
    
    # Lista de campos deseados por el usuario y su orden.
    # Asegúrate de que estos nombres coincidan EXACTAMENTE con los nombres de las columnas en tu Google Sheet.
    campos_ordenados_preferidos = [
        'EDAD',
        'CONDICION JURIDICA',
        'FECHA DE INGRESO',
        'UBICACION',
        'ESTABLECIMIENTO PENITENCIARIO',
        'FASE DEL PROCESO',
        'CIRCUITO JUDICIAL',
        'NUMERO DE TRIBUNAL',
        'EXTENSION',
        'NUMERO DE EXPEDIENTE',
        'TIEMPO DE PENA',
        'SEXO',
        'PAIS DE ORIGEN',
        'FECHA DE DETENCION',
        'MOTIVO DE INGRESO',
        'DELITO CON MAYOR GRAVEDAD',
        'CASO CONMOCION PUBLICA', # Si esta columna existe con este nombre exacto
        'TIEMPO FISICO',          # Si esta columna existe con este nombre exacto
        'TIEMPO FISICO CON REDENCIONES'
    ]
    campos_procesados = set()

    for campo_pref in campos_ordenados_preferidos:
        if campo_pref in datos_privado_dict and campo_pref not in campos_a_omitir_display:
            valor = datos_privado_dict[campo_pref]
            if pd.notna(valor) and str(valor).strip() != "": # type: ignore
                valor_formateado = format_value_for_display(valor, column_name=campo_pref) # Pasar nombre de columna
                campo_display_titulo = campo_pref.replace('_', ' ').title()
                bot_reply_info_html += f"<b>{campo_display_titulo}:</b> {valor_formateado}<br>"
                campos_procesados.add(campo_pref)

    # --- Lógica para mostrar fotos ---
    fotos_existentes = []
    photo_types = {
        'frente': 'Frente',
        'perfil_derecho': 'Perfil Derecho',
        'perfil_izquierdo': 'Perfil Izquierdo'
    }

    for photo_type, label in photo_types.items():
        if _check_photo_exists(cedula_normalizada, photo_type):
            url = url_for('chat.pdl_photo', cedula=cedula_normalizada, photo_type=photo_type)
            fotos_existentes.append({'url': url, 'label': label})

    fotos_html = ""
    if fotos_existentes:
        fotos_html += '<h5>Fotografías:</h5><div style="display: flex; justify-content: space-around; flex-wrap: wrap; gap: 10px;">'
        for foto in fotos_existentes:
            fotos_html += f'<div style="text-align: center;"><img src="{foto["url"]}" alt="Foto de {foto["label"]}" style="max-width: 150px; max-height: 150px; border-radius: 5px;"><br><small>{foto["label"]}</small></div>'
        fotos_html += '</div>'

    # Generar la ficha jurídica (si se desea mantener esta funcionalidad) y el enlace de descarga
    enlace_ficha_html = ""
    ficha_generada_con_exito = False
    try:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        jpg_filename = f"ficha_{cedula_normalizada}_{timestamp}.jpg"
        generar_ficha_jpg(datos_privado_dict, cedula_display, jpg_filename)
        download_url = url_for('chat.download_report', filename=jpg_filename, _external=True)
        enlace_ficha_html = f"<br>Si lo deseas, también puedes <a href='{download_url}' target='_blank'>descargar la ficha jurídica completa en formato JPG aquí</a>."
        ficha_generada_con_exito = True
    except Exception as e_ficha:
        current_app.logger.error(f"Error al generar la ficha jurídica JPG para C.I. {cedula_display} (normalizada {cedula_normalizada}): {e_ficha}", exc_info=True)
        enlace_ficha_html = "<br><i>(Hubo un inconveniente al generar la ficha jurídica en formato JPG. Puedes ver la información principal arriba.)</i>"

    bot_reply_final = bot_reply_info_html + "<br>" + fotos_html + enlace_ficha_html
    accion_final = "info_cedula_con_opcion_ficha" if ficha_generada_con_exito else "info_cedula_error_ficha"

    return bot_reply_final, accion_final, cedula_normalizada, nombre_completo
