"""
Módulo para generar e imprimir comandas térmicas en papel de 80mm
"""
import os
import socket
import time
from datetime import datetime
from flask import current_app
from fpdf import FPDF
from .models import (
    PedidoPanaderia,
    ItemPedidoPanaderia,
    ClientePanaderia,
    User,
    MensajeCocina,
    ProductoPanaderia,
)
from .extensions import db

def generar_comanda_escpos(pedido_id):
    """
    Genera el código ESC/POS para imprimir una comanda de pedido.
    
    Args:
        pedido_id: ID del pedido en la base de datos
        
    Returns:
        bytes: Código ESC/POS listo para imprimir
    """
    # Obtener pedido de la base de datos
    pedido = PedidoPanaderia.query.get(pedido_id)
    if not pedido:
        raise ValueError(f"Pedido {pedido_id} no encontrado")
    
    # Inicializar comando ESC/POS
    comando = bytearray()
    
    # Reset de impresora
    comando.extend(b'\x1B\x40')
    
    # Configuración inicial - TODO CENTRADO
    comando.extend(b'\x1B\x61\x01')  # Centrar
    
    # Encabezado - TEXTO MÁS GRANDE
    comando.extend(b'\x1B\x21\x38')  # Texto grande y negrita
    comando.extend('PANADERIA\n'.encode('utf-8'))
    comando.extend(b'\x1B\x21\x00')  # Reset formato
    
    comando.extend(('=' * 32 + '\n').encode('utf-8'))
    
    # Información del pedido - CENTRADO
    comando.extend(b'\x1B\x21\x08')  # Negrita
    comando.extend(f'PEDIDO: {pedido.numero_pedido}\n'.encode('utf-8'))
    comando.extend(b'\x1B\x21\x00')
    # Formato AM/PM
    fecha_formateada = pedido.fecha_pedido.strftime("%d/%m/%Y %I:%M %p")
    comando.extend(f'Fecha: {fecha_formateada}\n'.encode('utf-8'))
    comando.extend(('-' * 32 + '\n').encode('utf-8'))
    
    # Información del cliente - OPTIMIZADO - SIN LÍNEAS VACÍAS INNECESARIAS
    comando.extend(b'\x1B\x21\x08')  # Negrita
    cliente_str = f'CLIENTE: {pedido.cliente.nombre}'
    # Truncar si es muy largo para caber en una línea
    if len(cliente_str) > 32:
        cliente_str = cliente_str[:29] + '...'
    comando.extend(f'{cliente_str}\n'.encode('utf-8'))
    comando.extend(b'\x1B\x21\x00')
    
    # UBICACION con dirección en segunda línea
    if pedido.cliente.direccion:
        ubicacion_str = f'UBICACION: {pedido.cliente.direccion}'
        if len(ubicacion_str) > 32:
            ubicacion_str = ubicacion_str[:29] + '...'
        comando.extend(f'{ubicacion_str}\n'.encode('utf-8'))
    
    comando.extend(('-' * 32 + '\n').encode('utf-8'))
    
    # Items del pedido - CENTRADO
    comando.extend(b'\x1B\x21\x08')
    comando.extend('DETALLE:\n'.encode('utf-8'))
    comando.extend(b'\x1B\x21\x00')
    comando.extend(('-' * 32 + '\n').encode('utf-8'))
    
    # Cargar items del pedido
    items = ItemPedidoPanaderia.query.filter_by(pedido_id=pedido.id).all()
    
    for idx, item in enumerate(items, 1):
        # Nombre del producto - TAMAÑO NORMAL - SIN CONTADOR
        producto_nombre = item.producto.nombre
        if len(producto_nombre) > 28:
            producto_nombre = producto_nombre[:25] + '...'
        comando.extend(f'{producto_nombre}\n'.encode('utf-8'))
        
        # Cantidad y precio - CENTRADO con separadores de miles (formato Venezuela: 1.234.567,89)
        precio_formatted = f"{item.precio_unitario:,.2f}"
        if '.' in precio_formatted:
            parts = precio_formatted.split('.')
            precio_unitario_formateado = parts[0].replace(',', '.') + ',' + parts[1]
        else:
            precio_unitario_formateado = precio_formatted.replace(',', '.')
        cantidad_str = f'Cantidad: {item.cantidad} x {precio_unitario_formateado} Bs.'
        comando.extend(cantidad_str.encode('utf-8'))
        comando.extend('\n'.encode('utf-8'))
        
        # Subtotal - CENTRADO con separadores de miles
        subtotal_formatted = f"{item.subtotal:,.2f}"
        if '.' in subtotal_formatted:
            parts = subtotal_formatted.split('.')
            subtotal_formateado = parts[0].replace(',', '.') + ',' + parts[1]
        else:
            subtotal_formateado = subtotal_formatted.replace(',', '.')
        subtotal_str = f'{subtotal_formateado} Bs.'
        comando.extend(b'\x1B\x21\x08')  # Negrita
        comando.extend(subtotal_str.encode('utf-8'))
        comando.extend(b'\x1B\x21\x00')  # Reset
        comando.extend('\n'.encode('utf-8'))
    
    # Total - CENTRADO con separadores de miles
    comando.extend('\n'.encode('utf-8'))
    comando.extend(('-' * 32 + '\n').encode('utf-8'))
    comando.extend(b'\x1B\x21\x08')  # Negrita
    total_formatted = f"{pedido.total:,.2f}"
    if '.' in total_formatted:
        parts = total_formatted.split('.')
        total_formateado = parts[0].replace(',', '.') + ',' + parts[1]
    else:
        total_formateado = total_formatted.replace(',', '.')
    total_str = f'TOTAL: {total_formateado} Bs.'
    comando.extend(total_str.encode('utf-8'))
    comando.extend(b'\x1B\x21\x00')  # Reset
    comando.extend('\n'.encode('utf-8'))
    
    # Observaciones si existen - OPTIMIZADO
    if pedido.observaciones:
        comando.extend(('-' * 32 + '\n').encode('utf-8'))
        comando.extend(b'\x1B\x21\x08')  # Negrita
        comando.extend('OBSERVACIONES:\n'.encode('utf-8'))
        comando.extend(b'\x1B\x21\x00')
        # Dividir observaciones en líneas de máximo 32 caracteres
        obs_lines = [pedido.observaciones[i:i+32] for i in range(0, len(pedido.observaciones), 32)]
        for line in obs_lines:
            comando.extend(line.encode('utf-8'))
            comando.extend('\n'.encode('utf-8'))
        comando.extend(('-' * 32 + '\n').encode('utf-8'))
    
    # Usuario que hizo el pedido
    if pedido.usuario:
        usuario_str = f'Pedido por: {pedido.usuario.nombre_completo}'
        if len(usuario_str) > 32:
            usuario_str = usuario_str[:29] + '...'
        comando.extend(f'{usuario_str}\n'.encode('utf-8'))
        comando.extend(('-' * 32 + '\n').encode('utf-8'))
    
    # Pie de comanda - OPTIMIZADO
    comando.extend('\n'.encode('utf-8'))
    comando.extend('Gracias por su compra!\n'.encode('utf-8'))
    comando.extend('\n'.encode('utf-8'))
    
    # Cortar papel
    comando.extend(b'\x1D\x56\x00')  # Corte parcial
    
    return bytes(comando)

