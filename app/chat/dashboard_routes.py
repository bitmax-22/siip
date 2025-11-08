# c:\Users\Administrator\Desktop\SIIP\app\chat\dashboard_routes.py
from flask import render_template, session, current_app, flash, jsonify
import pandas as pd
import numpy as np
from datetime import date
from collections import OrderedDict
import json
import traceback

from . import chat_bp # Import the blueprint from app/chat/__init__.py
from flask_login import login_required
from ..utils import default_serializer # Adjusted relative import

def robust_clean_percentage(series):
    """
    Limpia una serie de pandas que contiene porcentajes (como strings o números)
    y la convierte a formato numérico (ej., 75% o 75.0 se convierte a 0.75).
    """
    if series is None:
        return pd.Series(dtype=float)
    # Convertir a string para manejo uniforme
    s_str = series.astype(str).str.strip()
    # Quitar el símbolo '%'
    s_no_percent = s_str.str.replace('%', '', regex=False)
    # Reemplazar coma decimal por punto
    s_no_comma = s_no_percent.str.replace(',', '.', regex=False)
    # Convertir a numérico, errores a NaN
    s_numeric = pd.to_numeric(s_no_comma, errors='coerce')
    # Si el valor es mayor que 1 (ej. 75 en lugar de 0.75), dividir por 100.
    # Si es NaN o ya está normalizado (<=1), se mantiene.
    s_normalized = s_numeric.apply(lambda x: x / 100 if pd.notnull(x) and x > 1 else x)
    return s_normalized

