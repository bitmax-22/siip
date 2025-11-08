import pandas as pd
import numpy as np

# Lista de columnas que se sabe que contienen porcentajes y deben formatearse como tal
COLUMNAS_PORCENTAJE = [
    "PORCENTAJE FISICO CUMPLIDO",
    "PORCENTAJE CUMPLIDO CON REDENCION",
    "% CUMPLIMIENTO SIN REDENCION",
    "%\n CUMPLIMIENTO CON REDENCION" # Nombre original de la hoja de cálculo
    # Añadir cualquier otra columna de porcentaje aquí si es necesario
]

def format_value_for_display(value, column_name=None): # Añadir column_name
    """
    Formatea un valor para mostrarlo, especialmente fechas a DD/MM/AAAA y porcentajes.
    """
    if pd.isna(value):
        return "" # O "N/D" si prefieres
    if isinstance(value, pd.Timestamp):
        try:
            return value.strftime('%d/%m/%Y') # Formato DD/MM/AAAA
        except ValueError: # En caso de fechas muy antiguas o inválidas
            return str(value) # Fallback a string simple

    # Manejo de porcentajes si column_name es proporcionado
    if column_name:
        # Normalizar el nombre de la columna para la comparación (quitar \n)
        normalized_column_name_check = column_name.replace('\n', '')
        if normalized_column_name_check in COLUMNAS_PORCENTAJE and pd.api.types.is_number(value):
            try:
                # El valor ya debería estar como decimal (ej. 0.75 para 75%)
                # Multiplicar por 100 y añadir '%'. {:g} elimina ceros decimales innecesarios.
                return "{:g}%".format(float(value) * 100)
            except (ValueError, TypeError):
                # Si falla, se intentará el formateo numérico genérico más abajo
                pass

    if pd.api.types.is_number(value):
        try:
            if float(value) == int(float(value)): # Comparar como float
                return str(int(float(value)))
            else:
                 return f"{float(value):.2f}"
        except (ValueError, TypeError):
            pass
    return str(value)

def default_serializer(obj):
    """Serializador JSON que maneja tipos de Pandas y NumPy."""
    if isinstance(obj, (pd.Timestamp, pd.Period)):
        try: return obj.strftime('%d/%m/%Y')
        except: return str(obj)
    if isinstance(obj, (pd.Timedelta, pd.NaT.__class__)): return str(obj)
    if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                        np.int16, np.int32, np.int64, np.uint8,
                        np.uint16, np.uint32, np.uint64)):
        return int(obj)
    elif isinstance(obj, (np.float_, np.float16, np.float32,
                          np.float64)):
        return float(obj)
    elif isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    return str(obj)