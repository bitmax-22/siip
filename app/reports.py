# c:\Users\Equipo z\Desktop\SIIP\app\reports.py
import os
import io
import time
import traceback
from datetime import date
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF, XPos, YPos
import pandas as pd
from flask import current_app # Para acceder a config (rutas)
from .utils import format_value_for_display # Importar desde utils

# --- Función para Añadir Marca de Agua PDF ---
def add_pdf_watermark(pdf):
    resources_folder = current_app.config['RESOURCES_FOLDER']
    watermark_path = os.path.join(resources_folder, "LOGO.png") # La marca de agua sigue siendo LOGO.png
    watermark_stream = None
    wm_w_mm = 100
    aspect_ratio = 1.0
    try:
        watermark_logo = Image.open(watermark_path).convert("RGBA")
        original_width_px, original_height_px = watermark_logo.size
        if original_width_px > 0:
            aspect_ratio = original_height_px / original_width_px
        else:
            aspect_ratio = 1.0

        base_width_px = 600
        w_percent = (base_width_px / float(original_width_px)) if original_width_px > 0 else 1.0
        h_size_px = int((float(original_height_px) * float(w_percent)))
        watermark_logo_resized = watermark_logo.resize((base_width_px, h_size_px), Image.Resampling.LANCZOS)

        alpha = 40
        watermark_logo_transparent = Image.new("RGBA", watermark_logo_resized.size)
        for x in range(watermark_logo_resized.width):
            for y in range(watermark_logo_resized.height):
                r, g, b, a_orig = watermark_logo_resized.getpixel((x, y))
                new_alpha = int(a_orig * (alpha / 255.0)) if a_orig > 0 else 0
                watermark_logo_transparent.putpixel((x, y), (r, g, b, new_alpha))

        watermark_stream = io.BytesIO()
        watermark_logo_transparent.save(watermark_stream, format="PNG")
        watermark_stream.seek(0)

        page_w_mm = pdf.w
        page_h_mm = pdf.h
        wm_h_mm = wm_w_mm * aspect_ratio
        wm_x_mm = (page_w_mm - wm_w_mm) / 2
        wm_y_mm = (page_h_mm - wm_h_mm) / 2

        pdf.image(watermark_stream, x=wm_x_mm, y=wm_y_mm, w=wm_w_mm, type='PNG')
        watermark_stream.seek(0)
        print(f"DEBUG: Marca de agua PDF añadida desde {watermark_path}")
        return watermark_stream, wm_w_mm, aspect_ratio

    except FileNotFoundError:
        print(f"ERROR: No se encontró el archivo de marca de agua PDF en {watermark_path}")
    except Exception as wm_error:
        print(f"Error al procesar o añadir la marca de agua PDF: {wm_error}")
    return None, wm_w_mm, aspect_ratio