def imprimir_comanda(pedido_id):
    """
    Envía una comanda a la impresora térmica por red.
    
    Args:
        pedido_id: ID del pedido a imprimir
        
    Returns:
        dict: Resultado de la impresión
    """
    if not current_app.config.get('IMPRESORA_HABILITADA', False):
        current_app.logger.info("Impresora deshabilitada en configuración")
        return {
            'success': False,
            'skipped': True,
            'message': 'Impresora deshabilitada'
        }
    
    impresora_ip = current_app.config.get('IMPRESORA_IP', '192.168.1.100')
    impresora_puerto = current_app.config.get('IMPRESORA_PUERTO', 9100)
    
    try:
        # Generar código ESC/POS
        comando_escpos = generar_comanda_escpos(pedido_id)
        
        # Enviar a impresora por socket TCP
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # Timeout de 5 segundos
        
        current_app.logger.info(f"Intentando imprimir en {impresora_ip}:{impresora_puerto}")
        sock.connect((impresora_ip, impresora_puerto))
        
        # Enviar comando
        sock.sendall(comando_escpos)
        
        # Cerrar conexión
        sock.close()
        
        current_app.logger.info(f"Comanda imprimida exitosamente para pedido {pedido_id}")
        return {
            'success': True,
            'message': 'Comanda imprimida exitosamente'
        }
        
    except socket.timeout:
        current_app.logger.error(f"Timeout conectando a impresora {impresora_ip}:{impresora_puerto}")
        # Generar PDF como fallback
        try:
            pdf_path = generar_comanda_pdf(pedido_id)
            current_app.logger.info(f"PDF generado como fallback: {pdf_path}")
            return {
                'success': True,
                'fallback_pdf': True,
                'pdf_path': pdf_path,
                'message': 'No se pudo conectar a la impresora. Se generó un PDF para descarga.'
            }
        except Exception as pdf_error:
            current_app.logger.error(f"Error generando PDF de fallback: {pdf_error}", exc_info=True)
            return {
                'success': False,
                'error': 'Error conectando a la impresora y generando PDF'
            }
    except socket.error as e:
        current_app.logger.error(f"Error de conexión con impresora: {e}")
        # Generar PDF como fallback
        try:
            pdf_path = generar_comanda_pdf(pedido_id)
            current_app.logger.info(f"PDF generado como fallback: {pdf_path}")
            return {
                'success': True,
                'fallback_pdf': True,
                'pdf_path': pdf_path,
                'message': 'No se pudo conectar a la impresora. Se generó un PDF para descarga.'
            }
        except Exception as pdf_error:
            current_app.logger.error(f"Error generando PDF de fallback: {pdf_error}", exc_info=True)
            return {
                'success': False,
                'error': 'Error conectando a la impresora y generando PDF'
            }
    except Exception as e:
        current_app.logger.error(f"Error imprimiendo comanda: {e}", exc_info=True)
        return {
            'success': False,
            'error': f'Error al imprimir: {str(e)}'
        }

