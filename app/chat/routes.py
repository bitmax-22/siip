# c:\Users\Administrator\Desktop\SIIP\app\chat\routes.py
from flask import redirect, request, url_for, session, flash, jsonify, send_from_directory, current_app
import pandas as pd
import os
import time
import re
import json
import traceback
from datetime import date, datetime, timedelta # Asegurarse que datetime y timedelta completo esté importado
import pytz # Para manejar zonas horarias
from dateutil import parser as date_parser # Para parsear fechas de forma flexible

from . import chat_bp # Import the blueprint from app/chat/__init__.py
from flask_login import login_required
from ..models import Conversation # Importar el modelo Conversation
from ..extensions import db # Importar db para las operaciones de base de datos
from sqlalchemy.orm.attributes import flag_modified # Para marcar el JSON como modificado
from ..reports import generar_reporte_pdf # Adjusted relative import
# Importar User para obtener el objeto completo
from ..models import User
# Import logic functions from message_logic.py
from .message_logic import (
    _validar_y_normalizar_cedula_capturada,
    _buscar_por_nombre,
    _parse_user_choice,
    _normalizar_partes_nombre,
    _buscar_nombres_similares,
    _procesar_solicitud_cedula,
    initialize_conversation_history # Importar la función de inicialización
)
from .report_processing import process_report_request, _parsear_tiempo_pena_a_anos
from ..utils import format_value_for_display # Importar para usar en preguntas de seguimiento

# --- Función refactorizada para contar libertades ---
def _contar_libertades_en_fecha(fecha_obj, df_datos_siip):
    """Cuenta las libertades en una fecha específica usando el DataFrame proporcionado."""
    if 'FECHA CAMBIO ESTATUS' in df_datos_siip.columns and \
       'ESTATUS' in df_datos_siip.columns and \
       pd.api.types.is_datetime64_any_dtype(df_datos_siip['FECHA CAMBIO ESTATUS']):
        
        df_temp = df_datos_siip.copy()
        # Asegurarse que la columna de fecha en el df sea solo date para comparar con fecha_obj que es date
        df_temp['FECHA_CAMBIO_DIA'] = pd.to_datetime(df_temp['FECHA CAMBIO ESTATUS'], errors='coerce').dt.date
        
        condicion_fecha = (df_temp['FECHA_CAMBIO_DIA'] == fecha_obj)
        condicion_estatus_pasivo = (df_temp['ESTATUS'].fillna('').str.upper() == 'PASIVO')
        
        libertades_en_fecha = df_temp[condicion_fecha & condicion_estatus_pasivo].shape[0]
        return libertades_en_fecha, None # (conteo, mensaje_error)
    else:
        error_msg = "Faltan datos necesarios (ESTATUS o FECHA CAMBIO ESTATUS) o no están en el formato correcto."
        current_app.logger.warning(f"Error en _contar_libertades_en_fecha: {error_msg}")
        return 0, error_msg


