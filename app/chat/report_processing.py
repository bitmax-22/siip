# c:\Users\Administrator\Desktop\SIIP\app\chat\report_processing.py
import pandas as pd
import re
import json
import time
from datetime import date, timedelta
from flask import url_for, current_app # Import current_app para el logger

from ..reports import generar_reporte_pdf
from ..utils import format_value_for_display # Asegúrate que esta función esté disponible o pásala como argumento

MAPA_COLUMNAS_REPORTE = {
    'cedula': 'CEDULA', 'cédula': 'CEDULA', 'cedulas': 'CEDULA', 'region': 'REGION',
    'establecimiento penalitario': 'ESTABLECIMIENTO PENITENCIARIO', 'expediente interno': 'EXPEDIENTE INTERNO',
    'cedula laminada': 'CEDULA LAMINADA', 'nombre': 'NOMBRES Y APELLIDOS', 'nombres': 'NOMBRES Y APELLIDOS',
    'apellido': 'NOMBRES Y APELLIDOS', 'nombres y apellidos': 'NOMBRES Y APELLIDOS',
    'nombre completo': 'NOMBRES Y APELLIDOS', 'edad': 'EDAD', 'delito': 'DELITO CON MAYOR GRAVEDAD',
    'delito expediente': 'DELITO DE EXPEDIENTE', 'pena': 'TIEMPO DE PENA', 'tiempo de pena': 'TIEMPO DE PENA',
    'circuito': 'CIRCUITO JUDICIAL', 'extension': 'EXTENSION', 'numero de tribunal': 'NUMERO DE TRIBUNAL',
    'nº de tribunal': 'NUMERO DE TRIBUNAL', 'nro de tribunal': 'NUMERO DE TRIBUNAL',
    'circuito judicial': 'CIRCUITO JUDICIAL', 'condicion juridica': 'CONDICION JURIDICA',
    'condición jurídica': 'CONDICION JURIDICA', 'fase del proceso': 'FASE DEL PROCESO',
    'fase proceso': 'FASE DEL PROCESO', 'penado': 'CONDICION JURIDICA=PENADO',
    'penados': 'CONDICION JURIDICA=PENADO', 'procesado': 'CONDICION JURIDICA=PROCESADO',
    'procesados': 'CONDICION JURIDICA=PROCESADO', 'control': 'FASE DEL PROCESO=CONTROL',
    'juicio': 'FASE DEL PROCESO=JUICIO', 'ejecucion': 'FASE DEL PROCESO=EJECUCION',
    'corte de apelaciones': 'FASE DEL PROCESO=CORTE DE APELACIONES', 'numero de expediente': 'NUMERO DE EXPEDIENTE',
    'numero expediente': 'NUMERO DE EXPEDIENTE', 'expediente': 'NUMERO DE EXPEDIENTE',
    'tiempo fisico': 'TIEMPO FISICO', 'tiempo fisicamente': 'TIEMPO FISICO',
    'redenciones': 'REDENCIONES COMPUTADAS', 'redenciones computadas': 'REDENCIONES COMPUTADAS',
    'redenciones sin computar': 'REDENCIONES SIN COMPUTAR', 'beneficio al cual opta': 'BENEFICIO AL CUAL OPTA',
    'tipo de droga': 'TIPO DE DROGA', 'droga': 'TIPO DE DROGA', 'cantidad de droga': 'CANTIDAD DE DROGA',
    'fecha nacimiento': 'FECHA DE NACIMIENTO', 'nacionalidad': 'NACIONALIDAD', 'pais de origen': 'PAIS DE ORIGEN',
    'estado civil': 'ESTADO CIVIL', 'nivel academico': 'NIVEL ACADEMICO', 'oficio': 'OFICIO',
    'fecha en boleta de encarcelacion': 'FECHA EN BOLETA DE ENCARCELACION',
    'fecha de boleta de encarcelacion': 'FECHA EN BOLETA DE ENCARCELACION',
    'numero de boleta de encarcelacion': 'Nº DE BOLETA DE ENCARCELACION',
    'nº en boleta de encarcelacion': 'Nº DE BOLETA DE ENCARCELACION', 'fecha de ingreso': 'FECHA DE INGRESO',
    'fecha ingreso': 'FECHA DE INGRESO', 'fecha de cumprimento de pena': 'FECHA DE CUMPLIMIENTO DE PENA',
    'fecha cumprimento de pena': 'FECHA DE CUMPLIMIENTO DE PENA', 'fecha psicosocial': 'FECHA PSICOSOCIAL',
    'fecha de psicosocial': 'FECHA PSICOSOCIAL', 'procedencia': 'PROCEDENCIA',
    'ruta penitenciaria': 'RUTA PENITENCIARIA', 'ruta': 'RUTA PENITENCIARIA',
    'motivo de ingreso': 'MOTIVO DE INGRESO', 'indice delictivo': 'INDICE DELICTIVO',
    'indice': 'INDICE DELICTIVO', 'ubicacion': 'UBICACION', 'ubicación': 'UBICACION',
    'establecimiento': 'ESTABLECIMIENTO PENITENCIARIO', 'region': 'REGION', 'región': 'REGION',
    'sexo': 'SEXO', 'estatus': 'ESTATUS', 'lugar de nacimiento': 'LUGAR DE NACIMIENTO',
    'fecha de nacimiento': 'FECHA DE NACIMIENTO', 'motivo ingreso': 'MOTIVO DE INGRESO',
    'fecha de detencion': 'FECHA DE DETENCION', 'fecha detencion': 'FECHA DE DETENCION',
    'fecha detención': 'FECHA DE DETENCION','celda':'CELDA'
}