def obtener_comanda_raw(pedido_id):
    """
    Obtiene el código ESC/POS sin imprimir (útil para debugging o impresión manual).
    
    Args:
        pedido_id: ID del pedido
        
    Returns:
        bytes: Código ESC/POS
    """
    return generar_comanda_escpos(pedido_id)

def imprimir_reporte_escpos(tipo_reporte, reporte_data, total_general, fecha_inicio='', fecha_fin='', filtro_estado='ENTREGADO_PAGADO'):
    """
    Genera el código ESC/POS para imprimir un reporte de ventas.
    
    Args:
        tipo_reporte: 'vendedor' o 'producto'
        reporte_data: Lista de diccionarios con datos del reporte
        total_general: Total general de ventas
        fecha_inicio: Fecha de inicio del reporte
        fecha_fin: Fecha de fin del reporte
        filtro_estado: Estado del filtro aplicado
        
    Returns:
        bytes: Código ESC/POS listo para imprimir
    """
    # Ancho de línea para impresora 80mm (48 caracteres)
    ancho_linea = 48
    
    # Función helper para formatear números con separadores de miles
    def formatear_numero(num):
        return f"{num:,.0f}"
    
    # Inicializar comando ESC/POS
    comando = bytearray()
    
    # Reset de impresora
    comando.extend(b'\x1B\x40')
    
    # Configuración inicial
    comando.extend(b'\x1B\x61\x01')  # Centrar
    
    # Encabezado
    comando.extend(b'\x1B\x21\x38')  # Texto grande y negrita
    comando.extend('REPORTE DE VENTAS\n'.encode('utf-8'))
    comando.extend(b'\x1B\x21\x00')  # Reset formato
    
    comando.extend(b'\x1B\x61\x01')  # Centrar
    comando.extend(('=' * ancho_linea + '\n').encode('utf-8'))
    comando.extend(b'\x1B\x61\x00')  # Izquierda
    
    # Fechas
    if fecha_inicio or fecha_fin:
        comando.extend('\n'.encode('utf-8'))
        if fecha_inicio and fecha_fin:
            comando.extend(f'Periodo: {fecha_inicio} a {fecha_fin}\n'.encode('utf-8'))
        elif fecha_inicio:
            comando.extend(f'Desde: {fecha_inicio}\n'.encode('utf-8'))
        elif fecha_fin:
            comando.extend(f'Hasta: {fecha_fin}\n'.encode('utf-8'))
        comando.extend(('-' * ancho_linea + '\n').encode('utf-8'))
    
    comando.extend('\n'.encode('utf-8'))
    
    # Tipo de reporte
    comando.extend(b'\x1B\x61\x01')  # Centrar
    comando.extend(b'\x1B\x21\x10')  # Negrita
    if tipo_reporte == 'vendedor':
        comando.extend('VENTAS POR CLIENTE\n'.encode('utf-8'))
    else:
        comando.extend('VENTAS POR PRODUCTO\n'.encode('utf-8'))
    comando.extend(b'\x1B\x21\x00')  # Reset
    comando.extend(b'\x1B\x61\x00')  # Izquierda
    comando.extend(('-' * ancho_linea + '\n').encode('utf-8'))
    comando.extend('\n'.encode('utf-8'))
    
    # Datos del reporte
    if tipo_reporte == 'vendedor':
        for idx, item in enumerate(reporte_data, 1):
            comando.extend(b'\x1B\x21\x08')  # Negrita
            comando.extend(f'{idx}. {item["nombre"]}\n'.encode('utf-8'))
            comando.extend(b'\x1B\x21\x00')
            
            comando.extend(f'   Pedidos: {formatear_numero(item["cantidad_pedidos"])}\n'.encode('utf-8'))
            comando.extend(f'   Items: {formatear_numero(item["total_items"])}\n'.encode('utf-8'))
            
            total_str = f'{item["total_ventas"]:,.2f} Bs.'
            espacios = ancho_linea - len(total_str) - 3
            comando.extend(('   ' + ' ' * espacios + total_str + '\n').encode('utf-8'))
            comando.extend('\n'.encode('utf-8'))
    else:  # producto
        for idx, item in enumerate(reporte_data, 1):
            comando.extend(b'\x1B\x21\x08')  # Negrita
            comando.extend(f'{idx}. {item["nombre"]}\n'.encode('utf-8'))
            comando.extend(b'\x1B\x21\x00')
            
            comando.extend(f'   Cantidad: {formatear_numero(item["cantidad_total"])}\n'.encode('utf-8'))
            comando.extend(f'   Pedidos: {formatear_numero(item["pedidos_distintos"])}\n'.encode('utf-8'))
            
            total_str = f'{item["total_ventas"]:,.2f} Bs.'
            espacios = ancho_linea - len(total_str) - 3
            comando.extend(('   ' + ' ' * espacios + total_str + '\n').encode('utf-8'))
            comando.extend('\n'.encode('utf-8'))
    
    # Total general
    comando.extend(('-' * ancho_linea + '\n').encode('utf-8'))
    comando.extend(b'\x1B\x61\x01')  # Centrar
    comando.extend(b'\x1B\x21\x10')  # Negrita
    total_str = f'TOTAL GENERAL: {total_general:,.2f} Bs.'
    comando.extend(total_str.encode('utf-8'))
    comando.extend(b'\x1B\x21\x00')
    comando.extend(b'\x1B\x61\x00')
    comando.extend('\n'.encode('utf-8'))
    
    # Agregar indicador de NO COBRADO si es cobranza
    if filtro_estado == 'ENTREGADO_NO_PAGADO':
        comando.extend('\n'.encode('utf-8'))
        comando.extend(b'\x1B\x61\x01')  # Centrar
        comando.extend(b'\x1B\x21\x10')  # Negrita
        comando.extend('*** NO COBRADO ***\n'.encode('utf-8'))
        comando.extend(b'\x1B\x21\x00')
        comando.extend(b'\x1B\x61\x00')
    
    comando.extend('\n'.encode('utf-8'))
    
    # Fecha y hora de impresión
    comando.extend(b'\x1B\x61\x01')  # Centrar
    ahora = datetime.now().strftime('%d/%m/%Y %I:%M %p')
    comando.extend(f'Emitido: {ahora}\n'.encode('utf-8'))
    comando.extend(b'\x1B\x61\x00')
    
    # Espacios finales
    comando.extend('\n'.encode('utf-8'))
    comando.extend('\n'.encode('utf-8'))
    comando.extend('\n'.encode('utf-8'))
    
    # Cortar papel
    comando.extend(b'\x1D\x56\x00')  # Corte parcial
    
    return bytes(comando)