@chat_bp.route('/dashboard')
@login_required
def dashboard(): # noqa: C901
    datos_siip_original = current_app.config.get('DATOS_SIIP')
    dashboard_data = {
        "counts": {},
        "charts": {}
    }

    if datos_siip_original is not None and not datos_siip_original.empty:
        df_copy = datos_siip_original.copy()

        current_app.logger.debug("Columnas cargadas desde Google Sheet por Pandas:")
        current_app.logger.debug(list(df_copy.columns))

        try:
            today_date = date.today()
            current_app.logger.debug(f"Fecha de 'hoy' según el sistema: {today_date}")

            if 'FECHA CAMBIO ESTATUS' in df_copy.columns:
                df_copy['FECHA CAMBIO ESTATUS'] = pd.to_datetime(df_copy['FECHA CAMBIO ESTATUS'], errors='coerce')
                current_app.logger.debug(f"Primeras 5 fechas convertidas de 'FECHA CAMBIO ESTATUS':\n{df_copy['FECHA CAMBIO ESTATUS'].head()}")
            else:
                current_app.logger.warning("La columna 'FECHA CAMBIO ESTATUS' no existe en los datos.")

            if 'FECHA DE EGRESO' in df_copy.columns:
                df_copy['FECHA DE EGRESO'] = pd.to_datetime(df_copy['FECHA DE EGRESO'], errors='coerce', dayfirst=True)
                current_app.logger.debug(f"Primeras 5 fechas convertidas de 'FECHA DE EGRESO':\n{df_copy['FECHA DE EGRESO'].head()}")
            else:
                current_app.logger.warning("La columna 'FECHA DE EGRESO' no existe en los datos.")

            # --- Preparar condición de fecha de cambio de estatus para hoy ---
            condicion_fecha_cambio_estatus_hoy = pd.Series(False, index=df_copy.index)
            if 'FECHA CAMBIO ESTATUS' in df_copy.columns and pd.api.types.is_datetime64_any_dtype(df_copy['FECHA CAMBIO ESTATUS']):
                df_fechas_validas_mov = df_copy[df_copy['FECHA CAMBIO ESTATUS'].notna()]
                if not df_fechas_validas_mov.empty:
                    condicion_fecha_cambio_estatus_hoy.loc[df_fechas_validas_mov.index] = (df_fechas_validas_mov['FECHA CAMBIO ESTATUS'].dt.date == today_date)
            
            # --- Identificar ingresos especiales de hoy para incluirlos en conteos generales ---
            # Ahora consideramos estos estatus como activos para conteo general, independientemente de la fecha de cambio de estatus.
            # La fecha de cambio de estatus solo se usará para los contadores de *movimientos del día*.
            cond_estatus_ing_interpenal = (df_copy['ESTATUS'].fillna('').str.upper() == 'INGRESO INTERPENAL')
            cond_estatus_ing_comisaria = (df_copy['ESTATUS'].fillna('').str.upper() == 'INGRESO COMISARIA')
            
            # Condición para PDL que están "dentro del sistema" para conteos generales
            # (Activos, Ingresos recientes que se consideran dentro, y Hospitalizados)
            condicion_dentro_del_sistema = (
                (df_copy['ESTATUS'].fillna('').str.upper() == 'ACTIVO') |
                cond_estatus_ing_interpenal |
                cond_estatus_ing_comisaria |
                (df_copy['ESTATUS'].fillna('').str.upper() == 'HOSPITALIZADO') |
                (df_copy['ESTATUS'].fillna('').str.upper() == 'TRASLADO') # Añadir TRASLADO aquí
            )
            df_dentro_del_sistema = df_copy[condicion_dentro_del_sistema].copy()
            # --- Fin preparación para conteos generales ---

            # Hospitalizados (conteo total de hospitalizados, independientemente de su condición jurídica para esta tarjeta específica)
            hospitalizados_df = df_copy[df_copy['ESTATUS'].fillna('').str.upper() == 'HOSPITALIZADO'].copy()
            hospitalizados_total = len(hospitalizados_df)
            current_app.logger.debug(f"Total Hospitalizados (para conteo general): {hospitalizados_total}")
            
            # Procesados (del df_dentro_del_sistema)
            procesados_df_general = df_dentro_del_sistema[df_dentro_del_sistema['CONDICION JURIDICA'].fillna('').str.upper() == 'PROCESADO'].copy()
            procesados_total = len(procesados_df_general)
            # Fases de los procesados (del df_dentro_del_sistema)
            fases_procesados_activos = procesados_df_general['FASE DEL PROCESO'].fillna('').str.upper().value_counts()
            procesados_control = int(fases_procesados_activos.get('CONTROL', 0))
            procesados_juicio = int(fases_procesados_activos.get('JUICIO', 0))
            procesados_corte = int(fases_procesados_activos.get('CORTE DE APELACIONES', 0))

            # Penados (del df_dentro_del_sistema)
            penados_df_general = df_dentro_del_sistema[df_dentro_del_sistema['CONDICION JURIDICA'].fillna('').str.upper() == 'PENADO'].copy()
            penados_total = len(penados_df_general)
            
            transitorios_df = df_copy[df_copy['ESTATUS'].fillna('').str.upper() == 'TRANSITORIO'].copy() 
            transitorios_count = len(transitorios_df)

            # --- Cálculo del Total General ---
            # Definir estatus que significan que el PDL ya NO está en el sistema
            estatus_de_egreso = [
                'PASIVO', 'FUGA', 'FALLECIDO', 
                'EGRESO INTERPENAL', 'EGRESO COMISARIA' # Añadir otros si aplican
            ]
            condicion_no_egresado = ~df_copy['ESTATUS'].fillna('').str.upper().isin(estatus_de_egreso)
            total_general_pdl = df_copy[condicion_no_egresado].shape[0]
            current_app.logger.debug(f"Total General (no egresados): {total_general_pdl}")
            # --- Fin Cálculo del Total General ---

            # Nuevos contadores de movimientos diarios
            libertades_hoy = 0
            fallecidos_hoy = 0
            fugas_hoy = 0
            ingresos_interpenales_hoy = 0
            ingresos_comisarias_hoy = 0
            egresos_interpenales_hoy = 0 # Contador para 'EGRESO INTERPENAL'
            egresos_comisarias_hoy = 0   # Nuevo contador para 'EGRESO COMISARIA'
            resguardos_hoy = 0
            depositos_hoy = 0

            # Los cálculos de movimientos diarios usan la 'condicion_fecha_cambio_estatus_hoy' ya definida
            if condicion_fecha_cambio_estatus_hoy.any(): # Solo si hay alguna posibilidad de movimiento hoy
                current_app.logger.debug(f"--- Inicio Depuración Libertades Hoy ({today_date}) ---")

                # 1. Libertades del día de hoy
                condicion_estatus_pasivo = df_copy['ESTATUS'].fillna('').str.upper() == 'PASIVO'
                df_debug_libertades = df_copy[condicion_estatus_pasivo & condicion_fecha_cambio_estatus_hoy]
                libertades_hoy = df_debug_libertades.shape[0]
                current_app.logger.debug(f"PDLs con ESTATUS=PASIVO y FECHA CAMBIO ESTATUS=hoy (Libertades): {libertades_hoy}")

                # 2. Fallecidos del día de hoy
                condicion_estatus_fallecido = df_copy['ESTATUS'].fillna('').str.upper() == 'FALLECIDO'
                fallecidos_hoy = df_copy[condicion_estatus_fallecido & condicion_fecha_cambio_estatus_hoy].shape[0]
                current_app.logger.debug(f"PDLs con FALLECIDO y FECHA CAMBIO ESTATUS=hoy: {fallecidos_hoy}")

                # 3. Fugas del día de hoy
                condicion_estatus_fuga = df_copy['ESTATUS'].fillna('').str.upper() == 'FUGA'
                fugas_hoy = df_copy[condicion_estatus_fuga & condicion_fecha_cambio_estatus_hoy].shape[0]
                current_app.logger.debug(f"PDLs con FUGA y FECHA CAMBIO ESTATUS=hoy: {fugas_hoy}")

                # 4. Ingresos interpenales del día de hoy
                # Usar la condición de estatus Y la condición de fecha de hoy para el *movimiento diario*
                ingresos_interpenales_hoy = df_copy[cond_estatus_ing_interpenal & condicion_fecha_cambio_estatus_hoy].shape[0]
                current_app.logger.debug(f"PDLs con ESTATUS=INGRESO INTERPENAL y FECHA CAMBIO ESTATUS=hoy: {ingresos_interpenales_hoy}")

                # 5. Ingresos comisarias del día de hoy
                # Usar la condición de estatus Y la condición de fecha de hoy para el *movimiento diario*
                ingresos_comisarias_hoy = df_copy[cond_estatus_ing_comisaria & condicion_fecha_cambio_estatus_hoy].shape[0]
                current_app.logger.debug(f"PDLs con ESTATUS=INGRESO COMISARIA y FECHA CAMBIO ESTATUS=hoy: {ingresos_comisarias_hoy}")

                # 6. Egresos Interpenales del día de hoy
                # Esta variable ahora cuenta los PDL con estatus 'EGRESO INTERPENAL'.
                condicion_estatus_egreso_interpenal_real = df_copy['ESTATUS'].fillna('').str.upper() == 'EGRESO INTERPENAL'
                egresos_interpenales_hoy = df_copy[condicion_estatus_egreso_interpenal_real & condicion_fecha_cambio_estatus_hoy].shape[0]
                current_app.logger.debug(f"PDLs con ESTATUS=EGRESO INTERPENAL y FECHA CAMBIO ESTATUS=hoy: {egresos_interpenales_hoy}")

                # 6b. Egresos Comisaría del día de hoy
                condicion_estatus_egreso_comisaria_real = df_copy['ESTATUS'].fillna('').str.upper() == 'EGRESO COMISARIA'
                egresos_comisarias_hoy = df_copy[condicion_estatus_egreso_comisaria_real & condicion_fecha_cambio_estatus_hoy].shape[0]
                current_app.logger.debug(f"PDLs con ESTATUS=EGRESO COMISARIA y FECHA CAMBIO ESTATUS=hoy: {egresos_comisarias_hoy}")

                # 7. Resguardos del día de hoy
                condicion_estatus_resguardo = df_copy['ESTATUS'].fillna('').str.upper() == 'RESGUARDO'
                resguardos_hoy = df_copy[condicion_estatus_resguardo & condicion_fecha_cambio_estatus_hoy].shape[0]
                current_app.logger.debug(f"PDLs con ESTATUS=RESGUARDO y FECHA CAMBIO ESTATUS=hoy: {resguardos_hoy}")

                # 8. Depositos del día de hoy
                condicion_estatus_deposito = df_copy['ESTATUS'].fillna('').str.upper() == 'DEPOSITO'
                depositos_hoy = df_copy[condicion_estatus_deposito & condicion_fecha_cambio_estatus_hoy].shape[0]
                current_app.logger.debug(f"PDLs con ESTATUS=DEPOSITO y FECHA CAMBIO ESTATUS=hoy: {depositos_hoy}")
            else:
                current_app.logger.warning("No se pudieron calcular los movimientos del día por falta de 'FECHA CAMBIO ESTATUS' o tipo incorrecto.")

            # Desglose de Hospitalizados (basado en el hospitalizados_df original)
            hospitalizados_procesados_df = hospitalizados_df[hospitalizados_df['CONDICION JURIDICA'].fillna('').str.upper() == 'PROCESADO']
            hospitalizados_procesados_total = int(len(hospitalizados_procesados_df))
            hospitalizados_penados = int(len(hospitalizados_df[hospitalizados_df['CONDICION JURIDICA'].fillna('').str.upper() == 'PENADO']))

            fases_hospitalizados_procesados = hospitalizados_procesados_df['FASE DEL PROCESO'].fillna('').str.upper().value_counts()
            # Los conteos de fases de hospitalizados se mantienen igual, basados en hospitalizados_procesados_df
            hospitalizados_proc_control = int(fases_hospitalizados_procesados.get('CONTROL', 0))
            hospitalizados_proc_juicio = int(fases_hospitalizados_procesados.get('JUICIO', 0))
            hospitalizados_proc_corte = int(fases_hospitalizados_procesados.get('CORTE DE APELACIONES', 0))

            dashboard_data['counts'] = {
                'total_general': total_general_pdl,
                'procesados_total': procesados_total,
                'procesados_control': procesados_control,
                'procesados_juicio': procesados_juicio,
                'procesados_corte': procesados_corte,
                'penados_total': penados_total,
                'transitorios': transitorios_count,
                'hospitalizados_total': hospitalizados_total,
                'hospitalizados_procesados_total': hospitalizados_procesados_total,
                'hospitalizados_penados': hospitalizados_penados,
                'hospitalizados_proc_control': hospitalizados_proc_control,
                'hospitalizados_proc_juicio': hospitalizados_proc_juicio,
                'hospitalizados_proc_corte': hospitalizados_proc_corte,
                # Nuevos contadores de movimientos diarios
                'libertades': libertades_hoy,
                'fallecidos': fallecidos_hoy,
                'fugas': fugas_hoy,
                'ingresos_interpenales': ingresos_interpenales_hoy,
                'ingresos_comisarias': ingresos_comisarias_hoy,
                'egresos_interpenales': egresos_interpenales_hoy, # Clave existente, ahora con el cálculo correcto para 'EGRESO INTERPENAL'
                'egresos_comisarias': egresos_comisarias_hoy,   # Nueva clave para el contador de 'EGRESO COMISARIA'
                'resguardos': resguardos_hoy,
                'depositos': depositos_hoy
            }

            # --- Nuevos cálculos para las tarjetas adicionales ---
            col_redencion = "PORCENTAJE CUMPLIDO CON REDENCION" 
            if col_redencion in df_copy.columns:
                # Usar df_dentro_del_sistema para estos cálculos, ya que queremos
                # contar solo sobre la población que se considera actualmente en el sistema.
                df_temp_cumplimiento = df_dentro_del_sistema.copy() # Trabajar sobre la población "dentro del sistema"
                current_app.logger.debug(f"DEBUG Pena Cumplida: Filas en df_dentro_del_sistema: {len(df_temp_cumplimiento)}")
                
                # La columna ya fue procesada por data_loader.py y debería ser numérica y normalizada (ej. 100% -> 1.0)
                # Si no es numérica aquí, es un problema en data_loader o en los datos originales.
                # Por seguridad, convertimos a numérico aquí de nuevo, pero sin la lógica de robust_clean_percentage.
                col_redencion_numeric_directa = pd.to_numeric(df_temp_cumplimiento[col_redencion], errors='coerce')
                current_app.logger.debug(f"DEBUG Pena Cumplida: Primeros valores de '{col_redencion}' (después de to_numeric directo):\n{col_redencion_numeric_directa.head()}")

                # Filtrar por >= 1.0 (100%)
                condicion_pena_cumplida_numeric = col_redencion_numeric_directa >= 1.0
                df_con_pena_cumplida = df_temp_cumplimiento[condicion_pena_cumplida_numeric]
                num_con_pena_cumplida = len(df_con_pena_cumplida)
                current_app.logger.debug(f"DEBUG Pena Cumplida: Número de PDL 'dentro del sistema' con '{col_redencion}' (numérico directo) >= 1.0: {num_con_pena_cumplida}")
                
                # Si quieres ver las cédulas de los que cumplen para comparar con tu Google Sheet:
                if not df_con_pena_cumplida.empty and 'CEDULA' in df_con_pena_cumplida.columns:
                    current_app.logger.debug(f"DEBUG Pena Cumplida: Cédulas de los {num_con_pena_cumplida} que SÍ cumplen (>=100% redención) y están dentro del sistema:\n{df_con_pena_cumplida['CEDULA'].tolist()}")

                # Log para los que NO cumplen el porcentaje pero SÍ están en df_dentro_del_sistema
                if num_con_pena_cumplida < 24 and num_con_pena_cumplida !=0: 
                    df_no_cumplen_porcentaje = df_temp_cumplimiento[~condicion_pena_cumplida_numeric]
                    if not df_no_cumplen_porcentaje.empty and 'CEDULA' in df_no_cumplen_porcentaje.columns and col_redencion in df_no_cumplen_porcentaje.columns:
                        current_app.logger.debug(f"DEBUG Pena Cumplida: {len(df_no_cumplen_porcentaje)} PDL en 'df_dentro_del_sistema' que NO tienen '{col_redencion}' (numérico directo) >= 1.0. Ejemplos (Cédula, Estatus, %Redención Original, %Redención Numérico Directo):")
                        for _, row_debug in df_no_cumplen_porcentaje[['CEDULA', 'ESTATUS', col_redencion]].assign(NUMERIC_DIRECT=col_redencion_numeric_directa[df_no_cumplen_porcentaje.index]).head(30).iterrows():
                            current_app.logger.debug(f"  - C.I: {row_debug['CEDULA']}, Estatus: {row_debug['ESTATUS']}, %RedOrig: '{row_debug[col_redencion]}', %RedNumDirect: {row_debug['NUMERIC_DIRECT']}")
                
                dashboard_data['counts']['pena_cumplida_redencion_total'] = num_con_pena_cumplida
                # Tarjeta 2: PDL 75% CUMPLIDO CON REDENCION (reutiliza la columna numérica)
                dashboard_data['counts']['setentaycinco_redencion_total'] = df_temp_cumplimiento[col_redencion_numeric_directa >= 0.75].shape[0]
            else:
                dashboard_data['counts']['pena_cumplida_redencion_total'] = 'N/A'
                dashboard_data['counts']['setentaycinco_redencion_total'] = 'N/A'
                current_app.logger.warning(f"Columna '{col_redencion}' no encontrada para tarjetas de cumplimiento con redención.")

            col_fisico = "PORCENTAJE FISICO CUMPLIDO" 
            if col_fisico in df_copy.columns:
                # Aplicar el mismo filtro de df_dentro_del_sistema aquí también
                df_temp_fisico = df_dentro_del_sistema.copy()
                # Usar la columna ya procesada por data_loader
                col_fisico_numeric_directa = pd.to_numeric(df_temp_fisico[col_fisico], errors='coerce')
                dashboard_data['counts']['setentaycinco_fisico_total'] = df_temp_fisico[col_fisico_numeric_directa >= 0.75].shape[0]
            else:
                dashboard_data['counts']['setentaycinco_fisico_total'] = 'N/A'
                current_app.logger.warning(f"Columna '{col_fisico}' no encontrada para tarjeta 'PDL 75% CUMPLIDO FISICO'.")

            col_computo = "POSEE COMPUTO" 
            col_condicion_juridica = "CONDICION JURIDICA" 
            if col_computo in df_copy.columns and col_condicion_juridica in df_copy.columns:
                # Filtrar primero por penados activos, luego por los que no poseen cómputo
                # Usamos 'penados_df_general' que incluye todos los penados "dentro del sistema"
                dashboard_data['counts']['penados_sin_computo_total'] = penados_df_general[
                    penados_df_general[col_computo].astype(str).str.strip().str.upper() == 'NO'
                ].shape[0]
            else:
                dashboard_data['counts']['penados_sin_computo_total'] = 'N/A'
                if not col_computo in df_copy.columns:
                    current_app.logger.warning(f"Columna '{col_computo}' no encontrada para tarjeta 'PDL PENADOS SIN COMPUTO'.")
                if not col_condicion_juridica in df_copy.columns: # Aunque penados_activos_df ya la usa, es bueno verificar aquí también
                    current_app.logger.warning(f"Columna '{col_condicion_juridica}' no encontrada para tarjeta 'PDL PENADOS SIN COMPUTO'.") # type: ignore
            # --- Fin de nuevos cálculos ---

            # Para los gráficos, usamos df_dentro_del_sistema que ya tiene la lógica correcta de quiénes contar
            poblacion_para_graficos_df = df_dentro_del_sistema.copy()

            dashboard_data['charts']['proc_vs_pen'] = {
                'labels': ['Procesados', 'Penados'],
                'values': [int(procesados_total), int(penados_total)]
            }

            if 'EDAD' in poblacion_para_graficos_df.columns:
                bins = [18, 25, 35, 45, 55, 70, 120]
                labels_edad_grupos = ['18-24', '25-34', '35-44', '45-54', '55-69', '70+']
                poblacion_para_graficos_df['GRUPO_EDAD'] = pd.cut(poblacion_para_graficos_df['EDAD'], bins=bins, labels=labels_edad_grupos, right=False)
                edad_counts = poblacion_para_graficos_df['GRUPO_EDAD'].value_counts().sort_index()
                dashboard_data['charts']['edad_grupos'] = {
                    'labels': edad_counts.index.tolist(),
                    'values': [int(v) for v in edad_counts.values]
                }
            else:
                current_app.logger.warning("Columna 'EDAD' no encontrada para gráficos de edad.")

            if 'CIRCUITO JUDICIAL' in poblacion_para_graficos_df.columns and 'CONDICION JURIDICA' in poblacion_para_graficos_df.columns:
                df_condicion_filtrada = poblacion_para_graficos_df[poblacion_para_graficos_df['CONDICION JURIDICA'].str.upper().isin(['PROCESADO', 'PENADO'])]
                df_condicion_filtrada['CIRCUITO_JUDICIAL_GRAFICO'] = df_condicion_filtrada['CIRCUITO JUDICIAL'].replace(
                    {'AREA METROPOLITANA DE CARACAS': 'AMC'}, regex=False
                )
                distribucion_estado_condicion = df_condicion_filtrada.groupby(['CIRCUITO_JUDICIAL_GRAFICO', 'CONDICION JURIDICA']).size().unstack(fill_value=0)
                if 'PROCESADO' not in distribucion_estado_condicion:
                    distribucion_estado_condicion['PROCESADO'] = 0
                if 'PENADO' not in distribucion_estado_condicion:
                    distribucion_estado_condicion['PENADO'] = 0
                distribucion_estado_condicion['TOTAL_ESTADO'] = distribucion_estado_condicion['PROCESADO'] + distribucion_estado_condicion['PENADO']
                distribucion_estado_condicion = distribucion_estado_condicion.sort_values(by='TOTAL_ESTADO', ascending=False) 
                dashboard_data['charts']['distribucion_estado_condicion'] = {
                    'labels': distribucion_estado_condicion.index.tolist(),
                    'procesados': distribucion_estado_condicion['PROCESADO'].tolist(),
                    'penados': distribucion_estado_condicion['PENADO'].tolist()
                }
            else:
                current_app.logger.warning("Columnas 'CIRCUITO JUDICIAL' o 'CONDICION JURIDICA' no encontradas para gráfico de distribución por estado.")

            if 'UBICACION' in poblacion_para_graficos_df.columns:
                torres_config_dashboard = OrderedDict([
                    ('OBSERVACION', ['OBSERVACION 1A', 'OBSERVACION 1B', 'OBSERVACION 2A', 'OBSERVACION 2B']),
                    ('ANEXO I', ['ANEXO I ALA A', 'ANEXO I ALA B', 'ANEXO I']),
                    ('ANEXO II', ['ANEXO II 1A', 'ANEXO II 1B', 'ANEXO II 2A', 'ANEXO II 2B']),
                    ('MINIMA', ['MINIMA 1A', 'MINIMA 1B', 'MINIMA 2A', 'MINIMA 2B']),
                    ('MEDIA', ['MEDIA 1A', 'MEDIA 1B', 'MEDIA 2A', 'MEDIA 2B']),
                    ('MAXIMA', ['MAXIMA 1A', 'MAXIMA 1B', 'MAXIMA 2A', 'MAXIMA 2B']),
                    ('ENFERMERIA', ['ENFERMERIA']),
                    ('REFLEXION', ['REFLEXION']),
                ])
                
                def get_torre_principal_para_grafico(ubicacion_str):
                    if pd.isna(ubicacion_str): return "Otros"
                    ubicacion_actual_upper = str(ubicacion_str).upper()
                    for torre, modulos_internos_config in torres_config_dashboard.items():
                        if ubicacion_actual_upper == torre.upper(): return torre
                        for modulo_config in modulos_internos_config:
                            if ubicacion_actual_upper == str(modulo_config).upper(): return torre
                    return "Otros"

                poblacion_para_graficos_df['TORRE_PARA_GRAFICO'] = poblacion_para_graficos_df['UBICACION'].apply(get_torre_principal_para_grafico)
                poblacion_para_graficos_df['UBICACION_STR'] = poblacion_para_graficos_df['UBICACION'].fillna('Desconocido').astype(str)
                ubicacion_counts_df = poblacion_para_graficos_df.groupby(['TORRE_PARA_GRAFICO', 'UBICACION_STR']).size().reset_index(name='CONTEO')
                ubicacion_counts_df = ubicacion_counts_df[ubicacion_counts_df['CONTEO'] > 0]
                orden_torres_grafico = list(torres_config_dashboard.keys()) + ["Otros", "Desconocido"]
                ubicacion_counts_df['TORRE_PARA_GRAFICO'] = pd.Categorical(
                    ubicacion_counts_df['TORRE_PARA_GRAFICO'], categories=orden_torres_grafico, ordered=True
                )
                ubicacion_counts_df_sorted = ubicacion_counts_df.sort_values(by=['TORRE_PARA_GRAFICO', 'UBICACION_STR'])
                dashboard_data['charts']['ubicacion_detallada'] = {
                    'labels': ubicacion_counts_df_sorted['UBICACION_STR'].tolist(),
                    'values': ubicacion_counts_df_sorted['CONTEO'].tolist(),
                    'torres': ubicacion_counts_df_sorted['TORRE_PARA_GRAFICO'].tolist()
                }
            else:
                current_app.logger.warning("Columna 'UBICACION' no encontrada para gráfico de ubicación.")

            if 'DELITO CON MAYOR GRAVEDAD' in poblacion_para_graficos_df.columns:
                top_n_delitos = 7
                delito_counts = poblacion_para_graficos_df['DELITO CON MAYOR GRAVEDAD'].value_counts().nlargest(top_n_delitos)
                dashboard_data['charts']['delitos'] = {
                    'labels': delito_counts.index.tolist(),
                    'values': [int(v) for v in delito_counts.values]
                }
            else:
                current_app.logger.warning("Columna 'DELITO CON MAYOR GRAVEDAD' no encontrada para gráfico de delitos.")

            if 'NACIONALIDAD' in poblacion_para_graficos_df.columns:
                count_vzla = len(poblacion_para_graficos_df[poblacion_para_graficos_df['NACIONALIDAD'].fillna('').str.upper() == 'VENEZOLANA'])
                count_extranj = len(poblacion_para_graficos_df) - count_vzla
                dashboard_data['charts']['nacionalidad'] = {
                    'labels': ['Venezolanos', 'Extranjeros'],
                    'values': [int(count_vzla), int(count_extranj)]
                }
            else:
                current_app.logger.warning("Columna 'NACIONALIDAD' no encontrada para gráfico de nacionalidad.")

        except Exception as e:
            current_app.logger.error(f"Error procesando datos para dashboard: {e}")
            traceback.print_exc()
            flash("Error al generar los datos para el dashboard.", "danger")
    else: # Si datos_siip_original es None o está vacío
        keys_a_inicializar = [
            'total_general', 'procesados_total', 'procesados_control', 'procesados_juicio',
            'procesados_corte', 'penados_total', 'transitorios', 'hospitalizados_total',
            'hospitalizados_procesados_total', 'hospitalizados_penados',
            'hospitalizados_proc_control', 'hospitalizados_proc_juicio', 'hospitalizados_proc_corte',
            'libertades', 'fallecidos', 'fugas', 'interpenales',
            # Nuevos contadores de movimientos diarios
            'ingresos_interpenales', 'ingresos_comisarias', 'egresos_interpenales', 'egresos_comisarias',
            'resguardos', 'depositos',
            # Tarjetas de cumplimiento y cómputo (ya existentes)
            'pena_cumplida_redencion_total', 
            'setentaycinco_redencion_total',
            'setentaycinco_fisico_total', 'penados_sin_computo_total'
        ]
        for key in keys_a_inicializar:
            dashboard_data['counts'][key] = 0 # o 'N/A' si prefieres

    current_app.logger.debug(f"Dashboard Counts para plantilla: {dashboard_data.get('counts', {})}")
    dashboard_data_json = json.dumps(dashboard_data, default=default_serializer)

    return render_template('dashboard.html', username=session.get('user_id'), dashboard_data=dashboard_data, dashboard_data_json=dashboard_data_json)