def _parsear_tiempo_pena_a_anos(texto_pena):
    """
    Convierte una cadena de texto como "09 AÑOS 04 MESES 00 DIAS" a un valor numérico de años.
    Retorna None si el formato no es parseable o la pena es indeterminada.
    """
    if pd.isna(texto_pena) or not isinstance(texto_pena, str):
        return None

    texto_pena_upper = texto_pena.upper()
    
    anos = 0
    match_anos = re.search(r'(\d+)\s*AÑO', texto_pena_upper) # AÑO o AÑOS
    if match_anos: anos = int(match_anos.group(1))

    match_meses = re.search(r'(\d+)\s*MES', texto_pena_upper) # MES o MESES
    if match_meses: anos += int(match_meses.group(1)) / 12

    # Los días suelen tener un impacto menor en comparaciones de años, pero se pueden añadir si es necesario.
    return anos if (match_anos or match_meses) else None


def _aplicar_filtro_numerico_operacional(df_original, columna_nombre, operador, valor_filtro_str):
    """
    Aplica un filtro numérico operacional (ej. >, <, ==) a una columna del DataFrame.
    Maneja el parseo especial para 'TIEMPO DE PENA'.
    Retorna (DataFrame_filtrado, criterio_aplicado_str).
    Si hay error, retorna (DataFrame_original, mensaje_de_error_como_criterio).
    """
    logger = current_app.logger
    df = df_original.copy()

    try:
        numeric_value_to_compare = pd.to_numeric(valor_filtro_str)
        if pd.isna(numeric_value_to_compare):
            raise ValueError(f"El valor del filtro '{valor_filtro_str}' para la columna '{columna_nombre}' no es numérico.")

        # Normalizar el valor de comparación si es una columna de porcentaje y el valor es > 1
        columnas_de_porcentaje = [
            "PORCENTAJE FISICO CUMPLIDO", "PORCENTAJE CUMPLIDO CON REDENCION",
            "% CUMPLIMIENTO SIN REDENCION", "%\n CUMPLIMIENTO CON REDENCION" # Nombres exactos de data_loader
        ]
        if columna_nombre in columnas_de_porcentaje and numeric_value_to_compare > 1:
            numeric_value_to_compare /= 100
            logger.debug(f"DEBUG: Valor de filtro para columna de porcentaje '{columna_nombre}' normalizado a {numeric_value_to_compare}")

        if columna_nombre == "TIEMPO DE PENA":
            source_series_for_comparison = df[columna_nombre].apply(_parsear_tiempo_pena_a_anos)
        else:
            source_series_for_comparison = pd.to_numeric(df[columna_nombre], errors='coerce')

        if operador == '<': mask = source_series_for_comparison < numeric_value_to_compare
        elif operador == '>': mask = source_series_for_comparison > numeric_value_to_compare
        elif operador == '<=': mask = source_series_for_comparison <= numeric_value_to_compare
        elif operador == '>=': mask = source_series_for_comparison >= numeric_value_to_compare
        elif operador == '==' or operador == '=': mask = source_series_for_comparison == numeric_value_to_compare
        else:
            logger.warning(f"Operador numérico no reconocido '{operador}' para columna {columna_nombre}. No se aplicó filtro.")
            return df_original, f"Operador '{operador}' no reconocido para {columna_nombre}"
        
        df_filtrado_final = df[mask.fillna(False)]
        
        op_display = operador.replace("==", "=")
        criterio_str = f"{columna_nombre} {op_display} {numeric_value_to_compare}"
        if columna_nombre == "TIEMPO DE PENA": criterio_str += " años"
        
        return df_filtrado_final, criterio_str
    except Exception as e:
        logger.warning(f"No se pudo aplicar filtro numérico operacional para {columna_nombre} con valor '{valor_filtro_str}' y op '{operador}': {e}")
        return df_original, f"Error procesando filtro numérico para {columna_nombre} (valor: {valor_filtro_str}, op: {operador})"