@chat_bp.route('/send_message', methods=['POST'])
@login_required
def send_message(): # noqa: C901
    data = request.get_json()
    user_message = data.get('message')

    if not user_message:
        return jsonify({"error": "Mensaje vacío"}), 400
    current_app.logger.info(f"[CHAT_INTERACTION] Usuario ({session.get('user_id', 'Desconocido')}): {user_message}")

    conversation_id = session.get('conversation_id')
    if not conversation_id:
        current_app.logger.error("No se encontró conversation_id en la sesión.")
        return jsonify({"error": "Sesión de conversación no encontrada. Por favor, inicia sesión de nuevo."}), 401

    conversation = db.session.get(Conversation, conversation_id) # Usar db.session.get para SQLAlchemy 2.0+
    if not conversation:
        current_app.logger.error(f"No se encontró la conversación con ID {conversation_id} en la BD.")
        # Podríamos intentar recrearla o redirigir al login
        session.pop('conversation_id', None)
        return jsonify({"error": "Error interno al cargar la conversación. Intenta iniciar sesión de nuevo."}), 500
    
    bot_reply = ""
    current_conversation_history = conversation.get_history() # Obtener historial de la BD
    accion_detectada = "ninguna"
    user_message_lower = user_message.lower()
    contexto_para_gemini = "" # Inicializar aquí

    user_message_lower_stripped = user_message.strip().lower()
    common_greetings = ['hola', 'hola!', 'buenas', 'buenos dias', 'buenas tardes', 'buenas noches', 'hey', 'hi', 'saludos']
    
    # Verifica si es el primer mensaje que el usuario envía en esta sesión
    # (considerando el historial de la BD)
    is_first_interaction_in_session = len(current_conversation_history) <= 1 # El primer mensaje es el de bienvenida del bot

    if is_first_interaction_in_session and user_message_lower_stripped in common_greetings:
        # --- MENSAJE DE SALUDO INICIAL PERSONALIZADO ---
        # Reemplaza el texto de abajo con el nuevo saludo que deseas.
        # Puedes usar HTML básico para formatear, como <ul>, <li>, <b>, <br>.
        bot_reply = (
            "¡Hola! Soy Sucre, tu asistente inteligente para el SIIP. 🤖<br><br>"
            "Estoy aquí para ayudarte con:" \
            "Generar reportes, como listado de PDL ordenados por delito,ubiacion, entre otros" \
            "Puedes escribir directamente la cedula de un PDL y puedo darte un resumen y generar su ficha juridica" \
            "Puedes pedirme cualquier informacion relacionada a los PDL en Centro de Formacion y intentare responder" \
            "" \

        )
        accion_detectada = "initial_greeting_handled"
    elif (not is_first_interaction_in_session) and user_message_lower_stripped in common_greetings:
        # Saludo para interacciones subsecuentes si el usuario vuelve a saludar
        bot_reply = "¡Hola de nuevo! ¿En qué más te puedo ayudar?"
        accion_detectada = "subsequent_greeting_handled"
    else:
        # Si no es un saludo especial, o es el primer mensaje pero no un saludo común,
        # se procede con la lógica principal.
        # La lógica MAX_HISTORY para el almacenamiento ya no es necesaria aquí.
        pass

    if accion_detectada in ["initial_greeting_handled", "subsequent_greeting_handled"]:
        pass # El saludo ya fue manejado, se salta la lógica principal.
    # Se eliminaron los manejadores específicos para "ayuda", fecha/hora y nombre del bot.
    # Estas preguntas ahora serán manejadas por el fallback a Gemini.

    if not bot_reply: # Si no es un saludo manejado, proceder con la lógica principal
        try:
            datos_siip = current_app.config.get('DATOS_SIIP')
            gemini_model = current_app.config.get('GEMINI_MODEL')

            if not gemini_model:
                raise Exception("El modelo Gemini no está configurado.")

            if datos_siip is not None and not datos_siip.empty:
                cedula_encontrada_directa = None
                texto_identificador_potencial = user_message
                
                keywords_id_intent = [
                    "ficha juridica", "ficha jurídica", 
                    "situacion juridica", "situación jurídica",
                    "situacion", "situación", 
                    "cedula", "cédula", "sj", "fj"
                ]
                detected_id_keyword_info = None

                try:
                    for kw in keywords_id_intent:
                        pattern_kw_search = r'\b' + re.escape(kw.lower()) + r'\b(?:\s+(?:de|del|la|el|a))?\s*(.+)'
                        match_kw_complex = re.search(pattern_kw_search, user_message_lower, re.IGNORECASE)
                        
                        if match_kw_complex:
                            texto_capturado_como_identificador = match_kw_complex.group(1).strip()
                            detected_id_keyword_info = {"keyword": kw.lower(), "text_after": texto_capturado_como_identificador}
                            texto_identificador_potencial = texto_capturado_como_identificador
                            break 
                    
                    cedula_pattern_str = r'([A-Z0-9\-]{6,20})'
                    match_cedula_pattern = re.match(cedula_pattern_str + r'$', texto_identificador_potencial, re.IGNORECASE)
                    if not match_cedula_pattern and not detected_id_keyword_info:
                        match_cedula_pattern = re.search(r'(?<![\w\-])' + cedula_pattern_str + r'(?![\w\-])', user_message, re.IGNORECASE)

                    if match_cedula_pattern:
                        cedula_encontrada_directa = _validar_y_normalizar_cedula_capturada(match_cedula_pattern.group(1))
                except Exception as cedula_re_error:
                    print(f"Advertencia: Error en regex de cédula: {cedula_re_error}")
                
                current_app.logger.debug(f"DEBUG: cedula_encontrada_directa: {cedula_encontrada_directa}, detected_id_keyword_info: {detected_id_keyword_info}")

                # --- Manejo de respuesta a autorización de seguimiento ---
                if session.get('awaiting_follow_up_authorization'):
                    pending_info = session['awaiting_follow_up_authorization']
                    cedula_auth = pending_info['cedula']
                    info_needed_auth = pending_info['info_needed']
                    nombre_auth = pending_info.get('nombre', f"C.I. {cedula_auth}")

                    if user_message_lower.strip() in ["si", "sí", "si.", "sí.", "ok", "dale", "procede", "autorizo"]:
                        current_app.logger.debug(f"DEBUG: Autorización concedida para C.I. {cedula_auth} para obtener '{info_needed_auth}'.")
                        try:
                            resultados_auth = pd.DataFrame()
                            if 'CEDULA_NORMALIZADA' in datos_siip.columns:
                                resultados_auth = datos_siip[datos_siip['CEDULA_NORMALIZADA'] == cedula_auth]

                            if not resultados_auth.empty:
                                datos_privado_auth = resultados_auth.iloc[0].to_dict()
                                valor_solicitado_auth = None
                                campo_display_auth = info_needed_auth 

                                # Mapping info_needed_auth to DataFrame column name (assuming these are the sensitive ones)
                                col_map_auth = {
                                    "delito": 'DELITO CON MAYOR GRAVEDAD',
                                    "edad": 'EDAD',
                                    # Add other sensitive mappings here if needed
                                }
                                col_name_for_auth = col_map_auth.get(info_needed_auth)

                                if col_name_for_auth and col_name_for_auth in datos_privado_auth:
                                     valor_solicitado_auth = datos_privado_auth.get(col_name_for_auth)
                                     # Use a display name map for sensitive info if needed, otherwise default
                                     campo_display_auth = info_needed_auth.replace('_', ' ').title() # Simple fallback

                                     if valor_solicitado_auth is not None and pd.notna(valor_solicitado_auth) and str(valor_solicitado_auth).strip():
                                         # Use format_value_for_display with column name for correct formatting (dates, percentages)
                                         bot_reply = f"Para {nombre_auth}, la información sobre '{campo_display_auth}' es: {format_value_for_display(valor_solicitado_auth, column_name=col_name_for_auth)}."
                                         accion_detectada = "follow_up_authorized_answered"
                                     else:
                                         bot_reply = f"No encontré información sobre '{campo_display_auth}' para {nombre_auth}."
                                         accion_detectada = "follow_up_authorized_no_data"
                                else:
                                     bot_reply = f"No tengo la información sobre '{campo_display_auth}' disponible en los datos para {nombre_auth}."
                                     accion_detectada = "follow_up_authorized_no_data" # Or a specific error like "column_not_found_for_auth"
                            else:
                                bot_reply = f"No pude recuperar los datos para {nombre_auth} (C.I. {cedula_auth}) después de la autorización."
                                accion_detectada = "follow_up_error_after_auth"
                        except Exception as e_auth_proc:
                            current_app.logger.error(f"ERROR procesando información autorizada para C.I. {cedula_auth} ({nombre_auth}) sobre '{info_needed_auth}': {e_auth_proc}")
                            traceback.print_exc()
                            bot_reply = f"Lo siento, tuve un problema al procesar la información para {nombre_auth} después de la autorización."
                            accion_detectada = "follow_up_error_processing_authorized"
                        
                        del session['awaiting_follow_up_authorization'] # Limpiar estado de espera
                        # Mantener last_person_context si se pudo responder, o limpiarlo si hubo error recuperando datos.
                        if accion_detectada == "follow_up_error_after_auth":
                            if 'last_person_context_cedula' in session: del session['last_person_context_cedula']
                            if 'last_person_context_name' in session: del session['last_person_context_name']
                        session.modified = True

                    elif user_message_lower.strip() in ["no", "no.", "cancela", "cancelar"]:
                        bot_reply = f"Entendido. No accederé a la información de {nombre_auth}."
                        accion_detectada = "follow_up_authorization_denied"
                        del session['awaiting_follow_up_authorization']
                        if 'last_person_context_cedula' in session: del session['last_person_context_cedula'] # Limpiar contexto si se niega
                        if 'last_person_context_name' in session: del session['last_person_context_name']
                        session.modified = True
                    else:
                        # Si la respuesta no es clara, mantener el estado y pedir confirmación de nuevo.
                        bot_reply = f"Por favor, responde 'sí' o 'no' para confirmar si puedo acceder a la información de {nombre_auth} sobre '{info_needed_auth}'."
                        accion_detectada = "awaiting_follow_up_authorization" # Mantener estado
                
                # --- Fin manejo de respuesta a autorización ---

                # --- Manejo de preguntas de seguimiento usando contexto (si last_person_context_cedula existe) ---
                # This block runs if bot_reply is still empty (i.e., not handled by authorization response)
                if not bot_reply and 'last_person_context_cedula' in session:
                    cedula_contexto = session['last_person_context_cedula']
                    nombre_contexto = session.get('last_person_context_name', f"C.I. {cedula_contexto}")

                    # Define patterns for follow-up questions that DO NOT require authorization (answer directly)
                    patrones_seguimiento_no_auth = {
                        "nombre": r"\b(c[oó]mo\s+se\s+llama|cu[aá]l\s+es\s+su\s+nombre|nombre\s+del\s+pdl)\b",
                        "cedula": r"\b(cu[aá]l\s+es\s+su\s+c[eé]dula|dame\s+la\s+c[eé]dula|n[uú]mero\s+de\s+c[eé]dula)\b",
                        "estado_pdl": r"\b(de\s+qu[eé]\s+estado\s+es|cu[aá]l\s+es\s+su\s+estado)\b",
                        "establecimiento": r"\b(d[oó]nde\s+est[aá]\s+(recluso|recluido|preso)|en\s+qu[eé]\s+penal\s+est[aá]|establecimiento)\b",
                        "condicion_juridica": r"\b(condici[oó]n\s+jur[ií]dica|estatus\s+jur[ií]dico)\b",
                        "fase_proceso": r"\b(fase\s+del\s+proceso|en\s+qu[eé]\s+fase\s+est[aá])\b",
                        "fecha_ingreso": r"\b(cu[aá]ndo\s+ingres[oó]|fecha\s+de\s+ingreso)\b",
                        "fecha_nacimiento": r"\b(cu[aá]ndo\s+naci[oó]|fecha\s+de\s+nacimiento)\b",
                        "tiempo_pena": r"\b(cu[aá]nto\s+es\s+su\s+pena|tiempo\s+de\s+pena)\b",
                        "tribunal": r"\b(cu[aá]l\s+es\s+su\s+tribunal|qu[eé]\s+tribunal\s+lleva\s+el\s+caso)\b",
                        "circuito_judicial_pdl": r"\b(cu[aá]l\s+es\s+su\s+circuito|circuito\s+judicial\s+del\s+pdl)\b",
                        "expediente": r"\b(cu[aá]l\s+es\s+su\s+expediente|n[uú]mero\s+de\s+expediente)\b",
                        "indice_delictivo": r"\b([ií]ndice\s+delictivo)\b",
                        "caso_conmocion_publica": r"\b(es\s+caso\s+de\s+conmoci[oó]n\s+p[uú]blica|caso\s+conmoci[oó]n)\b",
                        "tiempo_fisico": r"\b(cu[aá]nto\s+tiempo\s+f[ií]sico\s+tiene|tiempo\s+f[ií]sico)\b",
                        "redenciones": r"\b(cu[aá]ntas\s+redenciones\s+tiene|redenciones\s+computadas)\b",
                        "porcentaje_redencion": r"\b(qu[eé]\s+porcentaje\s+de\s+pena\s+ha\s+cumplido\s+con\s+redenci[oó]n|porcentaje\s+redenci[oó]n)\b",
                        "porcentaje_fisico": r"\b(qu[eé]\s+porcentaje\s+f[ií]sico\s+ha\s+cumplido|porcentaje\s+f[ií]sico)\b",
                        "fecha_cumplimiento_pena": r"\b(cu[aá]ndo\s+cumple\s+pena|fecha\s+de\s+cumplimiento\s+de\s+pena)\b",
                    }

                    # Patrones que SÍ requieren autorización (para iniciar la solicitud de autorización)
                    patrones_seguimiento_auth = {
                         "delito": r"\b(cu[aá]l\s+es\s+el\s+delito|qu[eé]\s+delito\s+(tiene|cometi[oó])|por\s+qu[eé]\s+delito\s+est[aá])\b",
                         "edad": r"\b(qu[eé]\s+edad\s+tiene|cu[aá]ntos\s+a[ñn]os\s+tiene)\b",
                         # Estos patrones disparan el flujo de autorización.
                         # Otros datos sensibles podrían ser inferidos por Gemini basados en el contexto si no se preguntan explícitamente así.
                         "establecimiento": r"\b(d[oó]nde\s+est[aá]\s+(recluso|recluido|preso)|en\s+qu[eé]\s+penal\s+est[aá]|establecimiento)\b",
                         "condicion_juridica": r"\b(condici[oó]n\s+jur[ií]dica|estatus\s+jur[ií]dico)\b",
                         "fase_proceso": r"\b(fase\s+del\s+proceso|en\s+qu[eé]\s+fase\s+est[aá])\b",
                    }

                    # patrones_calculo_pena_especifico eliminado - Gemini manejará esto a través de las instrucciones del prompt principal
                    # si la pregunta llega al fallback de gemini_general.
                    es_pregunta_calculo_pena = False # Esta bandera ya no es estrictamente necesaria aquí si eliminamos el patrón específico.

                    # Mapping from internal key to DataFrame column name and user-friendly display name
                    follow_up_info_map = {
                        "nombre": {"display": "el nombre", "column": 'NOMBRES Y APELLIDOS'},
                        "cedula": {"display": "la cédula", "column": 'CEDULA'},
                        "estado_pdl": {"display": "el estado (circuito judicial)", "column": 'CIRCUITO JUDICIAL'},
                        "establecimiento": {"display": "el establecimiento penitenciario actual", "column": 'ESTABLECIMIENTO PENITENCIARIO'},
                        "condicion_juridica": {"display": "la condición jurídica actual", "column": 'CONDICION JURIDICA'},
                        "fase_proceso": {"display": "la fase del proceso actual", "column": 'FASE DEL PROCESO'},
                        "fecha_ingreso": {"display": "la fecha de ingreso", "column": 'FECHA DE INGRESO'},
                        "fecha_nacimiento": {"display": "la fecha de nacimiento", "column": 'FECHA DE NACIMIENTO'},
                        "edad": {"display": "la edad", "column": 'EDAD'}, # Used for auth pattern
                        "tiempo_pena": {"display": "el tiempo de pena", "column": 'TIEMPO DE PENA'},
                        "tribunal": {"display": "el tribunal", "column": 'NUMERO DE TRIBUNAL'},
                        "circuito_judicial_pdl": {"display": "el circuito judicial", "column": 'CIRCUITO JUDICIAL'},
                        "expediente": {"display": "el número de expediente", "column": 'NUMERO DE EXPEDIENTE'},
                        "indice_delictivo": {"display": "el índice delictivo", "column": 'INDICE DELICTIVO'},
                        "caso_conmocion_publica": {"display": "si es caso de conmoción pública", "column": 'CASO CONMOCION PUBLICA'},
                        "tiempo_fisico": {"display": "el tiempo físico", "column": 'TIEMPO FISICO'},
                        "redenciones": {"display": "las redenciones computadas", "column": 'REDENCIONES COMPUTADAS'},
                        "porcentaje_redencion": {"display": "el porcentaje de pena cumplida con redención", "column": 'PORCENTAJE CUMPLIDO CON REDENCION'},
                        "porcentaje_fisico": {"display": "el porcentaje físico cumplido", "column": 'PORCENTAJE FISICO CUMPLIDO'},
                        "fecha_cumplimiento_pena": {"display": "la fecha de cumplimiento de pena", "column": 'FECHA DE CUMPLIMIENTO DE PENA'},
                        "delito": {"display": "el delito principal", "column": 'DELITO CON MAYOR GRAVEDAD'}, # Used for auth pattern
                    }

                    # ELIMINADO: Manejo directo de patrones_seguimiento_no_auth.
                    # Estos ahora pasarán a Gemini si ningún otro estado específico (como respuesta de autorización) está activo.
                    info_requerida_no_auth = None

                    # Check for auth patterns ONLY if:
                    # 2. bot_reply aún no se ha establecido (es decir, no fue manejada por un patrón no-auth).
                    # 3. No estamos ya esperando una autorización.
                    if not bot_reply and not session.get('awaiting_follow_up_authorization'):
                         info_requerida_auth = None
                         for info_key, pattern in patrones_seguimiento_auth.items():
                             if re.search(pattern, user_message_lower):
                                 info_requerida_auth = info_key
                                 break

                         if info_requerida_auth: # If a sensitive follow-up question is detected
                             current_app.logger.debug(f"DEBUG: Pregunta de seguimiento (auth) detectada para '{info_requerida_auth}' sobre C.I. {cedula_contexto}.")
                             # Guardar estado para pedir autorización
                             session['awaiting_follow_up_authorization'] = {
                                 'cedula': cedula_contexto,
                                 'nombre': nombre_contexto,
                                 'info_needed': info_requerida_auth # Store the internal key
                             }
                             # Get the display name for the sensitive info
                             # Use the same map, assuming keys are consistent
                             info_display_name = follow_up_info_map.get(info_requerida_auth, {}).get('display', info_requerida_auth.replace('_', ' ').title())

                             bot_reply = f"Para responderte sobre {info_display_name} de {nombre_contexto}, necesito tu autorización para acceder a su información. ¿Autorizas el acceso?"
                             accion_detectada = "awaiting_follow_up_authorization"
                             session.modified = True

                # --- Fin manejo de preguntas de seguimiento usando contexto ---


                # Continuar con la lógica normal si bot_reply no fue establecido por la autorización o seguimiento
                if not bot_reply:
                    if cedula_encontrada_directa:
                        # Limpiar contexto de persona anterior si se busca una nueva cédula
                        if 'last_person_context_cedula' in session: del session['last_person_context_cedula']
                        if 'last_person_context_name' in session: del session['last_person_context_name']
                        session.modified = True
                        bot_reply, accion_detectada, ctx_cedula_norm, ctx_nombre_completo = _procesar_solicitud_cedula(
                            cedula_encontrada_directa, datos_siip
                        )
                        if accion_detectada in ["info_cedula_con_opcion_ficha", "info_cedula_error_ficha", "cedula_no_encontrada"]:
                            session['last_person_context_cedula'] = ctx_cedula_norm
                            if ctx_nombre_completo:
                                session['last_person_context_name'] = ctx_nombre_completo
                            elif 'last_person_context_name' in session:
                                 del session['last_person_context_name']
                            session.modified = True
                    elif 'last_name_search_results' in session and session['last_name_search_results']:
                        choice_idx = _parse_user_choice(user_message, len(session['last_name_search_results']))
                        if choice_idx is not None:
                            selected_record = session['last_name_search_results'][choice_idx]
                            cedula_seleccionada = selected_record['CEDULA_NORMALIZADA']
                            original_keyword_for_processing = session.get('original_intent_keyword', 'sj') 
                            simulated_user_message = f"{original_keyword_for_processing} {cedula_seleccionada}"
                            # Limpiar contexto de persona anterior si se selecciona de una lista
                            if 'last_person_context_cedula' in session: del session['last_person_context_cedula']
                            if 'last_person_context_name' in session: del session['last_person_context_name']
                            bot_reply, accion_detectada, ctx_cedula_norm, ctx_nombre_completo = _procesar_solicitud_cedula(
                                cedula_seleccionada, datos_siip
                            )
                            del session['last_name_search_results']
                            if 'original_intent_keyword' in session:
                                del session['original_intent_keyword']
                            session.modified = True
                            if accion_detectada in ["info_cedula_con_opcion_ficha", "info_cedula_error_ficha", "cedula_no_encontrada"]:
                                session['last_person_context_cedula'] = ctx_cedula_norm
                                if ctx_nombre_completo:
                                    session['last_person_context_name'] = ctx_nombre_completo
                                elif 'last_person_context_name' in session:
                                     del session['last_person_context_name']
                                session.modified = True
                        else: 
                            if user_message_lower.strip() in ["cancelar", "cancela", "ninguno", "ninguna"]:
                                bot_reply = "Búsqueda cancelada. ¿En qué más puedo ayudarte?"
                                accion_detectada = "name_search_cancelled"
                                del session['last_name_search_results']
                                if 'original_intent_keyword' in session:
                                    del session['original_intent_keyword']
                                session.modified = True
                            else: 
                                current_app.logger.debug("DEBUG: El mensaje del usuario no es una respuesta válida a la clarificación de nombre pendiente ni una cancelación. Tratando como nueva consulta.")
                                del session['last_name_search_results']
                                if 'original_intent_keyword' in session:
                                    del session['original_intent_keyword']
                                session.modified = True
                    
                    elif 'similar_name_suggestions' in session and session['similar_name_suggestions']:
                        choice_idx = _parse_user_choice(user_message, len(session['similar_name_suggestions']))
                        if choice_idx is not None:
                            selected_record = session['similar_name_suggestions'][choice_idx]
                            cedula_seleccionada = selected_record['CEDULA_NORMALIZADA']
                            original_keyword_for_processing = session.get('original_intent_keyword_similar', 'sj')
                            simulated_user_message = f"{original_keyword_for_processing} {cedula_seleccionada}"
                            # Limpiar contexto de persona anterior si se selecciona de una lista
                            if 'last_person_context_cedula' in session: del session['last_person_context_cedula']
                            if 'last_person_context_name' in session: del session['last_person_context_name']
                            bot_reply, accion_detectada, ctx_cedula_norm, ctx_nombre_completo = _procesar_solicitud_cedula(
                                cedula_seleccionada, datos_siip
                            )
                            del session['similar_name_suggestions']
                            if 'original_intent_keyword_similar' in session: del session['original_intent_keyword_similar']
                            session.modified = True
                            if accion_detectada in ["info_cedula_con_opcion_ficha", "info_cedula_error_ficha", "cedula_no_encontrada"]:
                                session['last_person_context_cedula'] = ctx_cedula_norm
                                if ctx_nombre_completo:
                                    session['last_person_context_name'] = ctx_nombre_completo
                                elif 'last_person_context_name' in session:
                                     del session['last_person_context_name']
                                session.modified = True
                        else: 
                            if user_message_lower.strip() in ["cancelar", "cancela", "ninguno", "ninguna"]:
                                bot_reply = "Búsqueda de sugerencias cancelada. ¿En qué más puedo ayudarte?"
                                accion_detectada = "name_search_cancelled"
                            else:
                                bot_reply = "Opción no válida para las sugerencias. Por favor, elige un número o escribe 'cancelar'."
                                accion_detectada = "similar_name_suggestion_pending" 
                            
                            if 'similar_name_suggestions' in session and accion_detectada != "similar_name_suggestion_pending":
                                 del session['similar_name_suggestions']
                            if 'original_intent_keyword_similar' in session and accion_detectada != "similar_name_suggestion_pending":
                                 del session['original_intent_keyword_similar']
                            session.modified = True

                # --- Manejo de preguntas de seguimiento sobre el último tribunal mencionado ---
                if not bot_reply and session.get('last_tribunal_context'):
                    tribunal_ctx = session['last_tribunal_context']
                    numero_trib_ctx = tribunal_ctx.get('numero')
                    circuito_trib_ctx = tribunal_ctx.get('circuito') # Puede ser string o lista

                    match_tribunal_estado_follow_up = re.search(r'\b(de\s+qu[eé]\s+estado\s+es|a\s+qu[eé]\s+circuito\s+pertenece|cu[aá]l\s+es\s+su\s+circuito|estado\s+del\s+tribunal|ubicaci[oó]n\s+del\s+tribunal|ese\s+1\s+de\s+qu[eé]\s+estado\s+es|el\s+1\s+de\s+qu[eé]\s+estado)\b', user_message_lower)

                    if match_tribunal_estado_follow_up and numero_trib_ctx:
                        current_app.logger.debug(f"DEBUG: Pregunta de seguimiento detectada para tribunal de contexto: {numero_trib_ctx}")
                        if circuito_trib_ctx:
                            if isinstance(circuito_trib_ctx, list):
                                circuitos_str = ", ".join(sorted([str(c) for c in circuito_trib_ctx if pd.notna(c)]))
                                if circuitos_str:
                                    bot_reply = f"El tribunal '{numero_trib_ctx}' está asociado con los siguientes circuitos judiciales: {circuitos_str}."
                                else:
                                    bot_reply = f"Para el tribunal '{numero_trib_ctx}', no tengo información clara sobre su circuito judicial en los datos."
                            else: # Es un string
                                bot_reply = f"El tribunal '{numero_trib_ctx}' pertenece al circuito judicial '{circuito_trib_ctx}'."
                            accion_detectada = "tribunal_context_follow_up_answered"
                        else:
                            bot_reply = f"Identifiqué que te refieres al tribunal '{numero_trib_ctx}', pero no tengo información sobre su circuito judicial o estado en los datos."
                            accion_detectada = "tribunal_context_follow_up_no_data"
                        
                        # Limpiar contexto del tribunal después de responder para evitar que afecte la siguiente pregunta no relacionada.
                        del session['last_tribunal_context']
                        session.modified = True
                
                # --- Manejo de preguntas de desglose para el último tribunal mencionado ---
                if not bot_reply and session.get('last_tribunal_context'):
                    tribunal_ctx = session['last_tribunal_context']
                    numero_trib_ctx = tribunal_ctx.get('numero')
                    # circuitos_asociados_ctx = tribunal_ctx.get('circuito') # Puede ser string o lista

                    match_tribunal_desglose_estado = re.search(r'\b(cu[aá]ntos\s+por\s+(estado|circuito)|desglose\s+por\s+(estado|circuito)|distribuci[oó]n\s+por\s+(estado|circuito))\b', user_message_lower)

                    if match_tribunal_desglose_estado and numero_trib_ctx:
                        current_app.logger.debug(f"DEBUG: Pregunta de desglose por estado/circuito detectada para tribunal de contexto: {numero_trib_ctx}")
                        try:
                            df_activos_tribunal = datos_siip[
                                (datos_siip['NUMERO DE TRIBUNAL'] == numero_trib_ctx) &
                                (datos_siip['ESTATUS'].fillna('').str.upper() == 'ACTIVO')
                            ]
                            if not df_activos_tribunal.empty and 'CIRCUITO JUDICIAL' in df_activos_tribunal.columns:
                                conteo_por_circuito = df_activos_tribunal['CIRCUITO JUDICIAL'].value_counts()
                                if not conteo_por_circuito.empty:
                                    bot_reply = f"Para el tribunal '{numero_trib_ctx}', el desglose de privados de libertad activos por circuito judicial es:<br>"
                                    for circuito, cantidad in conteo_por_circuito.items():
                                        bot_reply += f"- {circuito}: {cantidad} personas<br>"
                                    accion_detectada = "tribunal_context_desglose_answered"
                                else:
                                    bot_reply = f"Aunque el tribunal '{numero_trib_ctx}' tiene privados activos, no pude obtener un desglose por circuito judicial."
                                    accion_detectada = "tribunal_context_desglose_no_data"
                            else:
                                bot_reply = f"No encontré privados de libertad activos para el tribunal '{numero_trib_ctx}' o falta la columna 'CIRCUITO JUDICIAL' para el desglose."
                                accion_detectada = "tribunal_context_desglose_no_data"
                        except Exception as e_desglose:
                            current_app.logger.error(f"Error generando desglose para tribunal {numero_trib_ctx}: {e_desglose}")
                            bot_reply = f"Lo siento, tuve un problema al intentar generar el desglose para el tribunal '{numero_trib_ctx}'."
                            accion_detectada = "tribunal_context_desglose_error"
                        del session['last_tribunal_context'] # Limpiar contexto después de intentar responder
                        session.modified = True
                # --- Fin manejo de preguntas de seguimiento sobre el último tribunal ---


                # Continuar con la lógica normal si bot_reply no fue establecido por la autorización o seguimiento
                if not bot_reply:
                    match_reporte = None 
                    # Solo considerar reporte si no hay una keyword de ID detectada y no estamos en medio de una clarificación de nombre
                    if not detected_id_keyword_info and \
                       not ('last_name_search_results' in session and session['last_name_search_results']) and \
                       not ('similar_name_suggestions' in session and session['similar_name_suggestions']):
                        match_reporte = re.search(r'\b(reporte|lista|listado|relacion|relación|dame|todos|cuantos|quienes son|generar)\b', user_message_lower)
                    
                    if match_reporte:
                        accion_detectada = "reporte"
                        # Limpiar contexto de persona si se pide un reporte general
                        if 'last_tribunal_context' in session: del session['last_tribunal_context']
                        session.modified = True
                        # (el contexto de persona ya se limpia en la lógica de reporte si es necesario)
                        if 'last_person_context_cedula' in session: del session['last_person_context_cedula']
                        if 'last_person_context_name' in session: del session['last_person_context_name']
                        session.modified = True
                        current_app.logger.debug(f"DEBUG: Intención de reporte detectada para: '{user_message}'. Delegando a process_report_request.")
                        
                        temp_bot_reply, temp_accion_detectada = process_report_request(user_message, user_message_lower, datos_siip, gemini_model)

                        if temp_bot_reply:
                            bot_reply = temp_bot_reply
                            accion_detectada = temp_accion_detectada 
                            if temp_accion_detectada not in ["error_nlu", "error_reporte"]:
                                current_app.logger.debug(f"DEBUG: process_report_request proporcionó una respuesta directa o un reporte/conteo. Acción: {accion_detectada}. Respuesta: {bot_reply[:80]}")
                            else:
                                current_app.logger.debug(f"DEBUG: process_report_request encontró un error: {accion_detectada}. Respuesta: {bot_reply[:80]}")
                        else:
                            current_app.logger.debug(f"DEBUG: process_report_request no devolvió un bot_reply. Accion actual: {temp_accion_detectada}. Bot_reply sigue vacío.")
                    else: # No match_reporte
                        # --- Lógica para "pena más baja" ---
                        # (Esta lógica se ejecutará si bot_reply aún está vacío)
                        match_min_pena = None
                        # ELIMINADO: Manejador específico para min_pena. Dejar que Gemini lo maneje.
                        # if not bot_reply: 
                        #     if 'last_tribunal_context' in session: del session['last_tribunal_context'] # Clear tribunal context if asking about pena
                        #     session.modified = True
                        #     match_min_pena = re.search(r'\b(pena\s+m[aá]s\s+baja|pena\s+m[ií]nima|menor\s+pena|m[ií]nima\s+pena|cu[aá]l\s+es\s+la\s+pena\s+m[aá]s\s+baja)\b', user_message_lower)
                        
                        
                        if match_min_pena:
                            accion_detectada = "min_pena_query"
                            current_app.logger.debug("DEBUG: Intención de 'pena más baja' detectada.")
                            try:
                                if 'TIEMPO DE PENA' not in datos_siip.columns:
                                    bot_reply = "Lo siento, la columna 'TIEMPO DE PENA' no está disponible en los datos para calcular el mínimo."
                                else:
                                    # Aplicar filtro "dentro del sistema"
                                    estatus_dentro_del_sistema_qs = [
                                        'ACTIVO', 'HOSPITALIZADO', 
                                        'INGRESO INTERPENAL', 'INGRESO COMISARIA', 'TRASLADO'
                                    ]
                                    df_temp = datos_siip[
                                        datos_siip['ESTATUS'].fillna('').str.upper().isin(estatus_dentro_del_sistema_qs)
                                    ].copy()

                                    df_temp['ANOS_PENA_NUMERICO'] = df_temp['TIEMPO DE PENA'].apply(_parsear_tiempo_pena_a_anos)
                                    df_penas_validas = df_temp.dropna(subset=['ANOS_PENA_NUMERICO'])
                                    df_penas_validas = df_penas_validas[df_penas_validas['ANOS_PENA_NUMERICO'] > 0] 

                                    if not df_penas_validas.empty:
                                        current_app.logger.debug(f"DEBUG (min_pena): {len(df_penas_validas)} penas válidas encontradas en población 'dentro del sistema'.")
                                        min_pena_anos_val = df_penas_validas['ANOS_PENA_NUMERICO'].min()
                                        registros_min_pena = df_penas_validas[df_penas_validas['ANOS_PENA_NUMERICO'] == min_pena_anos_val]
                                        
                                        if not registros_min_pena.empty:
                                            anos_enteros = int(min_pena_anos_val)
                                            meses_decimal = (min_pena_anos_val - anos_enteros) * 12
                                            meses_enteros = int(round(meses_decimal))
                                            pena_formateada = f"{anos_enteros} años"
                                            if meses_enteros > 0:
                                                pena_formateada += f" y {meses_enteros} meses"
                                            
                                            bot_reply = f"La pena más baja registrada en el sistema (mayor a cero) es de {pena_formateada}."
                                            
                                            if len(registros_min_pena) == 1:
                                                registro = registros_min_pena.iloc[0]
                                                nombre = registro.get('NOMBRES Y APELLIDOS', 'No disponible')
                                                cedula = registro.get('CEDULA', 'No disponible')
                                                bot_reply += f"<br>Corresponde a: {nombre} (C.I. {cedula})."
                                                cedula_norm_ctx = _validar_y_normalizar_cedula_capturada(cedula)
                                                if cedula_norm_ctx:
                                                    session['last_person_context_cedula'] = cedula_norm_ctx
                                                    session['last_person_context_name'] = nombre
                                                    session.modified = True
                                                else: 
                                                    if 'last_person_context_cedula' in session: del session['last_person_context_cedula']
                                                    if 'last_person_context_name' in session: del session['last_person_context_name']
                                            else:
                                                bot_reply += f"<br>Esta pena corresponde a {len(registros_min_pena)} personas. Algunas de ellas son:"
                                                for i, (_, registro) in enumerate(registros_min_pena.head(3).iterrows()):
                                                    nombre = registro.get('NOMBRES Y APELLIDOS', 'No disponible')
                                                    cedula = registro.get('CEDULA', 'No disponible')
                                                    bot_reply += f"<br>- {nombre} (C.I. {cedula})"
                                                    if i == 2 and len(registros_min_pena) > 3:
                                                        bot_reply += "<br>... y más."
                                                        break
                                                if 'last_person_context_cedula' in session: del session['last_person_context_cedula']
                                                if 'last_person_context_name' in session: del session['last_person_context_name'] # type: ignore
                                        else:
                                            bot_reply = "No pude encontrar registros con la pena mínima después de calcularla."
                                    else:
                                        bot_reply = "No encontré penas válidas (mayores a cero) para calcular el mínimo. Verifica el formato de los datos en la columna 'TIEMPO DE PENA'."
                            except Exception as e_min_pena:
                                current_app.logger.error(f"Error calculando pena mínima: {e_min_pena}")
                                traceback.print_exc()
                                bot_reply = "Lo siento, tuve un problema al intentar calcular la pena más baja."
                        # --- Fin lógica "pena más baja" ---

                        # --- Lógica para "pena más alta" ---
                        match_max_pena = None
                        # ELIMINADO: Manejador específico para max_pena. Dejar que Gemini lo maneje.
                        # if not bot_reply: 
                        #     if 'last_tribunal_context' in session: del session['last_tribunal_context'] # Clear tribunal context if asking about pena
                        #     session.modified = True
                        #     match_max_pena = re.search(r'\b(pena\s+m[aá]s\s+alta|pena\s+m[aá]xima|mayor\s+pena|m[aá]xima\s+pena|cu[aá]l\s+es\s+la\s+pena\s+m[aá]s\s+alta)\b', user_message_lower)
                        
                        if match_max_pena: 
                            accion_detectada = "max_pena_query"
                            current_app.logger.debug("DEBUG: Intención de 'pena más alta' detectada.")
                            try:
                                if 'TIEMPO DE PENA' not in datos_siip.columns:
                                    bot_reply = "Lo siento, la columna 'TIEMPO DE PENA' no está disponible en los datos para calcular el máximo."
                                else:
                                    # Aplicar filtro "dentro del sistema"
                                    estatus_dentro_del_sistema_qs = [
                                        'ACTIVO', 'HOSPITALIZADO', 
                                        'INGRESO INTERPENAL', 'INGRESO COMISARIA', 'TRASLADO'
                                    ]
                                    df_temp = datos_siip[
                                        datos_siip['ESTATUS'].fillna('').str.upper().isin(estatus_dentro_del_sistema_qs)
                                    ].copy()
                                    df_temp['ANOS_PENA_NUMERICO'] = df_temp['TIEMPO DE PENA'].apply(_parsear_tiempo_pena_a_anos)
                                    df_penas_validas = df_temp.dropna(subset=['ANOS_PENA_NUMERICO'])

                                    if not df_penas_validas.empty:
                                        current_app.logger.debug(f"DEBUG (max_pena): {len(df_penas_validas)} penas válidas encontradas en población 'dentro del sistema'.")
                                        max_pena_anos_val = df_penas_validas['ANOS_PENA_NUMERICO'].max()
                                        registros_max_pena = df_penas_validas[df_penas_validas['ANOS_PENA_NUMERICO'] == max_pena_anos_val]
                                        
                                        if not registros_max_pena.empty:
                                            anos_enteros = int(max_pena_anos_val)
                                            meses_decimal = (max_pena_anos_val - anos_enteros) * 12
                                            meses_enteros = int(round(meses_decimal)) 
                                            pena_formateada = f"{anos_enteros} años"
                                            if meses_enteros > 0:
                                                pena_formateada += f" y {meses_enteros} meses"
                                            
                                            bot_reply = f"La pena más alta registrada en el sistema es de {pena_formateada}."
                                            
                                            if len(registros_max_pena) == 1:
                                                registro = registros_max_pena.iloc[0]
                                                nombre = registro.get('NOMBRES Y APELLIDOS', 'No disponible')
                                                cedula = registro.get('CEDULA', 'No disponible')
                                                bot_reply += f"<br>Corresponde a: {nombre} (C.I. {cedula})."
                                                cedula_norm_ctx = _validar_y_normalizar_cedula_capturada(cedula)
                                                if cedula_norm_ctx:
                                                    session['last_person_context_cedula'] = cedula_norm_ctx
                                                    session['last_person_context_name'] = nombre
                                                    session.modified = True
                                                else: 
                                                    if 'last_person_context_cedula' in session: del session['last_person_context_cedula']
                                                    if 'last_person_context_name' in session: del session['last_person_context_name']
                                            else:
                                                bot_reply += f"<br>Esta pena corresponde a {len(registros_max_pena)} personas. Algunas de ellas son:"
                                                for i, (_, registro) in enumerate(registros_max_pena.head(3).iterrows()): 
                                                    nombre = registro.get('NOMBRES Y APELLIDOS', 'No disponible')
                                                    cedula = registro.get('CEDULA', 'No disponible')
                                                    bot_reply += f"<br>- {nombre} (C.I. {cedula})"
                                                    if i == 2 and len(registros_max_pena) > 3: 
                                                        bot_reply += "<br>... y más."
                                                        break
                                                if 'last_person_context_cedula' in session: del session['last_person_context_cedula']
                                                if 'last_person_context_name' in session: del session['last_person_context_name'] # type: ignore
                                        else: 
                                            bot_reply = "No pude encontrar registros con la pena máxima después de calcularla."
                                    else:
                                        bot_reply = "No encontré penas válidas para calcular el máximo. Verifica el formato de los datos en la columna 'TIEMPO DE PENA'."
                            except Exception as e_max_pena:
                                current_app.logger.error(f"Error calculando pena máxima: {e_max_pena}")
                                traceback.print_exc() 
                                bot_reply = "Lo siento, tuve un problema al intentar calcular la pena más alta."
                        # --- Fin lógica "pena más alta" ---

                        # --- Lógica para "tribunal con más privados" ---
                        match_tribunal_max_pdl = None
                        # ELIMINADO: Manejador específico para tribunal_max_pdl. Dejar que Gemini lo maneje.
                        # if not bot_reply: # Solo si no se ha generado respuesta para pena alta/baja
                        #     if 'last_person_context_cedula' in session: del session['last_person_context_cedula'] # Clear person context if asking about tribunals
                        #     session.modified = True
                        #     match_tribunal_max_pdl = re.search(r'\b(qu[eé]\s+tribunal\s+tiene\s+m[aá]s\s+privados|tribunal\s+con\s+m[aá]s\s+pdl|mayor\s+poblaci[oó]n\s+por\s+tribunal)\b', user_message_lower)

                        if match_tribunal_max_pdl:
                            accion_detectada = "max_pdl_tribunal_query"
                            current_app.logger.debug("DEBUG: Intención de 'tribunal con más privados' detectada.")
                            try:
                                if 'NUMERO DE TRIBUNAL' not in datos_siip.columns or 'ESTATUS' not in datos_siip.columns:
                                    bot_reply = "Lo siento, las columnas 'NUMERO DE TRIBUNAL' o 'ESTATUS' no están disponibles en los datos para realizar este cálculo."
                                else:
                                    # Aplicar filtro "dentro del sistema"
                                    estatus_dentro_del_sistema_qs = [
                                        'ACTIVO', 'HOSPITALIZADO', 
                                        'INGRESO INTERPENAL', 'INGRESO COMISARIA', 'TRASLADO'
                                    ]
                                    df_poblacion_relevante_tribunal = datos_siip[
                                        datos_siip['ESTATUS'].fillna('').str.upper().isin(estatus_dentro_del_sistema_qs)
                                    ].copy()
                                    if not df_poblacion_relevante_tribunal.empty:
                                        conteo_por_tribunal = df_poblacion_relevante_tribunal['NUMERO DE TRIBUNAL'].value_counts()
                                        if not conteo_por_tribunal.empty:
                                            tribunal_max = conteo_por_tribunal.idxmax()
                                            cantidad_max = conteo_por_tribunal.max()
                                            
                                            circuitos_del_tribunal_max_serie = df_poblacion_relevante_tribunal[df_poblacion_relevante_tribunal['NUMERO DE TRIBUNAL'] == tribunal_max]['CIRCUITO JUDICIAL'].dropna().unique()
                                            circuitos_del_tribunal_max = [str(c) for c in circuitos_del_tribunal_max_serie if pd.notna(c)]

                                            circuito_info_str = ""
                                            if circuitos_del_tribunal_max:
                                                if len(circuitos_del_tribunal_max) == 1:
                                                    circuito_judicial_max_str = circuitos_del_tribunal_max[0]
                                                    circuito_info_str = f" (Circuito Judicial: {circuito_judicial_max_str})"
                                                    session['last_tribunal_context'] = {'numero': tribunal_max, 'circuito': circuito_judicial_max_str}
                                                else: # Múltiples circuitos para ese número de tribunal
                                                    circuitos_list_str = ", ".join(sorted(circuitos_del_tribunal_max))
                                                    circuito_info_str = f" (aparece en los circuitos: {circuitos_list_str})"
                                                    session['last_tribunal_context'] = {'numero': tribunal_max, 'circuito': sorted(circuitos_del_tribunal_max)} # Guardar lista
                                                session.modified = True
                                            bot_reply = f"El tribunal con más privados de libertad activos es el '{tribunal_max}'{circuito_info_str}, con {cantidad_max} personas."
                                        else:
                                            bot_reply = "No pude encontrar información sobre la cantidad de privados por tribunal (conteo vacío)."
                                    else:
                                        bot_reply = "No hay privados de libertad 'dentro del sistema' para calcular qué tribunal tiene más."
                            except Exception as e_trib_max:
                                current_app.logger.error(f"Error calculando tribunal con más privados: {e_trib_max}")
                                traceback.print_exc()
                                bot_reply = "Lo siento, tuve un problema al intentar determinar qué tribunal tiene más privados de libertad."
                        # --- Fin lógica "tribunal con más privados" ---

                        
                        # Si no fue pregunta de pena (máxima o mínima) y bot_reply sigue vacío, continuar con búsqueda por nombre
                        if not bot_reply: 
                            # Limpiar contexto de tribunal si se inicia una búsqueda por nombre
                            if 'last_tribunal_context' in session: del session['last_tribunal_context']
                            session.modified = True
                            # Limpiar contexto de persona si se inicia una búsqueda por nombre
                            if 'last_person_context_cedula' in session: del session['last_person_context_cedula']
                            if 'last_person_context_name' in session: del session['last_person_context_name']
                            session.modified = True
                            texto_a_usar_para_nombre = texto_identificador_potencial
                            current_app.logger.debug(f"DEBUG: Texto a usar para búsqueda por nombre: '{texto_a_usar_para_nombre}'")

                            nombre_parts_filtrado = _normalizar_partes_nombre(texto_a_usar_para_nombre)
                            
                            if len(nombre_parts_filtrado) >= 1:
                                current_app.logger.debug(f"DEBUG: Intentando búsqueda por nombre con partes normalizadas: {nombre_parts_filtrado}")
                                resultados_nombre = _buscar_por_nombre(datos_siip, nombre_parts_filtrado)
                                
                                if not resultados_nombre.empty:
                                    if len(resultados_nombre) == 1:
                                        cedula_encontrada_por_nombre = resultados_nombre.iloc[0]['CEDULA_NORMALIZADA']
                                        keyword_para_procesar = detected_id_keyword_info['keyword'] if detected_id_keyword_info else "sj"
                                        simulated_user_message = f"{keyword_para_procesar} {cedula_encontrada_por_nombre}"
                                        bot_reply, accion_detectada, ctx_cedula_norm, ctx_nombre_completo = _procesar_solicitud_cedula(
                                            cedula_encontrada_por_nombre, datos_siip
                                        )
                                        if accion_detectada in ["info_cedula_con_opcion_ficha", "info_cedula_error_ficha", "cedula_no_encontrada"]:
                                            session['last_person_context_cedula'] = ctx_cedula_norm
                                            if ctx_nombre_completo:
                                                session['last_person_context_name'] = ctx_nombre_completo
                                            elif 'last_person_context_name' in session:
                                                 del session['last_person_context_name']
                                            session.modified = True
                                    elif len(resultados_nombre) > 1:
                                        session['last_name_search_results'] = resultados_nombre[['CEDULA', 'NOMBRES Y APELLIDOS', 'CEDULA_NORMALIZADA']].to_dict('records')
                                        if detected_id_keyword_info:
                                            session['original_intent_keyword'] = detected_id_keyword_info['keyword']
                                        session.modified = True
                                        
                                        bot_reply = "Encontré varias coincidencias. Por favor, indica el número de la opción que deseas:<br>"
                                        for i, record in enumerate(session['last_name_search_results'][:10]):
                                            bot_reply += f"{i+1}. {record['NOMBRES Y APELLIDOS']} (C.I. {record['CEDULA']})<br>"
                                        if len(session['last_name_search_results']) > 10:
                                            bot_reply += "... y más resultados. Por favor, sé más específico si no está en la lista."
                                        accion_detectada = "name_search_clarification_pending"
                                else: 
                                    current_app.logger.debug(f"Nombre exacto no encontrado para: {nombre_parts_filtrado}. Intentando búsqueda similar para: '{texto_a_usar_para_nombre}'")
                                    resultados_similares = _buscar_nombres_similares(datos_siip, texto_a_usar_para_nombre)
                                    if not resultados_similares.empty:
                                        session['similar_name_suggestions'] = resultados_similares[['CEDULA', 'NOMBRES Y APELLIDOS', 'CEDULA_NORMALIZADA']].to_dict('records')
                                        if detected_id_keyword_info:
                                            session['original_intent_keyword_similar'] = detected_id_keyword_info['keyword']
                                        session.modified = True
                                        
                                        bot_reply = f"No encontré una coincidencia exacta para '{texto_a_usar_para_nombre}'. ¿Quizás quisiste decir alguna de estas opciones?<br>"
                                        for i, record in enumerate(session['similar_name_suggestions'][:10]):
                                            bot_reply += f"{i+1}. {record['NOMBRES Y APELLIDOS']} (C.I. {record['CEDULA']})<br>"
                                        if len(session['similar_name_suggestions']) > 10:
                                            bot_reply += "... y más resultados."
                                        accion_detectada = "similar_name_suggestion_pending"
                                    else: 
                                        current_app.logger.debug(f"No se encontraron resultados similares para: {texto_a_usar_para_nombre}")
                                        if detected_id_keyword_info: 
                                            bot_reply = f"No encontré a '{texto_a_usar_para_nombre}' en el sistema. Por favor, verifica el nombre o proporciona una cédula."
                                            accion_detectada = "name_not_found_after_keyword"
                                        elif not match_reporte: 
                                            accion_detectada = "gemini_general"
                            else: 
                                current_app.logger.debug(f"Nombre parts filtrado < 1. Texto original para nombre: '{texto_a_usar_para_nombre}'. Parts: {nombre_parts_filtrado}")
                                if not detected_id_keyword_info and not match_reporte: 
                                    accion_detectada = "gemini_general"


                    # --- Lógica para preguntas relativas a la última fecha de estadísticas (ej. día anterior) ---
                    if not bot_reply and 'last_stat_date_str' in session:
                        # ELIMINADO: Manejador específico para estadísticas del "día anterior". Dejar que Gemini lo maneje si es relevante.
                        pass
                        patrones_dia_anterior = [
                            r"y\s+(?:el|del)\s+d[ií]a\s+anterior",
                            r"el\s+d[ií]a\s+anterior\s+a\s+ese",
                            r"y\s+el\s+d[ií]a\s+antes",
                            r"del\s+d[ií]a\s+previo"
                        ]
                        match_dia_anterior = None
                        # for patron in patrones_dia_anterior:
                        #     match_dia_anterior = re.search(patron, user_message_lower, re.IGNORECASE)
                        #     if match_dia_anterior:
                        #         break
                        
                        # if match_dia_anterior:
                        #     try:
                        #         last_stat_date = date.fromisoformat(session['last_stat_date_str'])
                        #         fecha_solicitada_relativa = last_stat_date - timedelta(days=1)
                        #         session['last_stat_date_str'] = fecha_solicitada_relativa.isoformat() 
                        #         current_app.logger.debug(f"Detectada pregunta relativa 'día anterior'. Nueva fecha solicitada: {fecha_solicitada_relativa}")
                                
                        #         libertades, error_msg = _contar_libertades_en_fecha(fecha_solicitada_relativa, datos_siip)
                        #         if error_msg:
                        #             bot_reply = f"No puedo verificar el número de libertades para el día anterior ({fecha_solicitada_relativa.strftime('%d/%m/%Y')}): {error_msg}"
                        #             accion_detectada = "error_stat_libertades_datos_faltantes_relativa"
                        #         else:
                        #             bot_reply = f"Para el día anterior ({fecha_solicitada_relativa.strftime('%d/%m/%Y')}), se registraron {libertades} libertades según los datos del SIIP."
                        #             accion_detectada = "stat_libertades_fecha_relativa"
                        #     except Exception as e_rel_stat:
                        #         current_app.logger.error(f"Error procesando pregunta de libertades relativa: {e_rel_stat}")
                        #         bot_reply = "Tuve un problema al procesar tu solicitud para el día anterior."
                        #         accion_detectada = "error_stat_libertades_general_relativa"

                    # --- Lógica para preguntas sobre estadísticas del mes actual (ej. libertades este mes) ---
                    if not bot_reply:
                        # ELIMINADO: Manejador específico para "libertades este mes". Dejar que Gemini lo maneje.
                        pass
                        patrones_libertades_mes_actual = [
                            r"(cuántas|cuantas|numero\s+de|total\s+de)\s+libertades\s+(?:va[mn]\s+en|en|durante)\s+(?:este|el\s+actual)\s+mes", 
                            r"libertades\s+de\s+(?:este|el\s+actual)\s+mes"
                        ]
                        match_libertades_mes_actual = None
                        for patron in patrones_libertades_mes_actual:
                            match_libertades_mes_actual = re.search(patron, user_message_lower, re.IGNORECASE)
                        #     if match_libertades_mes_actual:
                        #         break
                        
                        # if match_libertades_mes_actual:
                        #     try:
                        #         today = date.today()
                        #         first_day_of_month = today.replace(day=1)
                        #         current_app.logger.debug(f"Detectada pregunta sobre libertades este mes. Rango: {first_day_of_month} a {today}")

                        #         if 'FECHA CAMBIO ESTATUS' in datos_siip.columns and \
                        #            'ESTATUS' in datos_siip.columns and \
                        #            pd.api.types.is_datetime64_any_dtype(datos_siip['FECHA CAMBIO ESTATUS']):
                                    
                        #             df_temp = datos_siip.copy()
                        #             df_temp['FECHA_CAMBIO_DIA'] = pd.to_datetime(df_temp['FECHA CAMBIO ESTATUS'], errors='coerce').dt.date
                                    
                        #             condicion_rango_fecha = (df_temp['FECHA_CAMBIO_DIA'] >= first_day_of_month) & (df_temp['FECHA_CAMBIO_DIA'] <= today)
                        #             condicion_estatus_pasivo = (df_temp['ESTATUS'].fillna('').str.upper() == 'PASIVO')
                                    
                        #             libertades_en_mes = df_temp[condicion_rango_fecha & condicion_estatus_pasivo].shape[0]
                                    
                        #             bot_reply = f"Según los datos del SIIP, en el mes actual (desde el {first_day_of_month.strftime('%d/%m/%Y')} hasta hoy, {today.strftime('%d/%m/%Y')}), se han registrado un total de {libertades_en_mes} libertades."
                        #             accion_detectada = "stat_libertades_mes_actual"
                        #         else:
                        #             bot_reply = "No puedo verificar el número de libertades este mes porque faltan datos necesarios (ESTATUS o FECHA CAMBIO ESTATUS) o no están en el formato correcto en el sistema."
                        #             accion_detectada = "error_stat_libertades_mes_datos_faltantes"
                        #     except Exception as e_stat_mes:
                        #         current_app.logger.error(f"Error procesando pregunta de libertades este mes: {e_stat_mes}")
                        #         bot_reply = "Tuve un problema al intentar calcular las libertades para este mes."
                        #         accion_detectada = "error_stat_libertades_mes_general"

                    # --- Lógica para preguntas específicas sobre estadísticas (ej. libertades) ---
                    if not bot_reply: 
                        # ELIMINADO: Manejador específico para "libertades en fecha X". Dejar que Gemini lo maneje.
                        pass
                        patrones_libertades_fecha = [
                            r"(cuántas|cuantas|numero\s+de|total\s+de)\s+libertades\s*(?:otorgadas|dadas|hubo|hubieron)?\s+(?:el\s*(?:día|dia)?|en\s+fecha|para\s+el\s*(?:día|dia)?|para\s+la\s+fecha)\s+([\d\/\-.\s]+\d)",
                            r"(libertades)\s+del?\s*(?:día|dia|fecha)?\s*([\d\/\-.\s]+\d)"
                        ]
                        match_libertades_fecha = None
                        # for patron in patrones_libertades_fecha:
                        #     match_libertades_fecha = re.search(patron, user_message_lower, re.IGNORECASE)
                        #     if match_libertades_fecha:
                        #         break
                        
                        # if match_libertades_fecha:
                        #     fecha_texto = match_libertades_fecha.group(match_libertades_fecha.lastindex).strip()
                        #     try:
                        #         fecha_solicitada = date_parser.parse(fecha_texto, dayfirst=True).date()
                        #         current_app.logger.debug(f"Detectada pregunta sobre libertades para fecha: {fecha_solicitada}")
                                
                        #         libertades, error_msg = _contar_libertades_en_fecha(fecha_solicitada, datos_siip)
                        #         if error_msg:
                        #             bot_reply = f"No puedo verificar el número de libertades en esa fecha ({fecha_solicitada.strftime('%d/%m/%Y')}): {error_msg}"
                        #             accion_detectada = "error_stat_libertades_datos_faltantes"
                        #         else:
                        #             bot_reply = f"Según los datos del SIIP, el {fecha_solicitada.strftime('%d/%m/%Y')} se registraron {libertades} libertades."
                        #             accion_detectada = "stat_libertades_fecha"
                        #             session['last_stat_date_str'] = fecha_solicitada.isoformat()
                        #             session.modified = True

                        #     except (ValueError, TypeError) as date_err:
                        #         current_app.logger.warning(f"Error parseando fecha '{fecha_texto}' para libertades: {date_err}")
                        #         if not bot_reply: accion_detectada = "gemini_general" # Fallback if date parsing fails
                        #     except Exception as e_stat:
                        #         current_app.logger.error(f"Error procesando pregunta de libertades: {e_stat}")
                        #         bot_reply = "Tuve un problema al intentar calcular las libertades para esa fecha."
                        #         accion_detectada = "error_stat_libertades_general"

                    current_app.logger.debug(f"PRE-FINAL FALLBACK: accion_detectada='{accion_detectada}', bot_reply_empty={not bot_reply}")
                    if not bot_reply and accion_detectada not in ["name_search_clarification_pending", "similar_name_suggestion_pending", "info_cedula_con_opcion_ficha", "info_cedula_error_ficha", "cedula_no_encontrada", "error_ficha", "error_pdf", "error_nlu", "error_reporte", "error_datos", "name_search_cancelled", "name_not_found_after_keyword", "stat_libertades_fecha", "stat_libertades_mes_actual", "stat_libertades_fecha_relativa", "max_pena_query", "min_pena_query", "context_follow_up_answered", "context_follow_up_no_data", "context_follow_up_error", "awaiting_follow_up_authorization", "follow_up_authorized_answered", "follow_up_authorized_no_data", "follow_up_error_after_auth", "follow_up_authorization_denied", "max_pdl_tribunal_query", "tribunal_context_follow_up_answered", "tribunal_context_follow_up_no_data", "tribunal_context_desglose_answered", "tribunal_context_desglose_no_data", "tribunal_context_desglose_error"]:
                        accion_detectada = "gemini_general"
                        current_app.logger.debug("ENTERING FINAL FALLBACK to gemini_general (bot_reply vacío y acción no es de espera/manejo específico)")
                        
                        try:
                            timezone_venezuela = pytz.timezone('America/Caracas')
                            now_venezuela = datetime.now(timezone_venezuela)
                            fecha_actual_vzla_prompt = now_venezuela.strftime("%Y-%m-%d")
                            hora_actual_vzla_prompt = now_venezuela.strftime("%H:%M")
                        except Exception as tz_err:
                            current_app.logger.error(f"Error obteniendo fecha/hora de Venezuela: {tz_err}. Usando UTC.")
                            now_utc = datetime.utcnow()
                            fecha_actual_vzla_prompt = now_utc.strftime("%Y-%m-%d") + " (UTC)"
                            hora_actual_vzla_prompt = now_utc.strftime("%H:%M") + " (UTC)"

                        contexto_para_gemini = f"""
Eres 'Sucre', un asistente IA conversacional y servicial. Tu especialidad principal es el Sistema Integrado de Información Penitenciaria (SIIP) de Venezuela, pero también puedes usar tu conocimiento general para responder preguntas que no estén directamente relacionadas con el SIIP si el usuario lo solicita o si la pregunta es claramente de índole general. Tu objetivo principal es ser útil y mantener el contexto de la conversación.
Tu nombre es Sucre.

Información contextual general (para tu conocimiento):
- La fecha de hoy es: {fecha_actual_vzla_prompt}. Cuando te pregunten por la fecha, usa esta información y preséntala de forma amigable (ej. "Hoy es jueves, 08 de mayo de 2025").
- La hora actual es: {hora_actual_vzla_prompt}. Cuando te pregunten por la hora, usa esta información y preséntala de forma amigable (ej. "Son las 09:30 AM").
"""
                        # Añadir contexto de persona activa si existe
                        if 'last_person_context_cedula' in session:
                            nombre_ctx_gemini = session.get('last_person_context_name', f"C.I. {session['last_person_context_cedula']}")
                            # Obtener los datos completos de la persona en contexto para pasárselos a Gemini
                            datos_persona_contexto_str = "Información detallada no disponible en este momento para esta persona."
                            if datos_siip is not None and not datos_siip.empty and 'CEDULA_NORMALIZADA' in datos_siip.columns:
                                persona_en_contexto_df = datos_siip[datos_siip['CEDULA_NORMALIZADA'] == session['last_person_context_cedula']]
                                if not persona_en_contexto_df.empty:
                                    datos_persona_dict = persona_en_contexto_df.iloc[0].to_dict()
                                    # Formatear los datos de la persona para el prompt
                                    datos_persona_items = []
                                    for k_col, v_val in datos_persona_dict.items():
                                        # Omitir columnas internas o muy largas/complejas para el prompt directo
                                        if k_col not in ['N_CEDULA_NUMERIC', 'CEDULA_NORMALIZADA', 'NOMBRE_NORMALIZADO', 'FOTO'] and pd.notna(v_val) and str(v_val).strip():
                                            datos_persona_items.append(f"  - {k_col.replace('_', ' ').title()}: {format_value_for_display(v_val, column_name=k_col)}")
                                    if datos_persona_items:
                                        datos_persona_contexto_str = "\n".join(datos_persona_items)

                            contexto_persona_activa_str = (
                                f"\n\nIMPORTANTE: CONTEXTO DE PERSONA ACTIVA (SIIP):\n"
                                f"Actualmente la conversación podría estar girando en torno a **{nombre_ctx_gemini} (C.I. {session['last_person_context_cedula']})**.\n"
                                f"Aquí tienes los datos disponibles sobre esta persona del SIIP:\n"
                                f"{datos_persona_contexto_str}\n"
                                f"Si la pregunta del usuario parece referirse a esta persona (usando pronombres como 'él', 'ella', 'ese PDL', 'la persona que consulté', o si la pregunta es una continuación natural de la conversación sobre esta persona), DEBES priorizar responder usando estos datos del SIIP.\n"
                                f"Si la pregunta es sobre un campo específico de esta persona que no está en los datos proporcionados arriba, indica que esa información específica no está disponible para {nombre_ctx_gemini} en el SIIP.\n"
                                f"Si la pregunta es claramente sobre un tema nuevo, una persona diferente (ej. el usuario proporciona una nueva cédula o nombre), una solicitud de reporte general, o una pregunta general no relacionada con el SIIP, entonces puedes ignorar este contexto de persona activa.\n"
                                f"Si el usuario expresa frustración porque no entendiste una pregunta de seguimiento, o pregunta sobre tu capacidad para entender el contexto, responde de forma empática. Explica brevemente que intentas mantener el contexto de la última persona consultada, pero a veces necesitas que la pregunta sea más específica si no coincide con tus patrones conocidos o si la información no está disponible. Evita sonar repetitivo o demasiado robótico."
                                f"**Cálculo de Cumplimiento de Pena:** Si el usuario pregunta cuánto tiempo le falta a esta persona para cumplir un porcentaje de pena (ej. 75%, 100%), y en los datos de la persona tienes 'TIEMPO DE PENA' y 'TIEMPO FISICO CON REDENCIONES', debes:\n"
                                f"  1. Usar el 'TIEMPO DE PENA' total.\n"
                                f"  2. Calcular el porcentaje solicitado de esa 'TIEMPO DE PENA' (ej. 75% de 16 años).\n"
                                f"  3. Restar el 'TIEMPO FISICO CON REDENCIONES' del resultado del paso 2 para obtener el tiempo faltante.\n"
                                f"  4. Presenta la respuesta claramente, indicando el tiempo total de la pena, el tiempo requerido para el porcentaje, el tiempo ya cumplido con redenciones, y el tiempo faltante. Convierte los resultados a años, meses y días de forma legible."
                            )
                            contexto_para_gemini += contexto_persona_activa_str
                        else:
                            contexto_para_gemini += "\n\nActualmente no hay un privado de libertad específico en contexto en la conversación.\n"

                        contexto_para_gemini += """

Tus capacidades y cómo debes usarlas:
1.  **Información del SIIP (Prioridad Alta si es relevante):**
    - Si el usuario proporciona una cédula o nombre para buscar en el SIIP, el sistema Python lo manejará. Tu rol es entender si la pregunta es de seguimiento sobre esa persona (usa el CONTEXTO DE PERSONA ACTIVA).
    - Si el usuario pide un reporte del SIIP, el sistema Python lo manejará.
2.  **Preguntas Legales (RAG):**
    - Si la pregunta es sobre leyes o artículos, el sistema Python usará RAG.
3.  **Preguntas Generales y Conversacionales:**
    - **Tu Nombre:** Si te preguntan tu nombre, responde que te llamas Sucre.
    - **Fecha y Hora:** Si te preguntan la fecha o la hora, usa la "Información contextual general" proporcionada.
    - **Ayuda:** Si el usuario pide "ayuda" o quiere saber qué puedes hacer, explica tus capacidades principales:
        - Consultar información de privados de libertad del SIIP (por cédula o nombre).
        - Generar reportes en PDF sobre datos del SIIP.
        - Responder preguntas sobre leyes y artículos.
        - Responder preguntas generales y mantener una conversación.
    - **Conocimiento General:** Para preguntas que no son sobre el SIIP, leyes, o funciones específicas, usa tu conocimiento general para responder.
    - **Cálculos:** Realiza cálculos si se te solicitan.
    - **Personalidades:** Si te preguntan "quién es Julio Zerpa", responde que es el actual Ministro del Poder Popular para el Servicio Penitenciario en Venezuela.

Comportamiento Conversacional:
- no puedes responder preguntas sobre los siguientes temas, politica,religion,sexo
- Sé amable y servicial.
- Si no entiendes una pregunta, pide una clarificación en lugar de dar una respuesta incorrecta o demasiado genérica.
- Si una pregunta es ambigua pero hay un "CONTEXTO DE PERSONA ACTIVA", asume que la pregunta es sobre esa persona a menos que sea claramente sobre otra cosa.
- Evita respuestas como "Necesito más información para poder ayudarte" si el contexto de la conversación (historial o persona activa) puede ayudarte a inferir la intención. Intenta primero usar el contexto.
- **Memoria y Contexto de Conversación:** El "Historial reciente de la conversación" que se te proporciona ES tu memoria de la conversación actual. Úsalo para responder preguntas sobre interacciones previas DENTRO de esta misma sesión. No afirmes que no recuerdas la conversación actual. Si te preguntan sobre algo que ocurrió en la conversación actual (ej. "cuál fue la primera pregunta que te hice?"), busca en el historial proporcionado y responde de la mejor manera posible.

"""
            else: 
                 current_app.logger.debug("DEBUG: No hay datos SIIP para el contexto.")
                 bot_reply = "No se pudieron cargar los datos del sistema SIIP. No puedo procesar tu solicitud."
                 accion_detectada = "error_datos"

            if accion_detectada == "gemini_general" or accion_detectada.startswith("gemini_"): # "gemini_procesar_cedula_directo" ya no existe
                if gemini_model:
                    # Limitar el historial enviado a Gemini si es muy largo,
                    # aunque ahora se almacena completo en BD.
                    MAX_HISTORY_FOR_GEMINI = 40 # Número de pares de mensajes (usuario + bot)
                    history_for_gemini = current_conversation_history[-(MAX_HISTORY_FOR_GEMINI*2):]
                    history_text = "\n".join(history_for_gemini)
                    
                    # Construir el prompt final para Gemini
                    # contexto_para_gemini ya contiene la instrucción general y el contexto_persona_activa_str (si aplica)
                    prompt = f"Historial reciente de la conversación:\n{history_text}\n\nInstrucciones y Contexto para Sucre (tú):\n{contexto_para_gemini}\n\nPregunta del Usuario: {user_message}\nRespuesta de Sucre:"
                    current_app.logger.debug(f"--- Prompt para Gemini (Acción: {accion_detectada}) ---\n{prompt}\n------------------------")
                    try:
                        response = gemini_model.generate_content(prompt)
                        if response.parts: bot_reply = response.text
                        else:
                            current_app.logger.warning("Advertencia: Gemini no devolvió contenido."); bot_reply = "No sé cómo responder."
                            if response.prompt_feedback: current_app.logger.warning(f"Feedback: {response.prompt_feedback}")
                    except Exception as gemini_call_err:
                        print(f"ERROR al llamar a Gemini: {gemini_call_err}")
                        bot_reply = "Tuve un problema contactando a mi asistente IA. Intenta de nuevo."
                else:
                    bot_reply = "Lo siento, mi asistente IA no está disponible."

            elif not bot_reply and accion_detectada not in ["name_search_clarification_pending", "similar_name_suggestion_pending", "info_cedula_con_opcion_ficha", "info_cedula_error_ficha", "cedula_no_encontrada", "error_ficha", "error_pdf", "error_nlu", "error_reporte", "error_datos", "name_search_cancelled", "name_not_found_after_keyword", "max_pena_query", "min_pena_query", "context_follow_up_answered", "context_follow_up_no_data", "context_follow_up_error", "awaiting_follow_up_authorization", "follow_up_authorized_answered", "follow_up_authorized_no_data", "follow_up_error_after_auth", "follow_up_authorization_denied", "max_pdl_tribunal_query", "tribunal_context_follow_up_answered", "tribunal_context_follow_up_no_data", "tribunal_context_desglose_answered", "tribunal_context_desglose_no_data", "tribunal_context_desglose_error"]:
                 current_app.logger.error(f"ERROR: Accion fue '{accion_detectada}' pero bot_reply está vacío y no es un estado de espera o error manejado.")
                 bot_reply = "Lo siento, no pude procesar tu solicitud correctamente."
        except Exception as e:
            print(f"ERROR INESPERADO en send_message: {e}")
            traceback.print_exc()
            bot_reply = "Lo siento, ocurrió un error interno inesperado."

    # Guardar la interacción completa (mensaje de usuario y respuesta del bot) en la base de datos
    if conversation:
        # Asegurar que history_data sea una lista
        if not isinstance(conversation.history_data, list):
            conversation.history_data = []
            # Si se inicializa, es una modificación
            flag_modified(conversation, "history_data")

        if user_message:
            conversation.history_data.append(f"Usuario: {user_message}")
            flag_modified(conversation, "history_data") # Marcar como modificado
            current_app.logger.debug(f"Añadido mensaje de usuario al historial de conversación {conversation.id}")

        if bot_reply:
            conversation.history_data.append(f"Sucre: {bot_reply}")
            flag_modified(conversation, "history_data") # Marcar como modificado
            current_app.logger.debug(f"Añadida respuesta de Sucre al historial de conversación {conversation.id}")

        # Solo hacer commit si hubo cambios efectivos.
        if user_message or bot_reply: # O una condición más explícita si se modificó
            try:
                db.session.commit()
                current_app.logger.info(f"Historial de conversación {conversation.id} guardado en BD. Total mensajes: {len(conversation.history_data)}")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error guardando conversación {conversation.id} en BD: {e}", exc_info=True)
                # No sobrescribir bot_reply aquí, ya que el usuario debe recibir la respuesta original.
    else: # Fallback si la conversación no se pudo cargar/crear
        current_app.logger.error("La conversación no estaba disponible para guardar el historial.")

    if not bot_reply and accion_detectada not in ["name_search_clarification_pending", "similar_name_suggestion_pending", "awaiting_follow_up_authorization"]: # Añadido awaiting_follow_up_authorization
        current_app.logger.warning(f"Bot_reply vacío y acción no es de espera: {accion_detectada}. Enviando respuesta genérica.")
        bot_reply = "Hmm, algo salió mal. ¿Puedes intentar de nuevo?"
    
    current_app.logger.info(f"[CHAT_INTERACTION] Sucre: {bot_reply[:150]}...") # Log de la respuesta del bot
    current_app.logger.debug(f"DEBUG: Acción final: {accion_detectada} | Respuesta: {bot_reply[:150]}...")
    return jsonify({"reply": bot_reply})


@chat_bp.route('/reports/<filename>')
@login_required
def download_report(filename):
    print(f"DEBUG: Solicitud de descarga para {filename}")
    reports_folder_abs = current_app.config['REPORTS_FOLDER']
    try:
        if '..' in filename or filename.startswith('/'):
            raise ValueError("Nombre de archivo inválido.")
        print(f"DEBUG: Sirviendo desde directorio: {reports_folder_abs}")
        return send_from_directory(reports_folder_abs, filename, as_attachment=True)
    except FileNotFoundError:
        print(f"ERROR: Archivo de reporte no encontrado: {filename} en {reports_folder_abs}")
        flash("El archivo del reporte solicitado no fue encontrado.", "danger")
        return redirect(url_for('chat.chat_route'))
    except ValueError as ve:
        print(f"ERROR: Intento de acceso inválido a reporte: {filename} - {ve}")
        flash("Nombre de archivo inválido.", "danger")
        return redirect(url_for('chat.chat_route'))
    except Exception as e:
        print(f"ERROR: Error desconocido al descargar reporte {filename}: {e}")
        traceback.print_exc()
        flash("Ocurrió un error al intentar descargar el reporte.", "danger")
        return redirect(url_for('chat.chat_route'))