def _formatear_monto_bs(valor):
    try:
        cantidad = float(valor or 0)
    except (TypeError, ValueError):
        cantidad = 0.0
    monto = f"{cantidad:,.2f}"
    if '.' in monto:
        parte_entera, parte_decimal = monto.split('.')
        return f"Bs. {parte_entera.replace(',', '.')},{parte_decimal}"
    return f"Bs. {monto.replace(',', '.')}"


def _wrap_text(texto, ancho):
    palabras = texto.split()
    if not palabras:
        return ['']
    lineas = []
    linea_actual = palabras[0]
    for palabra in palabras[1:]:
        if len(linea_actual) + 1 + len(palabra) <= ancho:
            linea_actual += ' ' + palabra
        else:
            lineas.append(linea_actual)
            linea_actual = palabra
    lineas.append(linea_actual)
    return lineas


def generar_lista_precios_escpos(productos):
    ancho_linea = 48
    comando = bytearray()

    comando.extend(b'\x1B\x40')  # Reset
    comando.extend(b'\x1B\x61\x01')  # Centrar
    comando.extend(b'\x1B\x21\x38')
    comando.extend('LISTA DE PRECIOS\n'.encode('utf-8'))
    comando.extend(b'\x1B\x21\x00')

    comando.extend(('=' * ancho_linea + '\n').encode('utf-8'))
    comando.extend(b'\x1B\x61\x00')
    ahora = datetime.now().strftime('%d/%m/%Y %I:%M %p')
    comando.extend(f'Emitido: {ahora}\n'.encode('utf-8'))
    comando.extend(('-' * ancho_linea + '\n\n').encode('utf-8'))

    for producto in productos:
        nombre_lineas = _wrap_text(producto.nombre, ancho_linea)
        for idx, linea in enumerate(nombre_lineas):
            comando.extend(b'\x1B\x21\x08' if idx == 0 else b'\x1B\x21\x00')
            comando.extend(f'{linea}\n'.encode('utf-8'))
        comando.extend(b'\x1B\x21\x00')

        regular = _formatear_monto_bs(producto.precio_regular)
        minimo = _formatear_monto_bs(producto.precio_minimo)

        comando.extend(f'   Precio regular: {regular}\n'.encode('utf-8'))
        if producto.precio_minimo is not None and producto.precio_minimo != producto.precio_regular:
            comando.extend(f'   Precio mínimo:  {minimo}\n'.encode('utf-8'))
        comando.extend('\n'.encode('utf-8'))

    comando.extend(('-' * ancho_linea + '\n').encode('utf-8'))
    comando.extend(b'\x1B\x61\x01')
    comando.extend('Precios sujetos a cambio.\n'.encode('utf-8'))
    comando.extend(b'\x1B\x61\x00')

    comando.extend('\n'.encode('utf-8'))
    comando.extend('\n'.encode('utf-8'))
    comando.extend('\n'.encode('utf-8'))
    comando.extend(b'\x1D\x56\x00')  # Corte parcial

    return bytes(comando)