def _build_report_nlu_prompt(user_message, datos_siip_columns):
    column_info = ", ".join(datos_siip_columns)
    mapa_str = "\n".join([f"- '{k}' se refiere a la columna '{v}'" for k, v in MAPA_COLUMNAS_REPORTE.items()])
    return f"""
Eres un asistente experto **únicamente** en analizar solicitudes de reportes para el sistema SIIP. Tu única tarea es extraer filtros y columnas de la solicitud del usuario para generar un reporte SIIP. No realices ninguna otra acción.

Columnas disponibles en la base de datos:
{column_info}

Guía de mapeo de palabras comunes a columnas (usa los nombres EXACTOS de las columnas disponibles):
{mapa_str}

Consideraciones especiales para filtros:
- Si el usuario dice "penado" o "penados", el filtro es {{ "CONDICION JURIDICA": "PENADO" }}.
- Si el usuario dice "procesado" o "procesados", el filtro es {{ "CONDICION JURIDICA": "PROCESADO" }}.
- Si menciona una fase como "control", "juicio", "ejecucion", "corte de apelaciones", el filtro es sobre la columna "FASE DEL PROCESO".
- Si dice "droga" sin especificar tipo, y parece un filtro (ej. "que tengan droga"), usa {{ "TIPO DE DROGA": "NO VACIO" }}. Si dice "delito droga", el filtro es {{ "DELITO CON MAYOR GRAVEDAD": "droga" }} (buscando que contenga 'droga').
- Si menciona una ubicación específica como "observacion", el filtro es {{ "UBICACION": "OBSERVACION" }}.
- Si menciona un año (ej. "nacidos en 1990"), el filtro es sobre el año de "FECHA DE NACIMIENTO".
- **Importante para Ubicaciones/Tribunales:** Si menciona un estado de Venezuela (ej. "Miranda", "Carabobo", "Zulia") o "tribunal" seguido de un nombre, filtra por "CIRCUITO JUDICIAL" o "NUMERO DE TRIBUNAL", **NO** por "REGION". "REGION" es para zonas amplias (CENTRAL, OCCIDENTAL, etc.).
- **Fechas:** Si pide un rango explícito (ej. 'desde X hasta Y', 'durante el mes de abril'), devuelve el filtro como {{ "NOMBRE_COLUMNA": {{ "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD" }} }}. Si solo es una fecha, usa el valor simple 'YYYY-MM-DD'. **Si dice "desde [fecha/mes/año]" (o similar, como "a partir de") sin fecha final explícita, usa esa fecha como `start_date` y la fecha de HOY ({date.today().strftime('%Y-%m-%d')}) como `end_date`.**
- **Tipos de Tribunal (VCM, etc.):** Si el usuario menciona "VCM", "VCC", "VCEJ" o similares, interpreta esto como un filtro para la columna `NUMERO DE TRIBUNAL` que debe contener ese acrónimo. Ejemplo: "tribunal VCM" -> {{ "NUMERO DE TRIBUNAL": "VCM" }}.
- **Violencia (VCM):** Si el usuario menciona "violencia" o "violencia contra la mujer", interpreta esto como un filtro para la columna `NUMERO DE TRIBUNAL` que debe contener "VCM". Ejemplo: "casos de violencia" -> {{ "NUMERO DE TRIBUNAL": "VCM" }}.
- **Límites:** Si pide 'últimos N' o 'primeros N', añade una clave "limite": N al JSON principal.
- **Comparaciones Numéricas (ej. Tiempo de Pena):** Para frases como "menos de 5 años" o "mayor a 10 años" referidas a columnas numéricas como `TIEMPO DE PENA`, el filtro debe ser un diccionario: `{{"op": "<operador>", "valor": <numero>}}`. Operadores válidos: `<`, `>`, `<=`, `>=`, `==`. Ejemplo: "penas de menos de 5 años" -> `{{"TIEMPO DE PENA": {{"op": "<", "valor": 5}}}}`. Asegúrate de que el `valor` sea solo el número.
- **Año Actual:** Si el usuario pide "este año", "año actual", "en {date.today().year}", filtra la columna de fecha relevante (usualmente `FECHA DE INGRESO`) para que el año coincida con el año en curso ({date.today().year}). Ejemplo: si hoy es 2025, "este año" significa filtrar por año 2025.
- **Columnas relacionadas:** Si el usuario pregunta 'qué tribunal lleva el caso', 'especifícame el tribunal' o similar, asegúrate de incluir las columnas `NUMERO DE TRIBUNAL`, `CIRCUITO JUDICIAL`, y `EXTENSION` en la lista de `columnas` además de las que ya estén por defecto o por filtros.


Solicitud del Usuario: "{user_message}"

Analiza la solicitud y responde ÚNICAMENTE con un objeto JSON válido que contenga:
1. "filtros": un diccionario {{ "NOMBRE_COLUMNA_EXACTA": valor_o_rango }}. Vacío {{}} si no hay filtros.
2. "columnas": una lista de nombres EXACTOS de columnas a mostrar. Si no especifica, incluye ['CEDULA', 'NOMBRES Y APELLIDOS'] más las columnas de los filtros. Valida que existan.
Opcionalmente:
3. "limite": un número entero si pide una cantidad específica.

Ejemplo para "hazme un reporte con los ultimos 10 privados que ingresaron en abril 2024, muestra cedula y fecha de ingreso":
{{
  "filtros": {{ "FECHA DE INGRESO": {{ "start_date": "2024-04-01", "end_date": "2024-04-30" }} }},
  "columnas": ["CEDULA", "FECHA DE INGRESO"],
  "limite": 10
}}
Ejemplo para "reporte de los que tengan más de 3 años de pena":
{{
  "filtros": {{ "TIEMPO DE PENA": {{ "op": ">", "valor": 3 }} }},
  "columnas": ["CEDULA", "NOMBRES Y APELLIDOS", "TIEMPO DE PENA"]
}}

JSON de respuesta:
"""

def _generar_titulo_descriptivo_con_gemini(user_message, filtros_aplicados_dict, gemini_model, logger):
    """
    Usa Gemini para generar un título descriptivo para el reporte PDF
    basado en el mensaje del usuario y los filtros aplicados.
    """
    filtros_str = json.dumps(filtros_aplicados_dict, ensure_ascii=False, default=str)
    prompt = f"""
Dada la siguiente solicitud original de un usuario para un reporte SIIP y los filtros técnicos que se aplicaron,
genera un título conciso y descriptivo para el reporte en PDF. El título debe ser legible, reflejar la intención principal
e integrar de forma natural las columnas principales solicitadas si se mencionan en la consulta.
Máximo 10-15 palabras. Evita usar la palabra "Reporte" a menos que sea la única forma de ser claro.
Si se piden columnas adicionales como 'ubicación', 'delito', 'establecimiento', intenta incorporarlas fluidamente en el título.

Solicitud del Usuario: "{user_message}"
Filtros Técnicos Aplicados (JSON): {filtros_str}

Ejemplos de Títulos Deseados:
- Para "reporte con el numero de tribunal, carabobo, extension y penas cumplidas 75% o mas con sus ubicaciones" -> "PDL de Carabobo con 75% o más de Pena Cumplida (Redención)"
- Para "generame un reporte de pdl con mas 5 años procesado con ubicacion" -> "PDL Procesados con más de 5 Años de Pena y sus Ubicaciones"
- Para "reporte de penados en el Tocuyito con su delito" -> "Penados en el Establecimiento Tocuyito y sus Delitos"
- Para "reporte de los privados de libertad del estado miranda" -> "Privados de Libertad del Estado Miranda"
- Para "dame una lista de los procesados en fase de control" -> "Procesados en Fase de Control"
- Para "reporte de los ultimos 10 ingresos" -> "Últimos 10 Ingresos al Sistema"

Título Descriptivo para el PDF:
"""
    try:
        response = gemini_model.generate_content(prompt)
        titulo = response.text.strip()
        logger.debug(f"DEBUG: Título descriptivo generado por Gemini: '{titulo}'")
        return titulo if titulo else None
    except Exception as e:
        logger.error(f"Error generando título descriptivo con Gemini: {e}")
        return None