# --- Función para Generar Reporte PDF ---
def generar_reporte_pdf(dataframe_filtrado, titulo, filename):
    """Genera un archivo PDF a partir de un DataFrame."""
    resources_folder = current_app.config['RESOURCES_FOLDER']
    reports_folder = current_app.config['REPORTS_FOLDER']

    pdf = FPDF(orientation='L') # Landscape
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    watermark_stream_obj, wm_w_mm_global, aspect_ratio_global = add_pdf_watermark(pdf)

    # --- Encabezado del PDF ---
    # Logo del MSP (ahora LOGO MSP NEGRO.png)
    # Ajustar el path del logo para el encabezado del PDF
    logo_msp_path = os.path.join(resources_folder, "LOGO MSP NEGRO.png") # Nuevo logo para el reporte
    logo_x = pdf.l_margin # Usar el margen izquierdo definido por FPDF
    logo_y = 8
    logo_w = 20 # Ancho del logo en mm
    logo_h_approx = 0 # Se calculará basado en el aspect ratio
    try:
        with Image.open(logo_msp_path) as img_logo: # Usar with para asegurar que el archivo se cierre
            img_w, img_h = img_logo.size
            logo_h_approx = logo_w * (img_h / img_w) if img_w > 0 else 10 # Calcular altura proporcional
        pdf.image(logo_msp_path, x=logo_x, y=logo_y, w=logo_w)
    except Exception as logo_error:
        print(f"ADVERTENCIA: No se pudo añadir el logo MSP al PDF: {logo_error}")
        logo_h_approx = 10 # Fallback si no se puede cargar

    # Título del reporte
    pdf.set_font("Helvetica", size=10)
    # Calcular posición X e Y para el título, centrado al lado del logo
    title_x_start = logo_x + logo_w + 5 # Espacio después del logo
    # Centrar verticalmente el título con respecto a la altura aproximada del logo
    # (FontSize en puntos / 72 puntos por pulgada) * 25.4 mm por pulgada = FontSize en mm
    font_size_mm = pdf.font_size_pt / 72 * 25.4
    title_y_centered = logo_y + (logo_h_approx / 2) - (font_size_mm / 2)
    title_y_final = max(title_y_centered, logo_y) # Asegurar que no esté por encima del logo

    pdf.set_xy(title_x_start, title_y_final)
    available_width_for_title = pdf.w - title_x_start - pdf.r_margin # Ancho disponible para el título
    pdf.cell(available_width_for_title, 10, txt=titulo, align="C")

    # Nombre del Establecimiento Penitenciario (si aplica)
    establishment_name = ""
    if not dataframe_filtrado.empty and "ESTABLECIMIENTO PENITENCIARIO" in dataframe_filtrado.columns:
        # Tomar el primer valor no nulo de la columna como nombre del establecimiento
        valid_establishments = dataframe_filtrado["ESTABLECIMIENTO PENITENCIARIO"].dropna()
        if not valid_establishments.empty:
            first_valid_establishment = valid_establishments.iloc[0]
            establishment_name = format_value_for_display(first_valid_establishment, column_name="ESTABLECIMIENTO PENITENCIARIO")
    print(f"DEBUG: Nombre Establecimiento encontrado: '{establishment_name}'")

    if establishment_name:
        title_bottom_y_est = title_y_final + 10 # Debajo del título principal
        establishment_y_est = title_bottom_y_est + 1 # Un poco más abajo
        pdf.set_xy(title_x_start, establishment_y_est) # Alinear con el título
        pdf.set_font("Helvetica", 'I', 9) # Fuente más pequeña e itálica
        pdf.cell(available_width_for_title, 5, txt=establishment_name, align="C")
        print(f"DEBUG: Dibujando establishment_name en primera página: '{establishment_name}'")

    # Establecer la posición Y para el inicio de la tabla, después del encabezado
    current_y_after_header = pdf.get_y() # Obtener Y después de dibujar el nombre del establecimiento
    header_bottom_y = max(logo_y + logo_h_approx, current_y_after_header) # El punto más bajo del logo o del texto del establecimiento
    pdf.set_y(header_bottom_y + 3) # Espacio antes de la tabla

    if dataframe_filtrado.empty:
         pdf.ln(10) # Espacio antes del mensaje
         pdf.cell(0, 10, txt="No se encontraron registros para este reporte.", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    else:
        df_para_pdf = dataframe_filtrado.copy()
        # Excluir columnas no deseadas
        columnas = df_para_pdf.columns.tolist()
        columnas = [col for col in columnas if col not in ['N_CEDULA_NUMERIC']] # Ejemplo de exclusión

        # --- Cálculo de anchos de columna ---
        ancho_total_disponible = pdf.w - pdf.l_margin - pdf.r_margin
        # Proporciones sugeridas (ajustar según necesidad)
        column_proportions = {
            '#': 0.4, 'CEDULA': 0.8, 'NOMBRES Y APELLIDOS': 2.5, 'EDAD': 0.4,
            'DELITO CON MAYOR GRAVEDAD': 1.5, 'DELITO DE EXPEDIENTE': 2, 'TIEMPO DE PENA': 1.5,
            'CIRCUITO JUDICIAL': 1, 'CONDICION JURIDICA': 1, 'ESTABLECIMIENTO PENITENCIARIO': 2,
            'UBICACION': 1, 'FECHA DE INGRESO': 1, 'FECHA DE NACIMIENTO': 1,
            '_default_': 1.5 # Proporción por defecto para columnas no listadas
        }
        num_cols = len(columnas)
        if num_cols > 15: column_proportions['_default_'] = 1.0 # Reducir si hay muchas columnas
        elif num_cols > 10: column_proportions['_default_'] = 1.2

        total_proportion = sum(column_proportions.get(col, column_proportions['_default_']) for col in columnas)
        calculated_widths = {col: (column_proportions.get(col, column_proportions['_default_']) / total_proportion) * ancho_total_disponible for col in columnas}

        # --- Dibujar encabezado de la tabla ---
        pdf.set_font("Helvetica", 'B', 6) # Fuente para el encabezado de la tabla
        y_inicial_header_calc = pdf.get_y()
        line_height_header = 3 # Altura de línea base para el texto del encabezado
        max_altura_header = line_height_header # Altura mínima para el encabezado

        # Calcular la altura máxima necesaria para el encabezado (multi-línea)
        for col in columnas:
            header_text = str(col).replace('_', ' ').replace('\n', ' ').title() # Formatear texto del encabezado
            ancho_actual = calculated_widths.get(col, 10) # Ancho de la columna actual
            if ancho_actual <= 0: ancho_actual = 10 # Fallback
            # Usar multi_cell con dry_run para calcular la altura necesaria
            texto_lineas_header_dry = pdf.multi_cell(ancho_actual, line_height_header, txt=header_text, border=0, align="C", dry_run=True, output='LINES')
            altura_header_necesaria = len(texto_lineas_header_dry) * line_height_header
            max_altura_header = max(max_altura_header, altura_header_necesaria)
        max_altura_header = max(max_altura_header, line_height_header) # Asegurar altura mínima

        pdf.set_y(y_inicial_header_calc) # Volver a la Y inicial para dibujar los encabezados
        x_actual_header = pdf.l_margin
        for col in columnas:
            header_text = str(col).replace('_', ' ').replace('\n', ' ').title()
            ancho_actual = calculated_widths.get(col, 10)
            if ancho_actual <= 0: ancho_actual = 10
            pdf.set_xy(x_actual_header, y_inicial_header_calc) # Establecer posición para cada celda de encabezado
            pdf.multi_cell(ancho_actual, line_height_header, txt=header_text, border=0, align="C", new_x=XPos.LMARGIN, new_y=YPos.TOP) # Texto sin borde, Y no cambia
            # Dibujar el rectángulo del borde con la altura máxima calculada
            pdf.rect(x_actual_header, y_inicial_header_calc, ancho_actual, max_altura_header)
            x_actual_header += ancho_actual
        pdf.ln(max_altura_header) # Salto de línea después del encabezado

        # --- Dibujar filas de datos ---
        pdf.set_font("Helvetica", size=5.5) # Fuente para los datos
        line_height = 4.5 # Altura de línea base para los datos

        for index, row in df_para_pdf.iterrows():
            # Calcular altura máxima necesaria para la fila actual
            max_altura_fila = line_height
            for col in columnas:
                valor = format_value_for_display(row.get(col), column_name=col)
                ancho_actual = calculated_widths.get(col, 10)
                if ancho_actual <= 0: ancho_actual = 10
                try:
                    texto_lineas_dry = pdf.multi_cell(ancho_actual, line_height, txt=valor, border=0, align='L', dry_run=True, output='LINES')
                    altura_necesaria = len(texto_lineas_dry) * line_height
                except Exception as cell_calc_err:
                     print(f"Advertencia: Error calculando altura de celda para '{col}': {cell_calc_err}")
                     altura_necesaria = line_height # Fallback

                max_altura_fila = max(max_altura_fila, altura_necesaria)
            max_altura_fila = max(max_altura_fila, line_height) # Asegurar altura mínima

            # Verificar si se necesita nueva página
            y_antes_fila = pdf.get_y()
            if y_antes_fila + max_altura_fila > pdf.page_break_trigger:
                pdf.add_page()
                # Repetir marca de agua en nueva página
                if watermark_stream_obj:
                    try:
                        watermark_stream_obj.seek(0) # Rebobinar el stream
                        page_w_mm_new = pdf.w
                        page_h_mm_new = pdf.h
                        wm_h_mm_new = wm_w_mm_global * aspect_ratio_global # Usar aspect_ratio global
                        wm_x_mm_new = (page_w_mm_new - wm_w_mm_global) / 2
                        wm_y_mm_new = (page_h_mm_new - wm_h_mm_new) / 2
                        pdf.image(watermark_stream_obj, x=wm_x_mm_new, y=wm_y_mm_new, w=wm_w_mm_global, type='PNG')
                        print("DEBUG: Marca de agua PDF añadida (nueva página)")
                    except Exception as wm_err_new:
                        print(f"Error añadiendo marca de agua en nueva página: {wm_err_new}")

                # Repetir logo y título en nueva página
                try:
                    pdf.image(logo_msp_path, x=logo_x, y=logo_y, w=logo_w) # Logo
                except Exception as logo_error_new_page:
                    print(f"ADVERTENCIA: No se pudo añadir el logo MSP al PDF (nueva página): {logo_error_new_page}")

                pdf.set_font("Helvetica", size=10)
                pdf.set_xy(title_x_start, title_y_final) # Usar las mismas coordenadas relativas
                pdf.cell(available_width_for_title, 10, txt=titulo, align="C")

                current_y_after_repeated_header = title_y_final + 10
                if establishment_name:
                    establishment_y_new_page = current_y_after_repeated_header + 1
                    pdf.set_xy(title_x_start, establishment_y_new_page)
                    pdf.set_font("Helvetica", 'I', 9)
                    pdf.cell(available_width_for_title, 5, txt=establishment_name, align="C")
                    print(f"DEBUG: Dibujando establishment_name en nueva página: '{establishment_name}'")
                    current_y_after_repeated_header = pdf.get_y() # Actualizar Y

                # Repetir encabezado de tabla
                pdf.set_font("Helvetica", 'B', 6)
                header_start_y_new_page = max(logo_y + logo_h_approx, current_y_after_repeated_header) + 3
                pdf.set_y(header_start_y_new_page) # Establecer Y para el inicio del encabezado repetido
                x_actual_header_new = pdf.l_margin
                for col_h in columnas:
                    ancho_actual_h = calculated_widths.get(col_h, 10)
                    if ancho_actual_h <= 0: ancho_actual_h = 10
                    header_text_h = str(col_h).replace('_', ' ').replace('\n', ' ').title()
                    pdf.set_xy(x_actual_header_new, header_start_y_new_page) # Posicionar para cada celda
                    pdf.multi_cell(ancho_actual_h, line_height_header, txt=header_text_h, border=0, align="C", new_x=XPos.LMARGIN, new_y=YPos.TOP)
                    pdf.rect(x_actual_header_new, header_start_y_new_page, ancho_actual_h, max_altura_header) # Dibujar borde con altura máxima
                    x_actual_header_new += ancho_actual_h
                pdf.ln(max_altura_header)
                pdf.set_font("Helvetica", size=5.5) # Volver a fuente de datos
                y_antes_fila = pdf.get_y() # Actualizar Y para la fila de datos

            # Dibujar bordes de la celda
            current_x_border = pdf.l_margin
            for col in columnas:
                ancho_actual = calculated_widths.get(col, 10)
                if ancho_actual <= 0: ancho_actual = 10
                pdf.rect(current_x_border, y_antes_fila, ancho_actual, max_altura_fila)
                current_x_border += ancho_actual

            # Dibujar texto de la celda (multi_cell para manejo de altura)
            current_x_text = pdf.l_margin
            text_padding = 0.5 # Pequeño padding dentro de la celda
            for col in columnas:
                 valor = format_value_for_display(row.get(col))
                 valor = format_value_for_display(row.get(col), column_name=col)
                 ancho_actual = calculated_widths.get(col, 10)
                 if ancho_actual <= 0: ancho_actual = 10

                 pdf.set_xy(current_x_text + text_padding, y_antes_fila + text_padding) # Posicionar para texto
                 pdf.multi_cell(ancho_actual - 2 * text_padding, line_height, txt=valor, border=0, align="J") # 'J' para justificado si es posible
                 current_x_text += ancho_actual

            pdf.set_y(y_antes_fila + max_altura_fila) # Mover Y al final de la fila dibujada

    filepath = os.path.join(reports_folder, filename)
    try:
        pdf.output(filepath)
        print(f"DEBUG: Reporte PDF generado en {filepath}")
        if watermark_stream_obj: # Cerrar el stream de la marca de agua
            watermark_stream_obj.close()
        return filepath
    except Exception as e:
        print(f"Error al guardar PDF: {e}")
        if watermark_stream_obj:
            watermark_stream_obj.close()
        raise

# --- Función para Generar Reporte PDF de PDLs sin Foto ---
def generar_reporte_pdf_pdl_sin_foto(dataframe_filtrado, titulo, filename):
    """Genera un archivo PDF con los PDLs que no tienen fotos."""
    resources_folder = current_app.config['RESOURCES_FOLDER']
    reports_folder = current_app.config['REPORTS_FOLDER']

    pdf = FPDF(orientation='L')  # Landscape
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Agregar fuente Arial para soporte Unicode
    try:
        pdf.add_font('Arial', '', r'C:\Windows\Fonts\arial.ttf')
        pdf.add_font('Arial', 'B', r'C:\Windows\Fonts\arialbd.ttf')
        unicode_font = 'Arial'
    except Exception as font_error:
        print(f"Advertencia: No se pudo cargar Arial, usando Helvetica: {font_error}")
        unicode_font = 'Helvetica'

    watermark_stream_obj, wm_w_mm_global, aspect_ratio_global = add_pdf_watermark(pdf)

    # --- Encabezado del PDF ---
    logo_msp_path = os.path.join(resources_folder, "LOGO MSP NEGRO.png")
    logo_x = pdf.l_margin
    logo_y = 8
    logo_w = 20
    logo_h_approx = 0
    try:
        with Image.open(logo_msp_path) as img_logo:
            img_w, img_h = img_logo.size
            logo_h_approx = logo_w * (img_h / img_w) if img_w > 0 else 10
        pdf.image(logo_msp_path, x=logo_x, y=logo_y, w=logo_w)
    except Exception as logo_error:
        print(f"ADVERTENCIA: No se pudo añadir el logo MSP al PDF: {logo_error}")
        logo_h_approx = 10

    # Título del reporte
    pdf.set_font(unicode_font, 'B', 14)  # Título más grande y en negrita
    title_x_start = logo_x + logo_w + 5
    font_size_mm = pdf.font_size_pt / 72 * 25.4
    title_y_final = max(logo_y, logo_y + (logo_h_approx / 2) - (font_size_mm / 2))

    pdf.set_xy(title_x_start, title_y_final)
    available_width_for_title = pdf.w - title_x_start - pdf.r_margin
    pdf.cell(available_width_for_title, 10, txt=titulo, align="C")

    # Línea separadora
    header_bottom_y = max(logo_y + logo_h_approx, title_y_final + 10)
    pdf.set_y(header_bottom_y + 3)

    if dataframe_filtrado.empty:
        pdf.ln(10)
        pdf.set_font(unicode_font, size=12)
        pdf.cell(0, 10, txt="No se encontraron registros para este reporte.", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    else:
        df_para_pdf = dataframe_filtrado.copy()
        columnas = df_para_pdf.columns.tolist()

        # --- Cálculo de anchos de columna ---
        ancho_total_disponible = pdf.w - pdf.l_margin - pdf.r_margin
        column_proportions = {
            '#': 0.5,
            'CEDULA': 1.0,
            'NOMBRES Y APELLIDOS': 3.0,
            'UBICACION': 2.0,
            '_default_': 2.0
        }
        num_cols = len(columnas)
        total_proportion = sum(column_proportions.get(col, column_proportions['_default_']) for col in columnas)
        calculated_widths = {col: (column_proportions.get(col, column_proportions['_default_']) / total_proportion) * ancho_total_disponible for col in columnas}

        # --- Dibujar encabezado de la tabla ---
        pdf.set_font(unicode_font, 'B', 12)
        y_inicial_header_calc = pdf.get_y()
        line_height_header = 8
        max_altura_header = line_height_header

        for col in columnas:
            header_text = str(col).replace('_', ' ').replace('\n', ' ').title()
            ancho_actual = calculated_widths.get(col, 10)
            if ancho_actual <= 0:
                ancho_actual = 10
            texto_lineas_header_dry = pdf.multi_cell(ancho_actual, line_height_header, txt=header_text, border=0, align="C", dry_run=True, output='LINES')
            altura_header_necesaria = len(texto_lineas_header_dry) * line_height_header
            max_altura_header = max(max_altura_header, altura_header_necesaria)

        pdf.set_y(y_inicial_header_calc)
        x_actual_header = pdf.l_margin
        for col in columnas:
            header_text = str(col).replace('_', ' ').replace('\n', ' ').title()
            ancho_actual = calculated_widths.get(col, 10)
            if ancho_actual <= 0:
                ancho_actual = 10
            pdf.set_xy(x_actual_header, y_inicial_header_calc)
            pdf.multi_cell(ancho_actual, line_height_header, txt=header_text, border=0, align="C", new_x=XPos.LMARGIN, new_y=YPos.TOP)
            pdf.rect(x_actual_header, y_inicial_header_calc, ancho_actual, max_altura_header)
            x_actual_header += ancho_actual
        pdf.ln(max_altura_header)

        # --- Dibujar filas de datos ---
        pdf.set_font(unicode_font, size=9)
        line_height = 7

        for index, row in df_para_pdf.iterrows():
            max_altura_fila = line_height
            for col in columnas:
                valor = format_value_for_display(row.get(col), column_name=col)
                ancho_actual = calculated_widths.get(col, 10)
                if ancho_actual <= 0:
                    ancho_actual = 10
                try:
                    texto_lineas_dry = pdf.multi_cell(ancho_actual, line_height, txt=valor, border=0, align='L', dry_run=True, output='LINES')
                    altura_necesaria = len(texto_lineas_dry) * line_height
                except Exception as cell_calc_err:
                    print(f"Advertencia: Error calculando altura de celda para '{col}': {cell_calc_err}")
                    altura_necesaria = line_height
                max_altura_fila = max(max_altura_fila, altura_necesaria)
            max_altura_fila = max(max_altura_fila, line_height)

            y_antes_fila = pdf.get_y()
            if y_antes_fila + max_altura_fila > pdf.page_break_trigger:
                pdf.add_page()
                if watermark_stream_obj:
                    try:
                        watermark_stream_obj.seek(0)
                        page_w_mm_new = pdf.w
                        page_h_mm_new = pdf.h
                        wm_h_mm_new = wm_w_mm_global * aspect_ratio_global
                        wm_x_mm_new = (page_w_mm_new - wm_w_mm_global) / 2
                        wm_y_mm_new = (page_h_mm_new - wm_h_mm_new) / 2
                        pdf.image(watermark_stream_obj, x=wm_x_mm_new, y=wm_y_mm_new, w=wm_w_mm_global, type='PNG')
                        print("DEBUG: Marca de agua PDF añadida (nueva página)")
                    except Exception as wm_err_new:
                        print(f"Error añadiendo marca de agua en nueva página: {wm_err_new}")

                try:
                    pdf.image(logo_msp_path, x=logo_x, y=logo_y, w=logo_w)
                except Exception as logo_error_new_page:
                    print(f"ADVERTENCIA: No se pudo añadir el logo MSP al PDF (nueva página): {logo_error_new_page}")

                pdf.set_font(unicode_font, 'B', 14)
                pdf.set_xy(title_x_start, title_y_final)
                pdf.cell(available_width_for_title, 10, txt=titulo, align="C")

                pdf.set_font(unicode_font, 'B', 12)
                header_start_y_new_page = max(logo_y + logo_h_approx, pdf.get_y()) + 3
                pdf.set_y(header_start_y_new_page)
                x_actual_header_new = pdf.l_margin
                for col_h in columnas:
                    ancho_actual_h = calculated_widths.get(col_h, 10)
                    if ancho_actual_h <= 0:
                        ancho_actual_h = 10
                    header_text_h = str(col_h).replace('_', ' ').replace('\n', ' ').title()
                    pdf.set_xy(x_actual_header_new, header_start_y_new_page)
                    pdf.multi_cell(ancho_actual_h, line_height_header, txt=header_text_h, border=0, align="C", new_x=XPos.LMARGIN, new_y=YPos.TOP)
                    pdf.rect(x_actual_header_new, header_start_y_new_page, ancho_actual_h, max_altura_header)
                    x_actual_header_new += ancho_actual_h
                pdf.ln(max_altura_header)
                pdf.set_font(unicode_font, size=9)
                y_antes_fila = pdf.get_y()

            current_x_border = pdf.l_margin
            for col in columnas:
                ancho_actual = calculated_widths.get(col, 10)
                if ancho_actual <= 0:
                    ancho_actual = 10
                pdf.rect(current_x_border, y_antes_fila, ancho_actual, max_altura_fila)
                current_x_border += ancho_actual

            current_x_text = pdf.l_margin
            text_padding = 1
            for col in columnas:
                valor = format_value_for_display(row.get(col), column_name=col)
                ancho_actual = calculated_widths.get(col, 10)
                if ancho_actual <= 0:
                    ancho_actual = 10
                pdf.set_xy(current_x_text + text_padding, y_antes_fila + text_padding)
                pdf.multi_cell(ancho_actual - 2 * text_padding, line_height, txt=valor, border=0, align="L")
                current_x_text += ancho_actual
            pdf.set_y(y_antes_fila + max_altura_fila)

    filepath = os.path.join(reports_folder, filename)
    try:
        pdf.output(filepath)
        print(f"DEBUG: Reporte PDF de PDLs sin foto generado en {filepath}")
        if watermark_stream_obj:
            watermark_stream_obj.close()
        return filepath
    except Exception as e:
        print(f"Error al guardar PDF: {e}")
        if watermark_stream_obj:
            watermark_stream_obj.close()
        raise

# --- Función para Generar Ficha Jurídica en JPG ---
def generar_ficha_jpg(datos_privado, cedula_str, filename):
    """Genera un archivo JPG con la ficha jurídica."""
    reports_folder = current_app.config['REPORTS_FOLDER']
    resources_folder = current_app.config['RESOURCES_FOLDER']
    photos_folder = current_app.config['PHOTOS_FOLDER']
    project_folder = os.path.dirname(current_app.root_path) # Obtener ruta base del proyecto

    output_path = os.path.join(reports_folder, filename)

    img_width = 900
    img_height = 763
    background_color = (255, 255, 255)
    text_color = (0, 0, 0)
    try:
        font_data_label = ImageFont.load_default().font_variant(size=14)
        font_data_value = ImageFont.load_default().font_variant(size=14)
        font_static_header = ImageFont.load_default().font_variant(size=18)
        font_main_title = ImageFont.load_default().font_variant(size=24)
        bold_font_path = os.path.join(project_folder, "arialbd.ttf") # Asume que arialbd.ttf está en la carpeta SIIP
        font_header_bold = ImageFont.truetype(bold_font_path, 24)
        font_data_value_bold = ImageFont.truetype(bold_font_path, 14)
        font_static_bold = ImageFont.truetype(bold_font_path, 18)
    except IOError:
        print(f"Advertencia: Fuente bold '{bold_font_path}' no encontrada, usando fuente por defecto.")
        font_main_title = ImageFont.load_default().font_variant(size=24)
        font_static_header = ImageFont.load_default().font_variant(size=18)
        font_data_label = ImageFont.load_default().font_variant(size=14)
        font_data_value = ImageFont.load_default().font_variant(size=14)
        font_header_bold = font_main_title
        font_data_value_bold = font_data_value
        font_static_bold = font_static_header

    img = Image.new('RGB', (img_width, img_height), color=background_color)
    draw = ImageDraw.Draw(img)

    watermark_path = os.path.join(resources_folder, "LOGO.png")
    try:
        watermark_logo = Image.open(watermark_path).convert("RGBA")
        base_width = 350
        w_percent = (base_width / float(watermark_logo.size[0])) if watermark_logo.size[0] > 0 else 1.0
        h_size = int((float(watermark_logo.size[1]) * float(w_percent)))
        watermark_logo = watermark_logo.resize((base_width, h_size), Image.Resampling.LANCZOS)
        alpha = 100
        watermark_logo_transparent = Image.new("RGBA", watermark_logo.size)
        for x in range(watermark_logo.width):
            for y in range(watermark_logo.height):
                r, g, b, a_orig = watermark_logo.getpixel((x, y))
                new_alpha = int(a_orig * (alpha / 255.0)) if a_orig > 0 else 0
                watermark_logo_transparent.putpixel((x, y), (r, g, b, new_alpha))
        wm_x = (img_width - watermark_logo_transparent.width) // 2
        wm_y = (img_height - watermark_logo_transparent.height) // 2
        img.paste(watermark_logo_transparent, (wm_x, wm_y), watermark_logo_transparent)
        print(f"DEBUG: Marca de agua JPG pegada desde {watermark_path}")
    except FileNotFoundError:
        print(f"ERROR: No se encontró el archivo de marca de agua JPG en {watermark_path}")
    except Exception as wm_error:
        print(f"Error al procesar o pegar la marca de agua JPG: {wm_error}")

    draw.text((227, 116), "SITUACIÓN JURÍDICA", fill=text_color, font=font_header_bold)

    photo_x = 650
    photo_y = 30
    photo_max_width = 200
    photo_max_height = 250
    draw.rectangle([photo_x, photo_y, photo_x + photo_max_width, photo_y + photo_max_height], fill='white')
    photo_found_path = None
    possible_photo_names = [f"v-{cedula_str}.jpg", f"e-{cedula_str}.jpg", f"{cedula_str}.jpg"]
    for name in possible_photo_names:
        potential_path = os.path.join(photos_folder, name)
        if os.path.exists(potential_path):
            photo_found_path = potential_path
            break
    try:
        if photo_found_path:
            inmate_photo = Image.open(photo_found_path)
            inmate_photo.thumbnail((photo_max_width, photo_max_height))
            paste_x = photo_x + (photo_max_width - inmate_photo.width) // 2
            paste_y = photo_y + (photo_max_height - inmate_photo.height) // 2
            img.paste(inmate_photo, (paste_x, paste_y))
        else:
            raise FileNotFoundError
    except FileNotFoundError:
        default_photo_path = os.path.join(photos_folder, "NO_DISPONIBLE.jpg")
        try:
            default_photo = Image.open(default_photo_path)
            default_photo.thumbnail((photo_max_width, photo_max_height))
            paste_x = photo_x + (photo_max_width - default_photo.width) // 2
            paste_y = photo_y + (photo_max_height - default_photo.height) // 2
            img.paste(default_photo, (paste_x, paste_y))
        except FileNotFoundError:
            draw.rectangle([photo_x, photo_y, photo_x + photo_max_width, photo_y + photo_max_height], outline=text_color)
            draw.text((photo_x + 10, photo_y + 10), "Foto no disponible", fill=text_color, font=font_data_value)
    except Exception as e:
        draw.rectangle([photo_x, photo_y, photo_x + photo_max_width, photo_y + photo_max_height], outline=(255,0,0))
        draw.text((photo_x + 10, photo_y + 10), "Error foto", fill=(255,0,0), font=font_data_value)

    encabezado_path = os.path.join(resources_folder, "encabezado.png")
    try:
        encabezado_img = Image.open(encabezado_path).convert("RGBA")
        img.paste(encabezado_img, (50, 10), encabezado_img)
    except FileNotFoundError:
        print(f"ERROR: No se encontró la imagen de encabezado en {encabezado_path}")
    draw.text((58, 90), "CENTRO DE FORMACIÓN HOMBRE NUEVO EL LIBERTADOR", font=font_static_bold, fill="black")

    def draw_field(label_coord, label_text, col_name, value_x_coord, draw_value_box=True, max_value_width=None):
        label_x, label_y = label_coord
        padding = 6
        border_width = 2
        line_spacing = 4
        value_y = label_y
        value_x = value_x_coord
        clean_label = label_text.replace(':', '').replace(';', '').replace('}', '').replace(']', '').replace('|', '').strip()
        draw.text(xy=(label_x, label_y), text=f"{clean_label}:", fill=text_color, font=font_data_value_bold)
        raw_value = datos_privado.get(col_name)
        value_str = format_value_for_display(raw_value, column_name=col_name)
        if not value_str: value_str = "NO REGISTRA"
        lines = []
        needs_wrapping = False
        actual_text_width = 0
        if '\n' in value_str:
            needs_wrapping = True
            lines = value_str.split('\n')
            for line in lines: actual_text_width = max(actual_text_width, draw.textlength(line, font=font_data_value_bold))
        else:
            original_text_width = draw.textlength(value_str, font=font_data_value_bold)
            needs_wrapping = max_value_width is not None and original_text_width > max_value_width
        if needs_wrapping:
            if not lines:
                words = value_str.split()
                lines = []
                current_line = ""
                for word in words:
                    test_line = f"{current_line} {word}".strip()
                    if draw.textlength(test_line, font=font_data_value_bold) <= max_value_width:
                        current_line = test_line
                    else:
                        if current_line: lines.append(current_line)
                        if draw.textlength(word, font=font_data_value_bold) > max_value_width:
                            lines.append(word)
                            current_line = ""
                        else: current_line = word
                if current_line: lines.append(current_line)
            if not actual_text_width:
                for line in lines: actual_text_width = max(actual_text_width, draw.textlength(line, font=font_data_value_bold))
            line_height_font = font_data_value_bold.getbbox("A")[3] - font_data_value_bold.getbbox("A")[1]
            total_text_height = len(lines) * line_height_font + (len(lines) - 1) * line_spacing
            if draw_value_box:
                box_x0 = value_x - padding
                box_y0 = value_y - padding
                actual_box_width = max_value_width if max_value_width else actual_text_width
                box_x1 = value_x + actual_box_width + padding
                box_y1 = value_y + total_text_height + padding
                draw.rectangle([box_x0, box_y0, box_x1, box_y1], outline=text_color, width=border_width)
            current_y = value_y
            for line in lines:
                line_width = draw.textlength(line, font=font_data_value_bold)
                centered_line_x = value_x + (actual_box_width - line_width) // 2
                draw.text((centered_line_x, current_y), line, fill=text_color, font=font_data_value_bold)
                current_y += line_height_font + line_spacing
        else:
            if draw_value_box:
                try:
                    bbox = draw.textbbox((value_x, value_y), value_str, font=font_data_value_bold)
                    draw.rectangle([bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding], outline=text_color, width=border_width)
                    box_width_single = (bbox[2] + padding) - (bbox[0] - padding)
                    text_width_single = draw.textlength(value_str, font=font_data_value_bold)
                    centered_text_x = (bbox[0] - padding) + (box_width_single - text_width_single) // 2
                    draw.text((centered_text_x, value_y), value_str, fill=text_color, font=font_data_value_bold)
                except ValueError: pass
            else: draw.text((value_x, value_y), value_str, fill=text_color, font=font_data_value_bold)

    left_col_x = 40
    mid_col_x = 290
    right_col_x = 560
    y_start = 260
    y_step = 50
    padding = 6
    col1_value_start_x = 160
    col3_value_start_x = 670
    wrap_fields = ["PROCEDENCIA", "CIRCUITO_JUDICIAL", "REDENCIONES_COMPUTADAS", "UBICACION", "TIEMPO_FISICO", "TIEMPO_FISICO_MAS_RED"]
    campos_layout = {
        "CEDULA": ((left_col_x, y_start + 0*y_step), "CEDULA", "CEDULA"),
        "FECHA_NACIMIENTO": ((left_col_x, y_start + 1*y_step), "FECHA DE\nNACIMIENTO:", "FECHA DE NACIMIENTO"),
        "EDAD": ((left_col_x, y_start + 2*y_step), "EDAD", "EDAD"),
        "NACIONALIDAD": ((left_col_x, y_start + 3*y_step), "NACIONALIDAD", "NACIONALIDAD"),
        "NIVEL_ACADEMICO": ((left_col_x, y_start + 4*y_step), "GRADO DE\nINSTRUCCIÓN:", "NIVEL ACADEMICO"),
        "OFICIO": ((left_col_x, y_start + 5*y_step), "PROFESIÓN\nU OFICIO:", "OFICIO"),
        "UBICACION": ((left_col_x, y_start + 6*y_step), "UBICACIÓN", "UBICACION"),
        "REDENCIONES_COMPUTADAS": ((left_col_x, y_start + 7*y_step), "REDENCIONES\nCOMPUTADAS:", "REDENCIONES COMPUTADAS"),
        "ESTATUS": ((left_col_x, y_start + 8*y_step), "ESTATUS", "ESTATUS"),
        "EXP_INTERNO": ((mid_col_x, y_start + 0*y_step), "EXP. INTERNO", "EXPEDIENTE INTERNO"),
        "FECHA_DETENCION": ((mid_col_x, y_start + 1*y_step), "FECHA DE\nDETENCIÓN:", "FECHA DE DETENCION"),
        "FECHA_INGRESO": ((mid_col_x, y_start + 2*y_step), "FECHA DE\nINGRESO:", "FECHA DE INGRESO"),
        "NUM_EXPEDIENTE": ((mid_col_x, y_start + 3*y_step), "N° EXPEDIENTE", "NUMERO DE EXPEDIENTE"),
        "FECHA_PSICOSOCIAL": ((mid_col_x, y_start + 4*y_step), "FECHA\nPSICOSOCIAL:", "FECHA PSICOSOCIAL"),
        "PORC_FISICO_SIN_RED": ((mid_col_x, y_start + 5*y_step), "% FISICO\nCUMPLIDO:", "PORCENTAJE FISICO CUMPLIDO"),
        "TIEMPO_FISICO": ((mid_col_x, y_start + 6*y_step), "TIEMPO FÍSICO:", "TIEMPO FISICO"),
        "PORC_FISICO_CON_RED": ((mid_col_x, y_start + 7*y_step), "% FISICO CON\nREDENCIONES:", "PORCENTAJE CUMPLIDO CON REDENCION"),
        "TIEMPO_FISICO_MAS_RED": ((mid_col_x, y_start + 8*y_step), "TIEMPO FISICO\n+ REDENCIÓN:", "TIEMPO FISICO CON REDENCIONES"),
        "CONDICION_JURIDICA": ((right_col_x, y_start + 1*y_step), "CONDICIÓN\nJURÍDICA:", "CONDICION JURIDICA"),
        "TIEMPO_PENA": ((right_col_x, y_start + 2*y_step), "PENA", "TIEMPO DE PENA"),
        "NUMERO_TRIBUNAL": ((right_col_x, y_start + 3*y_step), "TRIBUNAL", "NUMERO DE TRIBUNAL"),
        "CIRCUITO_JUDICIAL": ((right_col_x, y_start + 4*y_step), "CIRCUITO\nJUDICIAL:", "CIRCUITO JUDICIAL"),
        "EXTENSION": ((right_col_x, y_start + 5*y_step), "EXTENSIÓN", "EXTENSION"),
        "FASE_PROCESO": ((right_col_x, y_start + 6*y_step), "FASE DEL\nPROCESO:", "FASE DEL PROCESO"),
        "PROCEDENCIA": ((right_col_x, y_start + 7*y_step), "PROCEDENCIA\nCARCELARIA:", "PROCEDENCIA"),
    }

    max_width_col1 = mid_col_x - col1_value_start_x - 2*padding - 10
    max_width_col2 = right_col_x - mid_col_x - 120 - 2*padding - 10
    max_width_col3 = img_width - col3_value_start_x - 2*padding - 15

    date_label_coord = (60, 170)
    date_value_offset = 70
    date_label_text = "FECHA"
    try: today_str = date.today().strftime('%d/%m/%Y')
    except Exception: today_str = "Error Fecha"
    draw.text(date_label_coord, f"{date_label_text}:", fill=text_color, font=font_data_value_bold)
    date_value_x = date_label_coord[0] + date_value_offset
    date_value_y = date_label_coord[1]
    try:
        date_bbox = draw.textbbox((date_value_x, date_value_y), today_str, font=font_data_value_bold)
        padding_date = 6
        border_width_date = 2
        draw.rectangle([date_bbox[0] - padding_date, date_bbox[1] - padding_date, date_bbox[2] + padding_date, date_bbox[3] + padding_date], outline=text_color, width=border_width_date)
        draw.text((date_value_x, date_value_y), today_str, fill=text_color, font=font_data_value_bold)
    except ValueError: pass

    nombre_coord_y = 210
    nombre_col = "NOMBRES Y APELLIDOS"
    nombre_str = format_value_for_display(datos_privado.get(nombre_col))
    if not nombre_str: nombre_str = "NO REGISTRA"
    if nombre_str:
        try:
            nombre_coord_x = 100
            name_bbox = draw.textbbox((nombre_coord_x, nombre_coord_y), nombre_str, font=font_header_bold)
            padding_name = 6
            draw.text((nombre_coord_x, nombre_coord_y), nombre_str, fill=text_color, font=font_header_bold)
            draw.rectangle([name_bbox[0] - padding_name, name_bbox[1] - padding_name, name_bbox[2] + padding_name, name_bbox[3] + padding_name], outline=text_color, width=2)
        except ValueError: pass

    delito_box_coords = [20, 710, 880, 750]
    draw.rectangle(delito_box_coords, outline=text_color, width=2)

    for key, (coords, label, col_name) in campos_layout.items():
        if col_name:
            should_draw_box = (key != "DELITO")
            current_max_width = None
            value_x_coord = 0
            if coords[0] < mid_col_x:
                value_x_coord = col1_value_start_x
                if key in wrap_fields: current_max_width = max_width_col1
            elif coords[0] < right_col_x:
                offset = 120 # Default offset for second column values
                value_x_coord = coords[0] + offset # Calculate value x based on label x + offset
                if key in wrap_fields: current_max_width = max_width_col2
            else:
                offset = 100 # Default offset for third column values
                value_x_coord = col3_value_start_x # Use fixed start for third column
                if key in wrap_fields: current_max_width = max_width_col3
            # Ensure value_x_coord is set if not calculated above (shouldn't happen with current layout)
            if not value_x_coord: value_x_coord = coords[0] + 120 # Fallback offset

            draw_field(coords, label, col_name, value_x_coord=value_x_coord, draw_value_box=should_draw_box, max_value_width=current_max_width)

    delito_label_coord = (44, 720)
    delito_col_name = "DELITO DE EXPEDIENTE"
    delito_label_text = "DELITO"
    draw.text((delito_label_coord[0], delito_label_coord[1]), f"{delito_label_text}:", fill=text_color, font=font_data_value_bold)
    raw_delito_value = datos_privado.get(delito_col_name)
    delito_value_str = format_value_for_display(raw_delito_value, column_name=delito_col_name)
    if not delito_value_str: delito_value_str = "NO REGISTRA"
    delito_box_width = delito_box_coords[2] - delito_box_coords[0]
    label_width_approx = 60
    max_delito_width = delito_box_width - label_width_approx - 20
    line_spacing = 4
    words = delito_value_str.split()
    delito_lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        if draw.textlength(test_line, font=font_data_value_bold) <= max_delito_width:
            current_line = test_line
        else:
            if current_line: delito_lines.append(current_line)
            if draw.textlength(word, font=font_data_value_bold) > max_delito_width:
                 delito_lines.append(word)
                 current_line = ""
            else: current_line = word
    if current_line: delito_lines.append(current_line)
    line_height_font = font_data_value_bold.getbbox("A")[3] - font_data_value_bold.getbbox("A")[1]
    total_delito_height = len(delito_lines) * line_height_font + (len(delito_lines) - 1) * line_spacing
    delito_box_height = delito_box_coords[3] - delito_box_coords[1]
    start_y_delito = delito_box_coords[1] + (delito_box_height - total_delito_height) // 2
    start_y_delito = max(start_y_delito, delito_box_coords[1] + 2)
    current_y = start_y_delito
    for line in delito_lines:
        line_width = draw.textlength(line, font=font_data_value_bold)
        available_width_for_text = max_delito_width
        centered_line_x = delito_box_coords[0] + label_width_approx + 10 + (available_width_for_text - line_width) // 2
        draw.text((centered_line_x, current_y), line, fill=text_color, font=font_data_value_bold)
        current_y += line_height_font + line_spacing

    try:
        img.save(output_path, "JPEG")
        print(f"DEBUG: Ficha JPG generada en {output_path}")
        return output_path
    except Exception as e:
        print(f"Error al guardar ficha JPG: {e}")
        raise