def imprimir_lista_precios(productos=None):
    if not current_app.config.get('IMPRESORA_HABILITADA', False):
        current_app.logger.info("Impresora deshabilitada en configuración")
        return {
            'success': False,
            'skipped': True,
            'message': 'Impresora deshabilitada'
        }

    if productos is None:
        productos = ProductoPanaderia.query.order_by(ProductoPanaderia.nombre.asc()).all()

    if not productos:
        return {
            'success': False,
            'error': 'No hay productos registrados para imprimir.'
        }

    impresora_ip = current_app.config.get('IMPRESORA_IP', '192.168.1.100')
    impresora_puerto = current_app.config.get('IMPRESORA_PUERTO', 9100)

    try:
        comando = generar_lista_precios_escpos(productos)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        current_app.logger.info(f"Imprimiendo lista de precios en {impresora_ip}:{impresora_puerto}")
        sock.connect((impresora_ip, impresora_puerto))
        sock.sendall(comando)
        sock.close()
        return {
            'success': True,
            'message': 'Lista de precios enviada a la impresora.'
        }
    except Exception as e:
        current_app.logger.error(f"Error imprimiendo lista de precios: {e}", exc_info=True)
        return {
            'success': False,
            'error': f'Error al imprimir: {str(e)}'
        }


def generar_comanda_pdf(pedido_id):
    """
    Genera un PDF de la comanda para impresión cuando no hay acceso directo a la impresora.
    
    Args:
        pedido_id: ID del pedido
        
    Returns:
        str: Ruta al archivo PDF generado
    """
    pedido = PedidoPanaderia.query.get(pedido_id)
    if not pedido:
        raise ValueError(f"Pedido {pedido_id} no encontrado")
    
    # Crear PDF en tamaño 80mm de ancho
    pdf = FPDF(orientation='P', unit='mm', format=(80, 200))
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(5, 5, 5)
    
    # Agregar fuente con soporte Unicode
    try:
        pdf.add_font('Arial', '', r'C:\Windows\Fonts\arial.ttf')
        pdf.add_font('Arial', 'B', r'C:\Windows\Fonts\arialbd.ttf')
        unicode_font = 'Arial'
    except:
        unicode_font = 'Helvetica'
    
    pdf.add_page()
    
    # Encabezado
    pdf.set_font(unicode_font, 'B', 12)
    pdf.cell(0, 8, txt='PANADERIA SIIP', ln=1, align='C')
    pdf.ln(2)
    
    pdf.set_font(unicode_font, '', 8)
    pdf.cell(0, 3, txt='=' * 30, ln=1, align='C')
    pdf.ln(1)
    
    # Número de pedido
    pdf.set_font(unicode_font, 'B', 10)
    pdf.cell(0, 5, txt=f'PEDIDO: {pedido.numero_pedido}', ln=1, align='L')
    
    # Fecha
    pdf.set_font(unicode_font, '', 8)
    fecha_str = pedido.fecha_pedido.strftime('%d/%m/%Y %H:%M')
    pdf.cell(0, 4, txt=f'Fecha: {fecha_str}', ln=1, align='L')
    pdf.ln(2)
    
    pdf.cell(0, 3, txt='-' * 30, ln=1, align='C')
    pdf.ln(1)
    
    # Cliente
    pdf.set_font(unicode_font, 'B', 9)
    pdf.cell(0, 5, txt='CLIENTE:', ln=1, align='L')
    pdf.set_font(unicode_font, '', 9)
    pdf.cell(0, 4, txt=pedido.cliente.nombre, ln=1, align='L')
    if pedido.cliente.telefono:
        pdf.cell(0, 4, txt=f'Tel: {pedido.cliente.telefono}', ln=1, align='L')
    pdf.ln(2)
    
    pdf.cell(0, 3, txt='-' * 30, ln=1, align='C')
    pdf.ln(1)
    
    # Items
    pdf.set_font(unicode_font, 'B', 9)
    pdf.cell(0, 5, txt='DETALLE:', ln=1, align='L')
    pdf.cell(0, 3, txt='-' * 30, ln=1, align='C')
    pdf.ln(1)
    
    items = ItemPedidoPanaderia.query.filter_by(pedido_id=pedido.id).all()
    for idx, item in enumerate(items, 1):
        pdf.set_font(unicode_font, '', 8)
        producto_nombre = item.producto.nombre
        if len(producto_nombre) > 30:
            producto_nombre = producto_nombre[:27] + '...'
        pdf.cell(0, 4, txt=f'{idx}. {producto_nombre}', ln=1, align='L')
        
        pdf.set_font(unicode_font, '', 7)
        cantidad_str = f'   Qty: {item.cantidad} x {item.precio_unitario:.2f} Bs.'
        pdf.cell(0, 3, txt=cantidad_str, ln=1, align='L')
        
        subtotal_str = f'{item.subtotal:.2f} Bs.'
        espacios = 20
        pdf.cell(espacios, 3, txt='', ln=0, align='R')
        pdf.set_font(unicode_font, 'B', 8)
        pdf.cell(0, 3, txt=subtotal_str, ln=1, align='R')
        pdf.ln(1)
    
    pdf.set_font(unicode_font, '', 8)
    pdf.cell(0, 3, txt='-' * 30, ln=1, align='C')
    pdf.ln(1)
    
    # Total
    pdf.set_font(unicode_font, 'B', 10)
    total_str = f'TOTAL: {pedido.total:.2f} Bs.'
    espacios = 20
    pdf.cell(espacios, 5, txt='', ln=0, align='R')
    pdf.cell(0, 5, txt=total_str, ln=1, align='R')
    pdf.ln(2)
    
    # Observaciones
    if pedido.observaciones:
        pdf.cell(0, 3, txt='-' * 30, ln=1, align='C')
        pdf.ln(1)
        pdf.set_font(unicode_font, 'B', 8)
        pdf.cell(0, 4, txt='OBSERVACIONES:', ln=1, align='L')
        pdf.set_font(unicode_font, '', 7)
        obs_lines = [pedido.observaciones[i:i+30] for i in range(0, len(pedido.observaciones), 30)]
        for line in obs_lines:
            pdf.cell(0, 3, txt=line, ln=1, align='L')
        pdf.ln(1)
    
    pdf.ln(3)
    pdf.set_font(unicode_font, '', 8)
    pdf.cell(0, 4, txt='Gracias por su compra!', ln=1, align='C')
    pdf.ln(2)
    
    ahora = datetime.now().strftime('%d/%m/%Y %H:%M')
    pdf.set_font(unicode_font, '', 7)
    pdf.cell(0, 3, txt=f'Emitido: {ahora}', ln=1, align='C')
    pdf.ln(2)
    
    # Guardar PDF
    reports_folder = current_app.config.get('REPORTS_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports'))
    os.makedirs(reports_folder, exist_ok=True)
    
    filename = f'comanda_{pedido.numero_pedido}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    filepath = os.path.join(reports_folder, filename)
    pdf.output(filepath)
    
    return filepath