def process_report_request(user_message, user_message_lower, datos_siip, gemini_model):
    bot_reply = ""
    accion_detectada = "reporte" # Initial assumption
    logger = current_app.logger # Get logger from current_app
    from collections import OrderedDict # Importar aquí para evitar importación global no usada en otros lados

    prompt_para_gemini_nlu = _build_report_nlu_prompt(user_message, datos_siip.columns)
    try:
        response = gemini_model.generate_content(prompt_para_gemini_nlu)
        respuesta_json_str = response.text.strip().lstrip('```json').rstrip('```').strip()
        logger.debug(f"DEBUG: Respuesta JSON cruda de Gemini NLU: {respuesta_json_str}")
        parsed_data = json.loads(respuesta_json_str)
        
        filtros_gemini = parsed_data.get("filtros", {})
        limite_gemini = parsed_data.get("limite")
        columnas_gemini_nlu = parsed_data.get("columnas", []) # Columnas sugeridas por NLU
        
        filtros_validados = {}
        for k, v in filtros_gemini.items():
            if k in datos_siip.columns:
                if isinstance(v, str) and v.upper() == "NO VACIO": filtros_validados[k] = pd.notna
                else: filtros_validados[k] = v
            else: logger.warning(f"ADVERTENCIA NLU: Columna de filtro inexistente '{k}'. Ignorando.")

        filtros = filtros_validados

        # Validar y registrar columnas sugeridas por NLU que no existen
        columnas_nlu_existentes_en_df = [col for col in columnas_gemini_nlu if col in datos_siip.columns]
        columnas_nlu_inexistentes = set(columnas_gemini_nlu) - set(columnas_nlu_existentes_en_df)
        if columnas_nlu_inexistentes:
            logger.warning(f"ADVERTENCIA NLU: Columnas inexistentes sugeridas por Gemini: {columnas_nlu_inexistentes}. Ignorando.")

        # Nueva lógica para el orden de columnas:
        columnas_base_fijas = ['NOMBRES Y APELLIDOS', 'CEDULA']
        columnas_base_validadas = [col for col in columnas_base_fijas if col in datos_siip.columns]

        columnas_pedidas_por_usuario_nlu_validas = [
            col for col in columnas_nlu_existentes_en_df if col not in columnas_base_validadas
        ]
        
        columnas_de_filtros_validadas = []
        for col_filtro in filtros.keys(): # Usar `filtros` (ya validados)
            if col_filtro in datos_siip.columns and \
               col_filtro not in columnas_base_validadas and \
               col_filtro not in columnas_pedidas_por_usuario_nlu_validas:
                columnas_de_filtros_validadas.append(col_filtro)
        
        columnas_deseadas_para_seleccion = columnas_base_validadas + columnas_pedidas_por_usuario_nlu_validas + columnas_de_filtros_validadas
        columnas_deseadas_para_seleccion = list(OrderedDict.fromkeys(columnas_deseadas_para_seleccion))

        limite_num = int(limite_gemini) if limite_gemini and str(limite_gemini).isdigit() else None

        logger.debug(f"DEBUG: Filtros NLU (Validados): {filtros}")
        logger.debug(f"DEBUG: Columnas Base (Validadas): {columnas_base_validadas}")
        logger.debug(f"DEBUG: Columnas Pedidas por Usuario (NLU válidas, sin base): {columnas_pedidas_por_usuario_nlu_validas}")
        logger.debug(f"DEBUG: Columnas de Filtros (validadas, sin base ni pedidas): {columnas_de_filtros_validadas}")
        logger.debug(f"DEBUG: Columnas Deseadas para Selección (ordenadas, antes de filtrar por resultados): {columnas_deseadas_para_seleccion}")
        logger.debug(f"DEBUG: Límite NLU: {limite_num}")

    except json.JSONDecodeError as json_err:
        logger.error(f"Error: Gemini NLU no devolvió JSON válido. Respuesta: {respuesta_json_str} | Error: {json_err}")
        bot_reply = "Lo siento, tuve problemas para entender la estructura de tu solicitud de reporte. ¿Puedes intentarlo de nuevo?"
        return bot_reply, "error_nlu"
    except Exception as gemini_nlu_err:
        logger.error(f"ERROR al llamar a Gemini para NLU: {gemini_nlu_err}")
        bot_reply = "Tuve un problema contactando a mi asistente IA para entender tu reporte. Intenta de nuevo."
        return bot_reply, "error_nlu"

    # Apply filters and generate report
    resultados_filtrados = datos_siip.copy()
    error_reporte = None

    # --- Aplicar filtro base de "dentro del sistema" si no se pide un ESTATUS específico ---
    # Esto asegura que los reportes generales operen sobre la población relevante.
    if not any(k.upper() == 'ESTATUS' for k in filtros.keys()):
        logger.debug("DEBUG: No se especificó filtro de ESTATUS. Aplicando filtro base 'dentro del sistema'.")
        estatus_dentro_del_sistema = [
            'ACTIVO', 'HOSPITALIZADO', 
            'INGRESO INTERPENAL', 'INGRESO COMISARIA',
            'TRASLADO' # Asegúrate que este estatus esté aquí si debe considerarse "dentro del sistema"
        ]
        # Crear una copia para no modificar el DataFrame original en la app.config
        resultados_filtrados = resultados_filtrados[
            resultados_filtrados['ESTATUS'].fillna('').str.upper().isin(estatus_dentro_del_sistema)
        ].copy()
        logger.debug(f"DEBUG: Registros después de filtro 'dentro del sistema': {len(resultados_filtrados)}")
    # --- Fin filtro base ---

    criterios_aplicados_str = []
    try:
        for col, val in filtros.items():
            criterio_valor_str = "" # Inicializar para cada filtro

            # Filtro 1: Operación numérica estructurada (ej. {"op": ">", "valor": 5})
            if isinstance(val, dict) and 'op' in val and 'valor' in val:
                resultados_filtrados, criterio_valor_str = _aplicar_filtro_numerico_operacional(
                    resultados_filtrados, col, val['op'], str(val['valor'])
                )
            # Filtro 2: "NO VACIO"
            elif val is pd.notna:
                resultados_filtrados = resultados_filtrados[resultados_filtrados[col].notna()]
                criterio_valor_str = f"{col} NO VACIO"
            # Filtro 3: Rango de fechas (ej. {"start_date": "...", "end_date": "..."})
            elif isinstance(val, dict) and 'start_date' in val and 'end_date' in val:
                start = pd.to_datetime(val['start_date'], errors='coerce')
                end = pd.to_datetime(val['end_date'], errors='coerce')
                criterio_valor_str = f"{col} entre {format_value_for_display(start)} y {format_value_for_display(end)}"
                col_datetime_series = pd.to_datetime(resultados_filtrados[col], errors='coerce')
                if pd.notna(start): resultados_filtrados = resultados_filtrados[col_datetime_series >= start]
                if pd.notna(end): resultados_filtrados = resultados_filtrados[col_datetime_series < end + pd.Timedelta(days=1)]
            # Filtro 4: Fecha/año específico (si la columna del DF es de tipo datetime)
            elif pd.api.types.is_datetime64_any_dtype(resultados_filtrados[col]):
                if isinstance(val, int) and 1900 < val < 2100: # Year filter
                    resultados_filtrados = resultados_filtrados[resultados_filtrados[col].dt.year == val]
                    criterio_valor_str = f"{col} año {val}"
                else: # Specific date
                    fecha_dt = pd.to_datetime(val, errors='coerce')
                    if pd.notna(fecha_dt):
                        resultados_filtrados = resultados_filtrados[resultados_filtrados[col].dt.date == fecha_dt.date()]
                        criterio_valor_str = f"{col} = {format_value_for_display(fecha_dt)}"
                    else:
                        raise ValueError(f"Fecha inválida '{val}' para columna {col}")
            # Filtro 5: Igualdad numérica simple (si la columna del DF es numérica y 'val' es un número simple)
            elif pd.api.types.is_numeric_dtype(resultados_filtrados[col]):
                val_num = pd.to_numeric(val, errors='coerce')
                if pd.notna(val_num):
                    resultados_filtrados = resultados_filtrados[resultados_filtrados[col] == val_num]
                    criterio_valor_str = f"{col} = {val_num}"
                else:
                    logger.warning(f"Se esperaba valor numérico para {col} pero se recibió '{val}'. Se intentará como texto si no se manejó antes.")
            
            # Filtro 6: Fallback a búsqueda de texto si no se aplicó otro filtro
            if not criterio_valor_str:
                if not isinstance(val, dict): # Si 'val' no es un diccionario (es un valor simple)
                    resultados_filtrados = resultados_filtrados[resultados_filtrados[col].astype(str).str.contains(str(val), case=False, na=False)]
                    criterio_valor_str = f"{col} contiene '{str(val)}'"
                else: # Si 'val' es un diccionario pero no uno de los tipos conocidos
                    logger.warning(f"Tipo de filtro de diccionario no reconocido para {col}: {val}. No se aplicó filtro.")
                    criterio_valor_str = f"Filtro complejo no aplicado para {col} (valor: {str(val)[:50]}...)"

            if criterio_valor_str: criterios_aplicados_str.append(criterio_valor_str)
        
        # --- Lógica de Ordenamiento y Límite --- #
        columna_orden_primario = None
        orden_primario_asc = False # Por defecto, si es numérico, será descendente. Si es texto, será ascendente.

        # 1. Prioridad: Filtros numéricos operacionales (orden descendente)
        for col_filtro, val_filtro in filtros.items():
            if isinstance(val_filtro, dict) and 'op' in val_filtro and 'valor' in val_filtro:
                columna_orden_primario = col_filtro
                orden_primario_asc = False # Mayor a Menor
                logger.debug(f"DEBUG: Ordenamiento por filtro numérico: '{col_filtro}' (Descendente)")
                break
        
        # 2. Prioridad media: Filtro por UBICACION (orden ascendente A-Z)
        # Esto se aplica si no hubo un filtro numérico que ya haya definido el orden.
        if not columna_orden_primario:
            if "UBICACION" in filtros:
                val_filtro_ubicacion = filtros["UBICACION"]
                # Asegurarse que el filtro de ubicación sea simple (un string) y no uno complejo
                # como "NO VACIO" o un rango de fechas (aunque no aplicaría a UBICACION).
                if isinstance(val_filtro_ubicacion, str) and val_filtro_ubicacion.strip() != "":
                    columna_orden_primario = "UBICACION"
                    orden_primario_asc = True # A-Z
                    logger.debug(f"DEBUG: Ordenamiento por filtro específico de UBICACION (Ascendente A-Z)")

        # 3. Prioridad media-baja: Filtro por CELDA (orden ascendente A-Z)
        # Esto se aplica si no hubo un filtro numérico ni por UBICACION que ya haya definido el orden.
        if not columna_orden_primario:
            if "CELDA" in filtros:
                val_filtro_celda = filtros["CELDA"]
                # Asegurarse que el filtro de celda sea simple (un string) y no uno complejo
                if isinstance(val_filtro_celda, str) and val_filtro_celda.strip() != "":
                    columna_orden_primario = "CELDA"
                    orden_primario_asc = True # Ascendente (numéricamente si es posible, sino A-Z)
                    logger.debug(f"DEBUG: Ordenamiento por filtro específico de CELDA (Ascendente)")

        # 4. Prioridad baja: Otros filtros de texto (orden ascendente A-Z)
        # Esto se aplica si no hubo un filtro numérico, ni por UBICACION, ni por CELDA que definiera el orden.
        if not columna_orden_primario:
            for col_filtro, val_filtro in filtros.items():
                # Considerar filtro de texto si no es "NO VACIO", ni rango de fechas, ni numérico operacional
                if not (val_filtro is pd.notna or \
                        (isinstance(val_filtro, dict) and ('start_date' in val_filtro or 'op' in val_filtro))):
                    columna_orden_primario = col_filtro
                    orden_primario_asc = True # A-Z
                    logger.debug(f"DEBUG: Ordenamiento por filtro de texto genérico: '{col_filtro}' (Ascendente A-Z)")
                    break # Usar el primer filtro de texto encontrado

        columnas_de_porcentaje_para_orden = [
            "PORCENTAJE FISICO CUMPLIDO", "PORCENTAJE CUMPLIDO CON REDENCION",
            "% CUMPLIMIENTO SIN REDENCION", "%\n CUMPLIMIENTO CON REDENCION"
        ]

        # Bandera para saber si el ordenamiento secundario por CELDA se aplicó
        _orden_secundario_celda_aplicado = False


        # Aplicar ordenamiento primario si se determinó una columna
        if columna_orden_primario and columna_orden_primario in resultados_filtrados.columns:
            try:
                if columna_orden_primario == "TIEMPO DE PENA":
                    temp_sort_col = columna_orden_primario + "_sort_val_prim"
                    resultados_filtrados[temp_sort_col] = resultados_filtrados[columna_orden_primario].apply(_parsear_tiempo_pena_a_anos)
                    resultados_filtrados = resultados_filtrados.sort_values(by=temp_sort_col, ascending=orden_primario_asc, na_position='last')
                    resultados_filtrados = resultados_filtrados.drop(columns=[temp_sort_col], errors='ignore') # type: ignore
                # Ordenamiento para columnas de texto (A-Z)
                elif orden_primario_asc and columna_orden_primario not in columnas_de_porcentaje_para_orden:
                    # Esta rama maneja UBICACION y CELDA como primarios, y otros textos A-Z
                    
                    current_sort_by_cols = [columna_orden_primario]
                    current_ascending_flags = [True] # orden_primario_asc es True aquí
                    
                    if columna_orden_primario == "UBICACION" and "CELDA" in resultados_filtrados.columns:
                        current_sort_by_cols.append("CELDA")
                        current_ascending_flags.append(True) # CELDA también A-Z
                        _orden_secundario_celda_aplicado = True # Marcar que se usará orden secundario
                        logger.debug(f"DEBUG: Ordenamiento secundario por CELDA (A-Z) configurado para UBICACION.")

                    if _orden_secundario_celda_aplicado: # Caso UBICACION y CELDA
                        df_temp_sort = resultados_filtrados.copy()
                        temp_sort_col_names_for_by = []
                        # Crear columnas temporales para ordenamiento insensible a mayúsculas/minúsculas
                        for i, col_name_to_sort in enumerate(current_sort_by_cols):
                            # Sanitize temp column name in case original col name has special chars
                            safe_col_name_part = re.sub(r'\W+', '_', col_name_to_sort)
                            temp_key_col_name = f"__sort_key_{i}_{safe_col_name_part}"
                            
                            if col_name_to_sort == "CELDA":
                                # Para CELDA como secundaria, intentar conversión numérica para su clave de ordenamiento
                                numeric_celda_series = pd.to_numeric(df_temp_sort[col_name_to_sort], errors='coerce')
                                # Si todos los valores que no son NaN pueden convertirse a numéricos, usar eso.
                                # Esto maneja casos donde CELDA podría ser mixta o tener NaNs.
                                # Usamos la serie numérica si una porción significativa es numérica, sino string.
                                # Una comprobación simple: si todos los no-NaN son numéricos, tratar como numérico.
                                if numeric_celda_series.notna().sum() > 0 and numeric_celda_series[numeric_celda_series.notna()].isna().sum() == 0:
                                    df_temp_sort[temp_key_col_name] = numeric_celda_series
                                else: # Fallback a ordenamiento de string para CELDA si no es puramente numérica o está vacía
                                    df_temp_sort[temp_key_col_name] = df_temp_sort[col_name_to_sort].astype(str).str.lower()
                            elif pd.api.types.is_string_dtype(df_temp_sort[col_name_to_sort]) or df_temp_sort[col_name_to_sort].dtype == 'object':
                                df_temp_sort[temp_key_col_name] = df_temp_sort[col_name_to_sort].astype(str).str.lower()
                            else:
                                df_temp_sort[temp_key_col_name] = df_temp_sort[col_name_to_sort]
                            temp_sort_col_names_for_by.append(temp_key_col_name)
                        
                        df_temp_sort = df_temp_sort.sort_values(
                            by=temp_sort_col_names_for_by,
                            ascending=current_ascending_flags,
                            na_position='last'
                        )
                        resultados_filtrados = df_temp_sort.drop(columns=temp_sort_col_names_for_by, errors='ignore')
                    elif columna_orden_primario == "CELDA": # Ordenamiento específico para CELDA como columna primaria
                        # Intentar ordenamiento numérico para CELDA, fallback a texto si falla o es mixta.
                        # Crear una serie temporal para ordenar para manejar errores potenciales y tipos mixtos
                        # Asegurar que estamos trabajando con una Serie para to_numeric
                        celda_series_to_sort = resultados_filtrados[columna_orden_primario]
                        if not isinstance(celda_series_to_sort, pd.Series):
                            celda_series_to_sort = pd.Series(celda_series_to_sort)

                        temp_celda_numeric = pd.to_numeric(celda_series_to_sort, errors='coerce')

                        # Si todos los valores no-NaN son numéricos, ordenar numéricamente. Sino, ordenar como texto.
                        if temp_celda_numeric.notna().sum() > 0 and temp_celda_numeric[temp_celda_numeric.notna()].isna().sum() == 0:
                            logger.debug(f"DEBUG: Ordenando CELDA numéricamente (ascendente: {orden_primario_asc}).")
                            # Necesidad de manejar alineación de índice si temp_celda_numeric es solo un array numpy de una lista
                            df_temp_celda_sort = resultados_filtrados.copy()
                            df_temp_celda_sort["__celda_sort_val__"] = temp_celda_numeric
                            df_temp_celda_sort = df_temp_celda_sort.sort_values(
                                by="__celda_sort_val__",
                                ascending=orden_primario_asc, # True para CELDA
                                na_position='last'
                            )
                            resultados_filtrados = df_temp_celda_sort.drop(columns=["__celda_sort_val__"])
                        else:
                            logger.debug(f"DEBUG: CELDA no es puramente numérica o está vacía. Ordenando como texto A-Z.")
                            resultados_filtrados = resultados_filtrados.sort_values(
                                by=columna_orden_primario,
                                ascending=True, # orden_primario_asc es True
                                na_position='last',
                                key=lambda col_series: col_series.astype(str).str.lower()
                            )
                    else: # Ordenamiento por una sola columna de texto (que no es CELDA)
                        resultados_filtrados = resultados_filtrados.sort_values(
                            by=columna_orden_primario, 
                            ascending=True, # orden_primario_asc es True
                            na_position='last',
                            key=lambda col_series: col_series.astype(str).str.lower() if pd.api.types.is_string_dtype(col_series) or col_series.dtype == 'object' else col_series
                        )
                else: # Ordenamiento para porcentajes u otras columnas numéricas
                    # (orden_primario_asc puede ser True o False aquí, dependiendo de si es un porcentaje ordenado A-Z o un numérico descendente)
                    col_to_sort_numeric = pd.to_numeric(resultados_filtrados[columna_orden_primario], errors='coerce')
                    if not col_to_sort_numeric.empty and col_to_sort_numeric.notna().any():
                        df_temp_sort = resultados_filtrados.copy()
                        df_temp_sort['_sort_col_temp_prim_'] = col_to_sort_numeric
                        df_temp_sort = df_temp_sort.sort_values(by='_sort_col_temp_prim_', ascending=orden_primario_asc, na_position='last')
                        resultados_filtrados = df_temp_sort.drop(columns=['_sort_col_temp_prim_'], errors='ignore') # type: ignore
                    else: # Fallback si la conversión a numérico falla y no era texto
                        logger.warning(f"Columna de orden '{columna_orden_primario}' no pudo ser ordenada numéricamente. Intentando como texto si es ascendente.")
                        if orden_primario_asc: # Si se esperaba A-Z pero falló la conversión numérica (ej. columna mixta)
                             resultados_filtrados = resultados_filtrados.sort_values(by=columna_orden_primario, ascending=True, na_position='last', key=lambda col: col.astype(str).str.lower())
                        else: # No se pudo ordenar numéricamente y no era A-Z
                            columna_orden_primario = None # Resetear si no se pudo ordenar

            except Exception as e_sort_prim:
                logger.error(f"Error al aplicar ordenamiento primario por '{columna_orden_primario}': {e_sort_prim}")
                columna_orden_primario = None # Resetear en caso de error
                _orden_secundario_celda_aplicado = False # Resetear también

        # Añadir mensaje de ordenamiento a los criterios
        if columna_orden_primario: # Solo si el ordenamiento no falló y reseteó la columna
            if _orden_secundario_celda_aplicado: # Implica que columna_orden_primario es UBICACION
                criterios_aplicados_str.append(f"Ordenado por UBICACION (A-Z), luego por CELDA (A-Z)")
            else:
                orden_desc_str = "A-Z" if orden_primario_asc else "Mayor a Menor"
                criterios_aplicados_str.append(f"Ordenado por {columna_orden_primario} ({orden_desc_str})")
        # Aplicar límite si existe
        if limite_num is not None:
            if not columna_orden_primario: # Si no hubo un ordenamiento primario por filtro, y hay límite, usar FECHA DE INGRESO
                col_orden_limite = 'FECHA DE INGRESO'
                if col_orden_limite in resultados_filtrados.columns:
                    try:
                        # Asegurar que la columna de orden exista y sea convertible a datetime
                        resultados_filtrados[col_orden_limite] = pd.to_datetime(resultados_filtrados[col_orden_limite], errors='coerce')
                        resultados_filtrados = resultados_filtrados.sort_values(by=col_orden_limite, ascending=False, na_position='last')
                        criterios_aplicados_str.append(f"Ordenado por {col_orden_limite} (Más Recientes Primero) para límite")
                    except Exception as e_limit_sort_default:
                        logger.warning(f"Error al ordenar por '{col_orden_limite}' para límite: {e_limit_sort_default}. Límite sin orden específico.")
                else:
                    logger.warning(f"Columna '{col_orden_limite}' no disponible para ordenar por límite. Límite sin orden específico.")
            
            # Aplicar el head(limite_num) después de cualquier ordenamiento
            resultados_filtrados = resultados_filtrados.head(limite_num)
            criterios_aplicados_str.append(f"Mostrando los primeros {limite_num} registros")
        # --- Fin Lógica de Ordenamiento y Límite ---

    except KeyError as ke: error_reporte = f"Columna de filtro '{ke}' no existe."; accion_detectada = "error_reporte"
    except ValueError as ve: error_reporte = f"Valor inválido para filtro: {ve}"; accion_detectada = "error_reporte"
    except Exception as filter_err: error_reporte = f"Error aplicando filtros: {filter_err}"; accion_detectada = "error_reporte"; logger.error(f"ERROR: {error_reporte}", exc_info=True)

    if accion_detectada == "error_reporte":
        bot_reply = f"No pude generar el reporte. Razón: {error_reporte}"
        return bot_reply, accion_detectada

    # Generate PDF and response
    try:
        # `columnas_deseadas_para_seleccion` ya tiene el orden preferido.
        # Ahora filtramos estas por las que existen en `resultados_filtrados`.
        columnas_finales_para_reporte = [col for col in columnas_deseadas_para_seleccion if col in resultados_filtrados.columns]

        # Si se aplicó un límite y el ordenamiento por defecto para el límite fue FECHA DE INGRESO
        # y esta columna no está ya en el reporte, añadirla.
        if limite_num is not None and not columna_orden_primario and \
           'FECHA DE INGRESO' in datos_siip.columns and \
           'FECHA DE INGRESO' not in columnas_finales_para_reporte and \
           'FECHA DE INGRESO' in resultados_filtrados.columns:
            columnas_finales_para_reporte.append('FECHA DE INGRESO')
            logger.debug("DEBUG: 'FECHA DE INGRESO' añadida a columnas del reporte debido al límite y orden por defecto.")

        # Fallback si columnas_finales_para_reporte está vacía pero hay resultados
        if not columnas_finales_para_reporte and not resultados_filtrados.empty:
            logger.debug("DEBUG: columnas_finales_para_reporte vacía, intentando fallback.")
            columnas_fallback = [col for col in columnas_base_validadas if col in resultados_filtrados.columns]
            if not columnas_fallback:
                logger.debug("DEBUG: Fallback con columnas base falló, tomando primeras N de resultados.")
                columnas_fallback = list(resultados_filtrados.columns[:3]) # Tomar hasta 3 como ejemplo
            columnas_finales_para_reporte = columnas_fallback
            logger.debug(f"DEBUG: Columnas de fallback seleccionadas: {columnas_finales_para_reporte}")

        if not columnas_finales_para_reporte and not resultados_filtrados.empty:
            logger.error("ERROR: No se pudieron determinar columnas para el reporte a pesar de haber resultados.")
            raise KeyError("No se pudieron determinar columnas para el reporte a pesar de haber resultados.")
        
        df_reporte = pd.DataFrame() 
        if not resultados_filtrados.empty and columnas_finales_para_reporte:
             df_reporte = resultados_filtrados[columnas_finales_para_reporte].copy()
        elif resultados_filtrados.empty:
            logger.debug("DEBUG: resultados_filtrados está vacío. El reporte estará vacío.")
        elif not columnas_finales_para_reporte: # Implica resultados_filtrados no vacío pero no se pudieron determinar columnas
            logger.warning("ADVERTENCIA: resultados_filtrados no vacío, pero no se pudieron determinar columnas. Reporte estará vacío.")

        if not df_reporte.empty:
            df_reporte.insert(0, '#', range(1, len(df_reporte) + 1))
        
        criterio_desc = ", ".join(criterios_aplicados_str) if criterios_aplicados_str else "Todos"

        # --- Generar título descriptivo para el PDF ---
        # Usar Gemini para generar el título descriptivo
        titulo_descriptivo_pdf = _generar_titulo_descriptivo_con_gemini(
            user_message, # La solicitud original del usuario
            filtros,      # Los filtros que realmente se aplicaron
            gemini_model,
            logger
        )

        if not titulo_descriptivo_pdf: # Fallback si Gemini no devuelve un título o hay error
            logger.warning("ADVERTENCIA: No se pudo generar título descriptivo con Gemini. Usando fallback.")
            titulo_descriptivo_pdf = "Reporte SIIP" # Default
            # Fallback a una versión más corta de criterios si no se pudo generar uno descriptivo
            if criterio_desc != "Todos":
                titulo_descriptivo_pdf = f"Reporte: {criterio_desc[:70]}"
                if len(criterio_desc) > 70: titulo_descriptivo_pdf += "..."
        # --- Fin de generar título descriptivo ---
        
        if 'cuantos' in user_message_lower: # Check if user asked for a count
            count = len(df_reporte)
            if criterios_aplicados_str: # Si hubo al menos un criterio aplicado
                bot_reply = f"Hay {count} registros que cumplen con: {criterio_desc}."
            else: # Si no se aplicaron filtros (ej. "cuantos registros hay en total")
                bot_reply = f"Hay un total de {count} registros en el sistema."
        elif not df_reporte.empty:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            base_parts = [re.sub(r'[^\w\-]+', '', str(v)) for k, v in filtros.items() if isinstance(v, (str, int))]
            if limite_num: base_parts.append(f"ultimos{limite_num}")
            nombre_base = "_".join(base_parts)[:40] if base_parts else "general"
            pdf_filename = f"reporte_{nombre_base}_{timestamp}.pdf" # Nombre del archivo sigue igual
            # Usar el nuevo título descriptivo para el PDF
            titulo_pdf_interno = f"Reporte SIIP: {titulo_descriptivo_pdf}" 
            
            generar_reporte_pdf(df_reporte, titulo_pdf_interno, pdf_filename)
            download_url = url_for('chat.download_report', filename=pdf_filename, _external=True)
            bot_reply = f"¡Reporte listo! ✅ Encontré {len(df_reporte)} privados de libertad con esas características. <a href='{download_url}' target='_blank'>Descárgalo aquí</a>"
        else:
            bot_reply = f"No encontré registros que cumplan con: {criterio_desc}. ¿Intenta con otros criterios?"
            
    except KeyError as ke: error_reporte = f"Columna '{ke}' necesaria para reporte no encontrada."; accion_detectada = "error_reporte"
    except Exception as report_final_err: error_reporte = f"Error finalizando reporte: {report_final_err}"; accion_detectada = "error_reporte"; logger.error(f"ERROR: {error_reporte}", exc_info=True)

    if accion_detectada == "error_reporte":
        bot_reply = f"No pude generar el reporte. Razón: {error_reporte}"
    elif accion_detectada.startswith("error_"): # Catch other generic errors from NLU stage
        if not bot_reply: bot_reply = "Hubo un problema procesando tu solicitud de reporte."
        
    return bot_reply, accion_detectada
