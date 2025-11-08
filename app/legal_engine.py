# c:\Users\Administrator\Desktop\SIIP CON FOTO\app\legal_engine.py
from .models import Ley, Articulo # Ley y Articulo se usan para el prompt informativo
from .extensions import db
import re
import json
from flask import current_app


def interpretar_pregunta_legal_con_gemini(user_message, gemini_model, datos_siip_columnas):
    """
    Usa Gemini para intentar entender qué información legal busca el usuario.
    Retorna una estructura con la intención y entidades detectadas.
    El objetivo es que cualquier pregunta sobre leyes o contenido legal
    se clasifique como "pregunta_general_legal_rag".
    """
    # Obtener leyes disponibles para el prompt (informativo, ya que RAG es más amplio)
    leyes_disponibles_obj = Ley.query.with_entities(Ley.nombre_ley).all()
    leyes_str = ", ".join([l.nombre_ley for l in leyes_disponibles_obj]) if leyes_disponibles_obj else "Varias leyes y documentos legales cargados en la base de conocimientos documental (RAG)."

    prompt = f"""
Eres un asistente experto en interpretar preguntas legales para el sistema SIIP.
Tu tarea es identificar si el usuario está preguntando por el contenido de un artículo de una ley específica o haciendo una consulta legal general que deba ser respondida usando una base de conocimientos de documentos legales (RAG).

Base de conocimientos legal (informativo, la búsqueda RAG es más amplia): {leyes_str}
Columnas de datos de privados de libertad (solo para contexto si la pregunta legal se relaciona con un PDL, no para buscar leyes aquí): {", ".join(datos_siip_columnas)}

Solicitud del usuario: "{user_message}"

Analiza la solicitud y responde ÚNICAMENTE con un objeto JSON válido que contenga:
- "intencion_legal": ("pregunta_general_legal_rag", "no_legal")
  (Usa "pregunta_general_legal_rag" para CUALQUIER consulta sobre contenido de leyes, artículos, o preguntas legales generales. La opción "buscar_articulo" ya no existe y no debe ser usada.)
- "entidades_legales": {{
    "nombre_ley": "el nombre de la ley si se menciona o infiere claramente (opcional, ya que RAG buscará en todos los documentos)",
    "numero_articulo": "el número del artículo si se menciona o infiere claramente (opcional, ya que RAG buscará en todos los documentos)"
  }}
- "pregunta_original": "{user_message}"

Ejemplo para "qué dice el artículo 15 del código penal":
{{
  "intencion_legal": "pregunta_general_legal_rag",
  "entidades_legales": {{ "nombre_ley": "código penal", "numero_articulo": "15" }},
  "pregunta_original": "qué dice el artículo 15 del código penal"
}}

Ejemplo para "háblame del artículo 20 de la ley Z":
{{
  "intencion_legal": "pregunta_general_legal_rag",
  "entidades_legales": {{ "nombre_ley": "ley Z", "numero_articulo": "20" }},
  "pregunta_original": "háblame del artículo 20 de la ley Z"
}}

Ejemplo para "cuál es la pena para el homicidio":
{{
  "intencion_legal": "pregunta_general_legal_rag",
  "entidades_legales": {{ "nombre_ley": null, "numero_articulo": null }},
  "pregunta_original": "cuál es la pena para el homicidio"
}}

Ejemplo para "háblame sobre la ley de protección de víctimas":
{{
  "intencion_legal": "pregunta_general_legal_rag",
  "entidades_legales": {{ "nombre_ley": "ley de protección de víctimas", "numero_articulo": null }},
  "pregunta_original": "háblame sobre la ley de protección de víctimas"
}}

JSON de respuesta:
    """
    try:
        response = gemini_model.generate_content(prompt)
        # Limpiar la respuesta de Gemini para asegurar que sea un JSON válido
        json_response_text = response.text.strip().lstrip('```json').rstrip('```').strip()
        parsed_data = json.loads(json_response_text)
        return parsed_data, None
    except Exception as e:
        current_app.logger.error(f"Error interpretando pregunta legal con Gemini: {e}. Respuesta cruda: {response.text if 'response' in locals() else 'No response'}")
        return None, f"Error interpretando pregunta legal con Gemini: {e}"