def generar_mensaje_cocina_escpos(mensaje_id):
    """
    Genera el código ESC/POS para imprimir un mensaje a la cocina.
    
    Args:
        mensaje_id: ID del mensaje en la base de datos
        
    Returns:
        bytes: Código ESC/POS listo para imprimir
    """
    # Obtener mensaje de la base de datos
    mensaje = MensajeCocina.query.get(mensaje_id)
    if not mensaje:
        raise ValueError(f"Mensaje {mensaje_id} no encontrado")
    
    # Inicializar comando ESC/POS
    comando = bytearray()
    
    # Reset de impresora
    comando.extend(b'\x1B\x40')
    
    # Configuración inicial - TODO CENTRADO
    comando.extend(b'\x1B\x61\x01')  # Centrar
    
    # Encabezado - TEXTO MÁS GRANDE
    comando.extend(b'\x1B\x21\x38')  # Texto grande y negrita
    comando.extend('MENSAJE COCINA\n'.encode('utf-8'))
    comando.extend(b'\x1B\x21\x00')  # Reset formato
    
    comando.extend(('=' * 32 + '\n').encode('utf-8'))
    
    # Prioridad - DESTACADA
    comando.extend(b'\x1B\x61\x01')  # Centrar
    comando.extend(b'\x1B\x21\x18')  # Texto grande y negrita
    if mensaje.prioridad == 'urgente':
        comando.extend('!!! URGENTE !!!\n'.encode('utf-8'))
    elif mensaje.prioridad == 'alta':
        comando.extend('** ALTA PRIORIDAD **\n'.encode('utf-8'))
    comando.extend(b'\x1B\x21\x00')
    comando.extend(('-' * 32 + '\n').encode('utf-8'))
    
    # Fecha y hora
    comando.extend(b'\x1B\x61\x01')  # Centrar
    fecha_formateada = mensaje.fecha_creacion.strftime("%d/%m/%Y %I:%M %p")
    comando.extend(f'Fecha: {fecha_formateada}\n'.encode('utf-8'))
    comando.extend(('-' * 32 + '\n').encode('utf-8'))
    
    # Mensaje - CENTRADO Y FORMATEADO
    comando.extend(b'\x1B\x61\x01')  # Centrar
    comando.extend(b'\x1B\x21\x08')  # Negrita
    comando.extend('MENSAJE:\n'.encode('utf-8'))
    comando.extend(b'\x1B\x21\x00')
    comando.extend(('-' * 32 + '\n').encode('utf-8'))
    
    # Dividir mensaje en líneas de máximo 32 caracteres
    mensaje_texto = mensaje.mensaje
    lineas = []
    palabras = mensaje_texto.split()
    linea_actual = ''
    
    for palabra in palabras:
        if len(linea_actual + ' ' + palabra) <= 32:
            if linea_actual:
                linea_actual += ' ' + palabra
            else:
                linea_actual = palabra
        else:
            if linea_actual:
                lineas.append(linea_actual)
            linea_actual = palabra
    
    if linea_actual:
        lineas.append(linea_actual)
    
    # Imprimir cada línea centrada
    for linea in lineas:
        comando.extend(b'\x1B\x61\x01')  # Centrar
        comando.extend(f'{linea}\n'.encode('utf-8'))
    
    comando.extend(('-' * 32 + '\n').encode('utf-8'))
    
    # Usuario que envió
    comando.extend(b'\x1B\x61\x01')  # Centrar
    comando.extend(b'\x1B\x21\x00')
    usuario_nombre = mensaje.usuario.nombre_completo if mensaje.usuario else 'Sistema'
    comando.extend(f'Enviado por: {usuario_nombre}\n'.encode('utf-8'))
    
    comando.extend(('=' * 32 + '\n').encode('utf-8'))
    comando.extend(b'\n\n\n')  # Espacios para cortar
    
    return bytes(comando)

