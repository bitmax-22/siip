import pandas as pd
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from flask import current_app # Para acceder a la configuración de la app

def cargar_datos_google_sheet():
    """Carga los datos desde Google Sheets usando la configuración de la app."""
    SERVICE_ACCOUNT_FILE = current_app.config['SERVICE_ACCOUNT_FILE']
    SPREADSHEET_ID = current_app.config['SPREADSHEET_ID']
    SHEET_RANGE = current_app.config['SHEET_RANGE']
    SCOPES = current_app.config['SCOPES']

    if not all([SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, SHEET_RANGE]):
        print("ADVERTENCIA: Faltan variables de configuración para Google Sheets. La carga de datos fallará.")
        return None

    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                    range=SHEET_RANGE).execute()
        values = result.get('values', [])

        if not values:
            print(f"No se encontraron datos en Google Sheet ID: {SPREADSHEET_ID}, Rango: {SHEET_RANGE}")
            return None
        else:
            header = values[0]
            num_header_cols = len(header)
            data_rows = values[1:]

            # Asegurar que todas las filas de datos tengan la misma longitud que el encabezado
            # rellenando con None si es necesario.
            processed_data_rows = []
            for row in data_rows:
                processed_data_rows.append(row + [None] * (num_header_cols - len(row)))

            df = pd.DataFrame(processed_data_rows, columns=header)
            print(f"¡Google Sheet cargado exitosamente! {len(df)} registros.")

            # --- Conversiones de tipo ---
            if 'EDAD' in df.columns:
                df['EDAD'] = pd.to_numeric(df['EDAD'], errors='coerce')
            
            if 'CEDULA' in df.columns:
                 df['CEDULA'] = df['CEDULA'].astype(str).str.strip()
                 # Crear columna numérica para búsquedas rápidas de cédulas numéricas
                 df['N_CEDULA_NUMERIC'] = pd.to_numeric(df['CEDULA'].str.replace(r'[^0-9]', '', regex=True), errors='coerce')
                 # Crear columna normalizada para búsquedas de cédulas alfanuméricas
                 df['CEDULA_NORMALIZADA'] = df['CEDULA'].astype(str).str.replace('-', '', regex=False).str.replace(' ', '', regex=False).str.upper()
            
            if 'NOMBRES Y APELLIDOS' in df.columns:
                df['NOMBRES Y APELLIDOS'] = df['NOMBRES Y APELLIDOS'].astype(str).str.strip()
                # Crear columna normalizada para búsquedas de nombres (minúsculas, sin acentos)
                df['NOMBRE_NORMALIZADO'] = df['NOMBRES Y APELLIDOS'].astype(str).str.lower().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
            
            for col in ['PORCENTAJE FISICO CUMPLIDO', 'PORCENTAJE CUMPLIDO CON REDENCION', '% CUMPLIMIENTO SIN REDENCION', '%\n CUMPLIMIENTO CON REDENCION']: # Se mantienen los anteriores por si acaso, pero se priorizan los nuevos.
                 # Intentar acceder a la columna con el nombre exacto, incluyendo el \n si existe
                 col_name_to_check = col 
                 if '\n' in col and col not in df.columns: # Si el nombre con \n no está, probar sin él
                     col_name_to_check_alternative = col.replace('\n', '')
                     if col_name_to_check_alternative in df.columns:
                         col_name_to_check = col_name_to_check_alternative
                         print(f"Advertencia: Columna '{col}' no encontrada, usando '{col_name_to_check_alternative}' en su lugar.")
                     else: # Si ninguna de las dos existe, saltar esta columna
                         print(f"Advertencia: Columna '{col}' (ni su alternativa sin \\n) no encontrada. Saltando conversión.")
                         continue
                 elif col not in df.columns: # Si el nombre original no está y no tiene \n
                     print(f"Advertencia: Columna '{col}' no encontrada. Saltando conversión.")
                     continue

                 if col_name_to_check in df.columns:
                     # Limpiar: quitar '%', reemplazar ',' por '.'
                     df[col_name_to_check] = df[col_name_to_check].astype(str).str.replace('%', '', regex=False).str.replace(',', '.', regex=False).str.strip()
                     df[col_name_to_check] = pd.to_numeric(df[col_name_to_check], errors='coerce')
                     # Normalizar a decimal si es > 1 (ej. 75 -> 0.75). Si es 150 -> 1.5.
                     df[col_name_to_check] = df[col_name_to_check].apply(lambda x: x / 100 if pd.notna(x) and x > 1 else x)


            date_columns = [
                'FECHA DE NACIMIENTO', 'FECHA DE DETENCION', 'FECHA DE INGRESO',
                'FECHA PSICOSOCIAL', 'FECHA DE EGRESO', 'FECHA BOLETA DE EXCARCELACION',
                'FECHA EN BOLETA DE ENCARCELACION', 'FECHA DE CUMPLIMIENTO DE PENA',
                'FECHA CAMBIO ESTATUS'
            ]
            for col_fecha in date_columns:
                if col_fecha in df.columns:
                    df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce', dayfirst=True)
                    if df[col_fecha].isnull().any() and df[col_fecha].notnull().any():
                         print(f"Advertencia: Algunas fechas en '{col_fecha}' no pudieron ser convertidas.")
                    # Log específico para FECHA DE EGRESO
                    if col_fecha == 'FECHA DE EGRESO':
                        print(f"DEBUG data_loader: Primeras 5 'FECHA DE EGRESO' convertidas:\n{df[col_fecha].head()}")
                        print(f"DEBUG data_loader: Cantidad de NaT en 'FECHA DE EGRESO' después de conversión: {df[col_fecha].isnull().sum()} de {len(df[col_fecha])} filas.")

            return df
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo de credenciales de servicio en {SERVICE_ACCOUNT_FILE}")
        return None
    except HttpError as err:
        print(f"Error de la API de Google Sheets: {err}")
        return None
    except Exception as e:
        print(f"Error inesperado al cargar datos de Google Sheet: {e}")
        return None