def imprimir_mensaje_cocina(mensaje_id):
    """
    Imprime un mensaje a la cocina en la impresora térmica.
    
    Args:
        mensaje_id: ID del mensaje a imprimir
        
    Returns:
        dict: Resultado de la impresión
    """
    try:
        # Verificar si la impresora está habilitada
        if not current_app.config.get('IMPRESORA_HABILITADA', False):
            return {
                'success': False,
                'skipped': True,
                'message': 'Impresora deshabilitada en configuración'
            }
        
        # Generar comando ESC/POS
        comando_escpos = generar_mensaje_cocina_escpos(mensaje_id)
        
        # Obtener configuración de impresora
        impresora_ip = current_app.config.get('IMPRESORA_IP', '192.168.1.100')
        impresora_puerto = current_app.config.get('IMPRESORA_PUERTO', 9100)
        
        # Conectar e imprimir
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        current_app.logger.info(f"Imprimiendo mensaje de cocina en {impresora_ip}:{impresora_puerto}")
        sock.connect((impresora_ip, impresora_puerto))
        sock.sendall(comando_escpos)
        sock.close()
        
        current_app.logger.info("Mensaje de cocina impreso exitosamente")
        return {
            'success': True,
            'message': 'Mensaje impreso exitosamente'
        }
        
    except socket.timeout:
        current_app.logger.error("Timeout al conectar con la impresora")
        return {
            'success': False,
            'error': 'Timeout al conectar con la impresora. Verifica la conexión.'
        }
    except socket.error as e:
        current_app.logger.error(f"Error de conexión con la impresora: {e}")
        return {
            'success': False,
            'error': f'Error de conexión con la impresora: {str(e)}'
        }
    except Exception as e:
        current_app.logger.error(f"Error imprimiendo mensaje de cocina: {e}", exc_info=True)
        return {
            'success': False,
            'error': f'Error al imprimir mensaje: {str(e)}'
        }
