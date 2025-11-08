from flask import render_template, redirect, url_for, flash, request, Blueprint, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from sqlalchemy import func, cast, Date, desc
from datetime import datetime
import time
import socket
import os

from app import db
from app.models import ProductoPanaderia, Vendedor, ProduccionDiaria, VentaDiaria, MovimientoVendedor, PedidoPanaderia, ItemPedidoPanaderia, ClientePanaderia, User, MensajeCocina
from app.panaderia.forms import (
    ProductoPanaderiaForm, VendedorForm, ProduccionDiariaForm,
    VentaDiariaForm, MovimientoVendedorForm
)
from app.panaderia import panaderia_bp # Import the blueprint
from app.thermal_printer import imprimir_comanda, imprimir_lista_precios

@panaderia_bp.route('/')
@login_required
def index():
    return render_template('panaderia/index.html', title='Gestión de Panadería')


@panaderia_bp.route('/reportes')
@login_required
def reportes():
    total_ingresos = db.session.query(func.sum(VentaDiaria.precio_total_venta)).scalar() or 0.0
    total_costo = db.session.query(func.sum(ProduccionDiaria.costo_total_produccion)).scalar() or 0.0
    ganancia_bruta = total_ingresos - total_costo

    ventas_por_vendedor = db.session.query(
        Vendedor.nombre.label('nombre'),
        func.coalesce(func.sum(VentaDiaria.precio_total_venta), 0).label('total_vendido'),
        func.count(VentaDiaria.id).label('cantidad_ventas')
    ).outerjoin(VentaDiaria).group_by(Vendedor.id).order_by(func.coalesce(func.sum(VentaDiaria.precio_total_venta), 0).desc()).all()

    produccion_agrupada = db.session.query(
        ProductoPanaderia.nombre,
        func.coalesce(func.sum(ProduccionDiaria.cantidad_producida), 0).label('total_producido')
    ).outerjoin(ProduccionDiaria).group_by(ProductoPanaderia.id).all()

    ventas_agrupadas = db.session.query(
        ProductoPanaderia.nombre,
        func.coalesce(func.sum(VentaDiaria.cantidad_vendida), 0).label('total_vendido')
    ).join(ProduccionDiaria, VentaDiaria.produccion_id == ProduccionDiaria.id)\
     .join(ProductoPanaderia, ProduccionDiaria.producto_id == ProductoPanaderia.id)\
     .group_by(ProductoPanaderia.id).all()

    reporte_productos = {}
    for prod in produccion_agrupada:
        reporte_productos[prod.nombre] = {
            'producido': int(prod.total_producido or 0),
            'vendido': 0
        }

    for venta in ventas_agrupadas:
        reporte_productos.setdefault(venta.nombre, {'producido': 0, 'vendido': 0})
        reporte_productos[venta.nombre]['vendido'] = int(venta.total_vendido or 0)

    produccion_reciente = ProduccionDiaria.query.order_by(
        ProduccionDiaria.fecha_produccion.desc(),
        ProduccionDiaria.id.desc()
    ).limit(15).all()

    return render_template(
        'panaderia/reportes.html',
        title='Reportes de Panadería',
        total_ingresos=total_ingresos,
        total_costo_produccion=total_costo,
        ganancia_bruta=ganancia_bruta,
        ventas_por_vendedor=ventas_por_vendedor,
        reporte_productos=reporte_productos,
        produccion_reciente=produccion_reciente
    )

# --- Rutas para Productos ---
@panaderia_bp.route('/productos', methods=['GET', 'POST'])
@login_required
def productos():
    form = ProductoPanaderiaForm()
    if form.validate_on_submit():
        producto = ProductoPanaderia(
            nombre=form.nombre.data,
            costo_produccion=form.costo_produccion.data,
            precio_regular=form.precio_regular.data,
            precio_minimo=form.precio_minimo.data
        )
        db.session.add(producto)
        db.session.commit()
        flash('Producto añadido exitosamente!', 'success')
        return redirect(url_for('panaderia.productos'))
    
    productos = ProductoPanaderia.query.order_by(ProductoPanaderia.nombre).all()
    return render_template('panaderia/productos.html', title='Productos', form=form, productos=productos)

@panaderia_bp.route('/productos/editar/<int:producto_id>', methods=['GET', 'POST'])
@login_required
def editar_producto(producto_id):
    producto = ProductoPanaderia.query.get_or_404(producto_id)
    form = ProductoPanaderiaForm(obj=producto)
    if form.validate_on_submit():
        form.populate_obj(producto)
        db.session.commit()
        flash('Producto actualizado exitosamente!', 'success')
        return redirect(url_for('panaderia.productos'))
    return render_template('panaderia/editar_producto.html', title='Editar Producto', form=form, producto=producto)

@panaderia_bp.route('/productos/eliminar/<int:producto_id>', methods=['POST'])
@login_required
def eliminar_producto(producto_id):
    producto = ProductoPanaderia.query.get_or_404(producto_id)
    db.session.delete(producto)
    db.session.commit()
    flash('Producto eliminado exitosamente!', 'success')
    return redirect(url_for('panaderia.productos'))

# --- Rutas para Vendedores ---
@panaderia_bp.route('/vendedores', methods=['GET', 'POST'])
@login_required
def vendedores():
    form = VendedorForm()
    if form.validate_on_submit():
        vendedor = Vendedor(
            nombre=form.nombre.data,
            telefono=form.telefono.data,
            direccion=form.direccion.data
        )
        db.session.add(vendedor)
        db.session.commit()
        flash('Vendedor añadido exitosamente!', 'success')
        return redirect(url_for('panaderia.vendedores'))
    
    vendedores = Vendedor.query.order_by(Vendedor.nombre).all()
    return render_template('panaderia/vendedores.html', title='Vendedores', form=form, vendedores=vendedores)

@panaderia_bp.route('/vendedores/editar/<int:vendedor_id>', methods=['GET', 'POST'])
@login_required
def editar_vendedor(vendedor_id):
    vendedor = Vendedor.query.get_or_404(vendedor_id)
    form = VendedorForm(obj=vendedor)
    if form.validate_on_submit():
        form.populate_obj(vendedor)
        db.session.commit()
        flash('Vendedor actualizado exitosamente!', 'success')
        return redirect(url_for('panaderia.vendedores'))
    return render_template('panaderia/editar_vendedor.html', title='Editar Vendedor', form=form, vendedor=vendedor)

@panaderia_bp.route('/vendedores/eliminar/<int:vendedor_id>', methods=['POST'])
@login_required
def eliminar_vendedor(vendedor_id):
    vendedor = Vendedor.query.get_or_404(vendedor_id)
    db.session.delete(vendedor)
    db.session.commit()
    flash('Vendedor eliminado exitosamente!', 'success')
    return redirect(url_for('panaderia.vendedores'))

# --- Rutas para Producción Diaria ---
@panaderia_bp.route('/produccion', methods=['GET', 'POST'])
@login_required
def produccion():
    form = ProduccionDiariaForm()
    form.producto_id.choices = [(p.id, p.nombre) for p in ProductoPanaderia.query.order_by(ProductoPanaderia.nombre).all()]

    if form.validate_on_submit():
        producto = ProductoPanaderia.query.get(form.producto_id.data)
        if not producto:
            flash('Producto no encontrado.', 'danger')
            return redirect(url_for('panaderia.produccion'))

        costo_total = producto.costo_produccion * form.cantidad_producida.data
        produccion_diaria = ProduccionDiaria(
            producto_id=form.producto_id.data,
            fecha_produccion=form.fecha_produccion.data,
            cantidad_producida=form.cantidad_producida.data,
            costo_total_produccion=costo_total
        )
        db.session.add(produccion_diaria)
        db.session.commit()
        flash('Producción registrada exitosamente!', 'success')
        return redirect(url_for('panaderia.produccion'))
    
    producciones = ProduccionDiaria.query.order_by(ProduccionDiaria.fecha_produccion.desc(), ProduccionDiaria.id.desc()).all()
    return render_template('panaderia/produccion.html', title='Producción Diaria', form=form, producciones=producciones)

@panaderia_bp.route('/produccion/eliminar/<int:produccion_id>', methods=['POST'])
@login_required
def eliminar_produccion(produccion_id):
    produccion = ProduccionDiaria.query.get_or_404(produccion_id)
    db.session.delete(produccion)
    db.session.commit()
    flash('Producción eliminada exitosamente!', 'success')
    return redirect(url_for('panaderia.produccion'))

# --- Rutas para Ventas Diarias ---
@panaderia_bp.route('/ventas', methods=['GET', 'POST'])
@login_required
def ventas():
    form = VentaDiariaForm()
    form.produccion_id.choices = [(p.id, f"{p.producto.nombre} ({p.cantidad_producida} unid. - {p.fecha_produccion.strftime('%Y-%m-%d')})") 
                                  for p in ProduccionDiaria.query.order_by(ProduccionDiaria.fecha_produccion.desc()).all()]
    form.vendedor_id.choices = [(v.id, v.nombre) for v in Vendedor.query.order_by(Vendedor.nombre).all()]

    if form.validate_on_submit():
        produccion_origen = ProduccionDiaria.query.get(form.produccion_id.data)
        if not produccion_origen:
            flash('Producción de origen no encontrada.', 'danger')
            return redirect(url_for('panaderia.ventas'))

        # Validar que la cantidad vendida no exceda la cantidad producida restante
        # Esto es una simplificación, en un sistema real se necesitaría un control de inventario más robusto
        # Por ahora, solo se valida contra la cantidad producida total
        if form.cantidad_vendida.data > produccion_origen.cantidad_producida:
            flash('La cantidad vendida no puede exceder la cantidad producida.', 'danger')
            return redirect(url_for('panaderia.ventas'))

        is_regalia = request.form.get('regalia_submit') == 'true'
        is_descuento = request.form.get('descuento_submit') == 'true'

        if is_regalia:
            precio_total = 0.0
            descripcion_movimiento = f"Regalía de {form.cantidad_vendida.data} unidades de {produccion_origen.producto.nombre}"
            tipo_movimiento = 'REGALIA'
        elif is_descuento:
            precio_total = produccion_origen.producto.precio_minimo * form.cantidad_vendida.data
            descripcion_movimiento = f"Venta con Descuento de {form.cantidad_vendida.data} unidades de {produccion_origen.producto.nombre}"
            tipo_movimiento = 'DESCUENTO'
        else:
            precio_total = produccion_origen.producto.precio_regular * form.cantidad_vendida.data
            descripcion_movimiento = f"Venta Normal de {form.cantidad_vendida.data} unidades de {produccion_origen.producto.nombre}"
            tipo_movimiento = 'NORMAL'

        venta = VentaDiaria(
            produccion_id=form.produccion_id.data,
            vendedor_id=form.vendedor_id.data,
            cantidad_vendida=form.cantidad_vendida.data,
            precio_total_venta=precio_total,
            fecha_venta=form.fecha_venta.data,
            tipo_venta=tipo_movimiento # Add this line
        )
        db.session.add(venta)
        
        # Registrar el movimiento de despacho para el vendedor
        movimiento = MovimientoVendedor(
            vendedor_id=form.vendedor_id.data,
            tipo_movimiento=tipo_movimiento,
            monto=precio_total, # El monto que el vendedor "debe" por este despacho (0 para regalías)
            venta_id=venta.id, # Asociar el movimiento a la venta
            descripcion=descripcion_movimiento
        )
        db.session.add(movimiento)

        db.session.commit()
        flash('Venta registrada exitosamente!', 'success')
        return redirect(url_for('panaderia.ventas'))
    
    ventas = VentaDiaria.query.order_by(VentaDiaria.fecha_venta.desc(), VentaDiaria.id.desc()).all()
    return render_template('panaderia/ventas.html', title='Ventas Diarias', form=form, ventas=ventas)

@panaderia_bp.route('/ventas/editar/<int:venta_id>', methods=['GET', 'POST'])
@login_required
def editar_venta(venta_id):
    venta = VentaDiaria.query.get_or_404(venta_id)
    form = VentaDiariaForm(obj=venta)
    
    # Populate choices for dropdowns
    form.produccion_id.choices = [(p.id, f"{p.producto.nombre} ({p.cantidad_producida} unid. - {p.fecha_produccion.strftime('%Y-%m-%d')})") 
                                  for p in ProduccionDiaria.query.order_by(ProduccionDiaria.fecha_produccion.desc()).all()]
    form.vendedor_id.choices = [(v.id, v.nombre) for v in Vendedor.query.order_by(Vendedor.nombre).all()]

    if request.method == 'POST':
        if form.validate_on_submit():
            # Store original values for comparison
            original_cantidad_vendida = venta.cantidad_vendida
            original_produccion_id = venta.produccion_id

            # Store original type before populating from form, as form doesn't have tipo_venta yet
            original_tipo_venta = venta.tipo_venta

            form.populate_obj(venta)

            produccion_origen = ProduccionDiaria.query.get(venta.produccion_id)
            if not produccion_origen:
                flash('Producción de origen no encontrada.', 'danger')
                return redirect(url_for('panaderia.ventas'))

            # Recalculate price and update description based on the original sale type
            if original_tipo_venta == 'REGALIA':
                venta.precio_total_venta = 0.0
                descripcion_movimiento = f"Regalía de {venta.cantidad_vendida} unidades de {produccion_origen.producto.nombre}"
            elif original_tipo_venta == 'DESCUENTO':
                venta.precio_total_venta = produccion_origen.producto.precio_minimo * venta.cantidad_vendida
                descripcion_movimiento = f"Venta con Descuento de {venta.cantidad_vendida} unidades de {produccion_origen.producto.nombre}"
            else: # 'NORMAL' or any other case
                venta.precio_total_venta = produccion_origen.producto.precio_regular * venta.cantidad_vendida
                descripcion_movimiento = f"Venta Normal de {venta.cantidad_vendida} unidades de {produccion_origen.producto.nombre}"
            
            venta.tipo_venta = original_tipo_venta # Preserve original type

            # Update associated MovimientoVendedor
            movimiento = MovimientoVendedor.query.filter_by(venta_id=venta.id).first()
            if movimiento:
                movimiento.vendedor_id = venta.vendedor_id
                movimiento.monto = venta.precio_total_venta
                movimiento.descripcion = descripcion_movimiento
            else:
                # This case should ideally not happen if a sale always creates a movement
                # But as a fallback, create a new movement
                new_movimiento = MovimientoVendedor(
                    vendedor_id=venta.vendedor_id,
                    tipo_movimiento=original_tipo_venta,
                    monto=venta.precio_total_venta,
                    venta_id=venta.id,
                    descripcion=descripcion_movimiento
                )
                db.session.add(new_movimiento)

            db.session.commit()
            flash('Venta actualizada exitosamente!', 'success')
            return redirect(url_for('panaderia.ventas'))
        else:
            # If form validation fails, re-render the template with errors
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Error en {getattr(form, field).label.text}: {error}", 'danger')

    return render_template('panaderia/editar_venta.html', title='Editar Venta', form=form, venta=venta)

@panaderia_bp.route('/ventas/eliminar/<int:venta_id>', methods=['POST'])
@login_required
def eliminar_venta(venta_id):
    venta = VentaDiaria.query.get_or_404(venta_id)
    
    # Delete associated MovimientoVendedor first due to foreign key constraints
    movimiento = MovimientoVendedor.query.filter_by(venta_id=venta.id).first()
    if movimiento:
        db.session.delete(movimiento)

    db.session.delete(venta)
    db.session.commit()
    flash('Venta eliminada exitosamente!', 'success')
    return redirect(url_for('panaderia.ventas'))

# --- Rutas para Movimientos de Vendedores (Pagos) ---
@panaderia_bp.route('/movimientos_vendedor', methods=['GET', 'POST'])
@login_required
def movimientos_vendedor():
    form = MovimientoVendedorForm()
    form.vendedor_id.choices = [(v.id, v.nombre) for v in Vendedor.query.order_by(Vendedor.nombre).all()]

    if form.validate_on_submit():
        # Si es un pago, el monto debe ser negativo para restar al balance del vendedor
        monto_final = form.monto.data
        if form.tipo_movimiento.data == 'PAGO':
            monto_final = -abs(monto_final) # Asegurar que el pago sea negativo

        movimiento = MovimientoVendedor(
            vendedor_id=form.vendedor_id.data,
            tipo_movimiento=form.tipo_movimiento.data,
            monto=monto_final,
            descripcion=form.descripcion.data
        )
        db.session.add(movimiento)
        db.session.commit()
        flash('Movimiento registrado exitosamente!', 'success')
        return redirect(url_for('panaderia.movimientos_vendedor'))
    
    movimientos = MovimientoVendedor.query.order_by(MovimientoVendedor.fecha_movimiento.desc(), MovimientoVendedor.id.desc()).all()
    return render_template('panaderia/movimientos_vendedor.html', title='Movimientos de Vendedores', form=form, movimientos=movimientos)

# --- Reporte de Deuda de Vendedores ---
@panaderia_bp.route('/reporte_vendedores')
@login_required
def reporte_vendedores():
    # Calcular el balance de cada vendedor
    # Suma de montos de movimientos (despachos positivos, pagos negativos)
    reporte = db.session.query(
        Vendedor.nombre,
        func.sum(MovimientoVendedor.monto).label('balance_actual')
    ).join(MovimientoVendedor).group_by(Vendedor.nombre).all()

    return render_template('panaderia/reporte_vendedores.html', title='Reporte de Vendedores', reporte=reporte)

# --- Reporte de Producción y Ventas por Día ---
@panaderia_bp.route('/reporte_diario')
@login_required
def reporte_diario():
    # Debugging: Get product ID for "PAN CAMPESINO 400gr"
    pan_campesino = ProductoPanaderia.query.filter_by(nombre='PAN CAMPESINO 400gr').first()
    if pan_campesino:
        pan_campesino_id = pan_campesino.id
        print(f"ID for PAN CAMPESINO 400gr: {pan_campesino_id}")

        # Debugging: Fetch all individual production records for PAN CAMPESINO 400gr on 2025-08-29
        produccion_details = db.session.query(
            ProduccionDiaria.id,
            ProduccionDiaria.fecha_produccion,
            ProduccionDiaria.cantidad_producida,
            ProduccionDiaria.costo_total_produccion
        ).filter(
            ProduccionDiaria.producto_id == pan_campesino_id,
            ProduccionDiaria.fecha_produccion == '2025-08-29'
        ).all()

        print(f"Detailed Production for PAN CAMPESINO 400gr on 2025-08-29:")
        debug_sum = 0
        for p in produccion_details:
            print(f"  ID: {p.id}, Fecha: {p.fecha_produccion}, Cantidad: {p.cantidad_producida}, Costo: {p.costo_total_produccion}")
            debug_sum += p.cantidad_producida
        print(f"  Sum of individual quantities for PAN CAMPESINO 400gr on 2025-08-29: {debug_sum}")
    else:
        print("PAN CAMPESINO 400gr not found in ProductoPanaderia.")

    # Agrupar producción y ventas por fecha y producto
    produccion_agrupada = db.session.query(
        func.date(ProduccionDiaria.fecha_produccion).label('fecha'),
        ProduccionDiaria.producto_id,
        func.sum(ProduccionDiaria.cantidad_producida).label('total_producido'),
        func.sum(ProduccionDiaria.costo_total_produccion).label('costo_total')
    ).group_by(func.date(ProduccionDiaria.fecha_produccion), ProduccionDiaria.producto_id).order_by(func.date(ProduccionDiaria.fecha_produccion)).all()

    # Fetch product names separately
    productos_map = {p.id: p.nombre for p in ProductoPanaderia.query.all()}

    ventas_agrupadas = db.session.query(
        func.date(VentaDiaria.fecha_venta).label('fecha'),
        ProductoPanaderia.nombre,
        func.sum(VentaDiaria.cantidad_vendida).label('total_vendido'),
        func.sum(VentaDiaria.precio_total_venta).label('ingreso_total')
    ).select_from(VentaDiaria).join(ProduccionDiaria).join(ProductoPanaderia, ProduccionDiaria.producto_id == ProductoPanaderia.id).group_by(func.date(VentaDiaria.fecha_venta), ProductoPanaderia.nombre).order_by(func.date(VentaDiaria.fecha_venta)).all()

    # Convertir a diccionarios para fácil acceso en la plantilla
    reporte_produccion = {}
    for p in produccion_agrupada:
        fecha_str = p.fecha  # CORREGIDO: Usar la fecha como string directamente
        producto_nombre = productos_map.get(p.producto_id, 'Desconocido')
        if fecha_str not in reporte_produccion:
            reporte_produccion[fecha_str] = {'productos': {}, 'total_producido_dia': 0, 'costo_total_dia': 0}
        reporte_produccion[fecha_str]['productos'][producto_nombre] = {
            'producido': p.total_producido,
            'costo': p.costo_total
        }
        reporte_produccion[fecha_str]['total_producido_dia'] += p.total_producido
        reporte_produccion[fecha_str]['costo_total_dia'] += p.costo_total

    reporte_ventas = {}
    for v in ventas_agrupadas:
        fecha_str = v.fecha  # CORREGIDO: Usar la fecha como string directamente
        if fecha_str not in reporte_ventas:
            reporte_ventas[fecha_str] = {'productos': {}, 'total_vendido_dia': 0, 'ingreso_total_dia': 0}
        reporte_ventas[fecha_str]['productos'][v.nombre] = {
            'vendido': v.total_vendido,
            'ingreso': v.ingreso_total
        }
        reporte_ventas[fecha_str]['total_vendido_dia'] += v.total_vendido
        reporte_ventas[fecha_str]['ingreso_total_dia'] += v.ingreso_total

    # Combinar ambos reportes por fecha
    fechas = sorted(list(set(reporte_produccion.keys()) | set(reporte_ventas.keys())), reverse=True)
    reporte_combinado = []
    for fecha in fechas:
        produccion_data = reporte_produccion.get(fecha, {'productos': {}, 'total_producido_dia': 0, 'costo_total_dia': 0})
        ventas_data = reporte_ventas.get(fecha, {'productos': {}, 'total_vendido_dia': 0, 'ingreso_total_dia': 0})
        
        productos_combinados = {}
        all_product_names = sorted(list(set(produccion_data['productos'].keys()) | set(ventas_data['productos'].keys())))
        for prod_name in all_product_names:
            prod_info = produccion_data['productos'].get(prod_name, {'producido': 0, 'costo': 0})
            venta_info = ventas_data['productos'].get(prod_name, {'vendido': 0, 'ingreso': 0})
            productos_combinados[prod_name] = {
                'producido': prod_info['producido'],
                'costo': prod_info['costo'],
                'vendido': venta_info['vendido'],
                'ingreso': venta_info['ingreso']
            }

        reporte_combinado.append({
            'fecha': fecha,
            'produccion': produccion_data,
            'ventas': ventas_data,
            'productos_combinados': productos_combinados
        })

    return render_template('panaderia/reporte_diario.html', title='Reporte Diario de Panadería', reporte=reporte_combinado)

# --- Rutas para Sistema de Pedidos ---
@panaderia_bp.route('/pedidos')
@login_required
def pedidos():
    """Página principal de gestión de pedidos optimizada para tablet."""
    return render_template('panaderia/pedidos.html', title='Control de Pedidos')

@panaderia_bp.route('/api/productos_disponibles')
@login_required
def api_productos_disponibles():
    """API para obtener lista de productos disponibles para pedidos."""
    productos = ProductoPanaderia.query.order_by(ProductoPanaderia.nombre).all()
    productos_data = [{
        'id': p.id,
        'nombre': p.nombre,
        'precio_regular': float(p.precio_regular),
        'precio_minimo': float(p.precio_minimo)
    } for p in productos]
    
    return jsonify({'success': True, 'productos': productos_data})

@panaderia_bp.route('/api/crear_pedido', methods=['POST'])
@login_required
def api_crear_pedido():
    """API para crear un nuevo pedido."""
    try:
        data = request.get_json()
        
        # Validar datos
        if not data or 'items' not in data or not data['items']:
            return jsonify({'success': False, 'error': 'El pedido debe contener al menos un producto'}), 400
        
        # Obtener fecha del pedido (si no viene, usar fecha actual)
        fecha_pedido_str = data.get('fecha_pedido')
        if fecha_pedido_str:
            try:
                fecha_pedido = datetime.strptime(fecha_pedido_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({'success': False, 'error': 'Fecha inválida'}), 400
        else:
            fecha_pedido = datetime.now()
        
        # Generar número de pedido único: PED-{SEQ}-{YYYYMMDD}
        fecha_str = fecha_pedido.strftime('%Y%m%d')
        
        # Contar pedidos del día para generar secuencia
        pedidos_hoy = PedidoPanaderia.query.filter(
            func.date(PedidoPanaderia.fecha_pedido) == fecha_pedido.date()
        ).count()
        
        numero_pedido = f"PED-{pedidos_hoy + 1:03d}-{fecha_str}"
        
        # Validar que cliente existe
        cliente_id = data.get('cliente_id')
        if not cliente_id:
            return jsonify({'success': False, 'error': 'Debe seleccionar un cliente'}), 400
        
        cliente = ClientePanaderia.query.get(cliente_id)
        if not cliente:
            return jsonify({'success': False, 'error': 'Cliente no encontrado'}), 400
        
        # Crear items del pedido primero para calcular el total
        total_pedido = 0.0
        for item_data in data['items']:
            cantidad = int(item_data['cantidad'])
            producto = ProductoPanaderia.query.get(item_data['producto_id'])
            if not producto:
                return jsonify({'success': False, 'error': f'Producto ID {item_data["producto_id"]} no encontrado'}), 400
            
            precio_unitario = float(item_data.get('precio_unitario', producto.precio_regular))
            subtotal = cantidad * precio_unitario
            total_pedido += subtotal
        
        # Crear pedido
        pedido = PedidoPanaderia(
            numero_pedido=numero_pedido,
            cliente_id=cliente_id,
            fecha_pedido=fecha_pedido,
            estado='CONFIRMADO',
            observaciones=data.get('observaciones'),
            usuario_id=current_user.id,
            total=total_pedido
        )
        
        db.session.add(pedido)
        db.session.flush()  # Para obtener el ID del pedido
        
        # Crear items del pedido
        for item_data in data['items']:
            producto = ProductoPanaderia.query.get(item_data['producto_id'])
            cantidad = int(item_data['cantidad'])
            precio_unitario = float(item_data.get('precio_unitario', producto.precio_regular))
            subtotal = cantidad * precio_unitario
            
            item = ItemPedidoPanaderia(
                pedido_id=pedido.id,
                producto_id=producto.id,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                subtotal=subtotal
            )
            
            db.session.add(item)
        
        # Ya no necesitamos actualizar el total aquí
        
        # Commit de la transacción
        db.session.commit()
        
        # Intentar imprimir comanda
        resultado_impresion = imprimir_comanda(pedido.id)
        
        # Preparar respuesta
        respuesta = {
            'success': True,
            'pedido_id': pedido.id,
            'numero_pedido': numero_pedido,
            'total': total_pedido,
            'message': f'Pedido {numero_pedido} creado exitosamente',
            'impresion': resultado_impresion
        }
        
        # Si se generó PDF de fallback, agregar URL de descarga
        if resultado_impresion.get('fallback_pdf') and resultado_impresion.get('pdf_path'):
            pdf_filename = os.path.basename(resultado_impresion['pdf_path'])
            respuesta['pdf_url'] = url_for('panaderia.descargar_pdf', filename=pdf_filename)
        
        # Retornar respuesta exitosa
        return jsonify(respuesta)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creando pedido: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al crear pedido: {str(e)}'}), 500

@panaderia_bp.route('/api/listar_pedidos')
@login_required
def api_listar_pedidos():
    """API para listar pedidos."""
    estado_filtro = request.args.get('estado', None)
    cliente_id = request.args.get('cliente_id', None)
    fecha_inicio = request.args.get('fecha_inicio', None)
    fecha_fin = request.args.get('fecha_fin', None)
    limit = request.args.get('limit', 50, type=int)
    
    query = PedidoPanaderia.query
    
    if estado_filtro:
        query = query.filter_by(estado=estado_filtro)
    
    if cliente_id:
        query = query.filter_by(cliente_id=cliente_id)
    
    # Filtrar por fecha de pedido
    if fecha_inicio:
        fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        query = query.filter(PedidoPanaderia.fecha_pedido >= fecha_inicio_dt)
    
    if fecha_fin:
        fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
        # Incluir todo el día final
        fecha_fin_dt = fecha_fin_dt.replace(hour=23, minute=59, second=59)
        query = query.filter(PedidoPanaderia.fecha_pedido <= fecha_fin_dt)
    
    # Ordenar más reciente primero; si hay misma fecha/hora, el mayor id primero
    pedidos = query.order_by(desc(PedidoPanaderia.fecha_pedido), desc(PedidoPanaderia.id)).limit(limit).all()
    
    pedidos_data = []
    for pedido in pedidos:
        items_data = []
        for item in pedido.items:
            items_data.append({
                'producto': item.producto.nombre,
                'cantidad': item.cantidad,
                'precio_unitario': float(item.precio_unitario),
                'subtotal': float(item.subtotal)
            })
        
        pedidos_data.append({
            'id': pedido.id,
            'numero_pedido': pedido.numero_pedido,
            'cliente_nombre': pedido.cliente.nombre,
            'cliente_telefono': pedido.cliente.telefono,
            'fecha_pedido': pedido.fecha_pedido.isoformat(),
            'estado': pedido.estado,
            'total': float(pedido.total),
            'items': items_data,
            'observaciones': pedido.observaciones
        })
    
    return jsonify({'success': True, 'pedidos': pedidos_data})

@panaderia_bp.route('/api/cambiar_estado_pedido/<int:pedido_id>', methods=['POST'])
@login_required
def api_cambiar_estado_pedido(pedido_id):
    """API para cambiar el estado de un pedido."""
    try:
        pedido = PedidoPanaderia.query.get_or_404(pedido_id)
        data = request.get_json()
        nuevo_estado = data.get('estado')
        
        if nuevo_estado not in ['CONFIRMADO', 'ENTREGADO_PAGADO', 'ENTREGADO_NO_PAGADO', 'CANCELADO']:
            return jsonify({'success': False, 'error': 'Estado inválido'}), 400
        
        pedido.estado = nuevo_estado
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Estado del pedido {pedido.numero_pedido} cambiado a {nuevo_estado}'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cambiando estado de pedido: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al cambiar estado: {str(e)}'}), 500

@panaderia_bp.route('/api/reimprimir_comanda/<int:pedido_id>', methods=['POST'])
@login_required
def api_reimprimir_comanda(pedido_id):
    """API para reimprimir una comanda."""
    try:
        pedido = PedidoPanaderia.query.get_or_404(pedido_id)
        
        # Intentar imprimir comanda
        resultado_impresion = imprimir_comanda(pedido.id)
        
        if resultado_impresion.get('success'):
            return jsonify({
                'success': True,
                'message': f'Comanda del pedido {pedido.numero_pedido} reimpresa exitosamente'
            })
        else:
            return jsonify({
                'success': False,
                'error': resultado_impresion.get('error', 'Error al imprimir')
            }), 500
        
    except Exception as e:
        current_app.logger.error(f"Error reimprimiendo comanda: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al reimprimir: {str(e)}'}), 500

@panaderia_bp.route('/api/datos_impresion/<int:pedido_id>')
@login_required
def api_datos_impresion(pedido_id):
    """API para obtener datos de un pedido para impresión desde el cliente."""
    try:
        pedido = PedidoPanaderia.query.get_or_404(pedido_id)
        items = ItemPedidoPanaderia.query.filter_by(pedido_id=pedido.id).all()
        
        datos = {
            'success': True,
            'pedido': {
                'numero_pedido': pedido.numero_pedido,
                'fecha_pedido': pedido.fecha_pedido.strftime('%d/%m/%Y %H:%M'),
                'total': pedido.total,
                'estado': pedido.estado,
                'observaciones': pedido.observaciones or '',
                'cliente': {
                    'nombre': pedido.cliente.nombre,
                    'telefono': pedido.cliente.telefono or ''
                },
                'items': []
            }
        }
        
        for item in items:
            datos['pedido']['items'].append({
                'nombre': item.producto.nombre,
                'cantidad': item.cantidad,
                'precio_unitario': item.precio_unitario,
                'subtotal': item.subtotal
            })
        
        return jsonify(datos)
        
    except Exception as e:
        current_app.logger.error(f"Error obteniendo datos de impresión: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al obtener datos: {str(e)}'}), 500

@panaderia_bp.route('/descargar_pdf/<filename>')
@login_required
def descargar_pdf(filename):
    """Endpoint para descargar PDFs de comandas."""
    reports_folder = current_app.config.get('REPORTS_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports'))
    return send_from_directory(reports_folder, filename)

# --- APIs para Gestión de Clientes ---
@panaderia_bp.route('/api/clientes_disponibles')
@login_required
def api_clientes_disponibles():
    """API para obtener lista de clientes activos."""
    todos = request.args.get('todos', 'false').lower() == 'true'
    
    query = ClientePanaderia.query
    if not todos:
        query = query.filter_by(activo=True)
    
    clientes = query.order_by(ClientePanaderia.nombre).all()
    clientes_data = [{
        'id': c.id,
        'nombre': c.nombre,
        'telefono': c.telefono or '',
        'direccion': c.direccion or '',
        'precio_regular': c.precio_regular,
        'precio_minimo': c.precio_minimo,
        'precio_regalia': c.precio_regalia
    } for c in clientes]
    
    return jsonify({'success': True, 'clientes': clientes_data})

@panaderia_bp.route('/api/crear_cliente', methods=['POST'])
@login_required
def api_crear_cliente():
    """API para crear un nuevo cliente."""
    try:
        data = request.get_json()
        
        # Validar datos
        if not data or 'nombre' not in data:
            return jsonify({'success': False, 'error': 'El nombre del cliente es obligatorio'}), 400
        
        # Verificar si ya existe un cliente con ese nombre
        cliente_existente = ClientePanaderia.query.filter_by(nombre=data['nombre']).first()
        if cliente_existente:
            return jsonify({'success': False, 'error': 'Ya existe un cliente con ese nombre'}), 400
        
        # Crear cliente
        cliente = ClientePanaderia(
            nombre=data['nombre'],
            telefono=data.get('telefono'),
            direccion=data.get('direccion'),
            activo=True,
            precio_regular=data.get('precio_regular', True),
            precio_minimo=data.get('precio_minimo', False),
            precio_regalia=data.get('precio_regalia', False)
        )
        
        db.session.add(cliente)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'cliente_id': cliente.id,
            'message': f'Cliente {cliente.nombre} creado exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creando cliente: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al crear cliente: {str(e)}'}), 500

@panaderia_bp.route('/api/editar_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def api_editar_cliente(cliente_id):
    """API para editar un cliente existente."""
    try:
        cliente = ClientePanaderia.query.get_or_404(cliente_id)
        data = request.get_json()
        
        # Validar datos
        if not data or 'nombre' not in data:
            return jsonify({'success': False, 'error': 'El nombre del cliente es obligatorio'}), 400
        
        # Verificar si ya existe otro cliente con ese nombre
        cliente_existente = ClientePanaderia.query.filter_by(nombre=data['nombre']).first()
        if cliente_existente and cliente_existente.id != cliente_id:
            return jsonify({'success': False, 'error': 'Ya existe otro cliente con ese nombre'}), 400
        
        # Actualizar datos
        cliente.nombre = data['nombre']
        cliente.telefono = data.get('telefono')
        cliente.direccion = data.get('direccion')
        cliente.precio_regular = data.get('precio_regular', True)
        cliente.precio_minimo = data.get('precio_minimo', False)
        cliente.precio_regalia = data.get('precio_regalia', False)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Cliente {cliente.nombre} actualizado exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error editando cliente: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al editar cliente: {str(e)}'}), 500

@panaderia_bp.route('/api/eliminar_cliente/<int:cliente_id>', methods=['DELETE'])
@login_required
def api_eliminar_cliente(cliente_id):
    """API para desactivar un cliente (no se elimina físicamente para mantener histórico)."""
    try:
        cliente = ClientePanaderia.query.get_or_404(cliente_id)
        
        # Verificar si tiene pedidos asociados
        pedidos_count = PedidoPanaderia.query.filter_by(cliente_id=cliente_id).count()
        if pedidos_count > 0:
            return jsonify({
                'success': False,
                'error': f'No se puede eliminar el cliente porque tiene {pedidos_count} pedido(s) asociado(s). Se desactivará en su lugar.'
            }), 400
        
        # Desactivar cliente en lugar de eliminarlo
        cliente.activo = False
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Cliente {cliente.nombre} desactivado exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error eliminando cliente: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al eliminar cliente: {str(e)}'}), 500

# --- APIs para Reportes de Pedidos ---
@panaderia_bp.route('/reportes_pedidos')
@login_required
def reportes_pedidos():
    """Página de generación de reportes de pedidos."""
    return render_template('panaderia/reportes_pedidos.html', title='Reportes de Pedidos')

@panaderia_bp.route('/api/reporte_por_vendedor', methods=['POST'])
@login_required
def api_reporte_por_vendedor():
    """API para generar reporte de ventas agrupadas por cliente."""
    try:
        data = request.get_json()
        
        # Parámetros de filtro
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        cliente_ids = data.get('clientes', [])  # Lista de IDs de clientes o vacío para todos
        filtro_estado = data.get('filtro_estado', 'ENTREGADO_PAGADO')  # Por defecto solo pagados
        
        # Construir query base
        query = PedidoPanaderia.query.join(ClientePanaderia)
        
        # Filtrar por fechas
        if fecha_inicio:
            try:
                fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
                query = query.filter(PedidoPanaderia.fecha_pedido >= fecha_inicio_dt)
            except:
                pass
        
        if fecha_fin:
            try:
                fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
                # Agregar 23:59:59 para incluir todo el día
                fecha_fin_dt = fecha_fin_dt.replace(hour=23, minute=59, second=59)
                query = query.filter(PedidoPanaderia.fecha_pedido <= fecha_fin_dt)
            except:
                pass
        
        # Filtrar por clientes
        if cliente_ids:
            query = query.filter(PedidoPanaderia.cliente_id.in_(cliente_ids))
        
        # Filtrar por estado
        if filtro_estado == 'TODOS_ENTREGADOS':
            query = query.filter(PedidoPanaderia.estado.in_(['ENTREGADO_PAGADO', 'ENTREGADO_NO_PAGADO']))
        else:
            query = query.filter(PedidoPanaderia.estado == filtro_estado)
        
        # Agrupar por cliente
        pedidos = query.all()
        
        # Procesar datos agrupados
        ventas_por_cliente = {}
        for pedido in pedidos:
            cliente_nombre = pedido.cliente.nombre if pedido.cliente else 'Sin cliente'
            
            if cliente_nombre not in ventas_por_cliente:
                ventas_por_cliente[cliente_nombre] = {
                    'nombre': cliente_nombre,
                    'cantidad_pedidos': 0,
                    'total_ventas': 0.0,
                    'total_items': 0
                }
            
            ventas_por_cliente[cliente_nombre]['cantidad_pedidos'] += 1
            ventas_por_cliente[cliente_nombre]['total_ventas'] += pedido.total
            ventas_por_cliente[cliente_nombre]['total_items'] += len(pedido.items)
        
        # Convertir a lista ordenada
        reporte = sorted(ventas_por_cliente.values(), key=lambda x: x['total_ventas'], reverse=True)
        
        # Calcular totales
        total_general = sum(item['total_ventas'] for item in reporte)
        pedidos_generales = sum(item['cantidad_pedidos'] for item in reporte)
        
        return jsonify({
            'success': True,
            'reporte': reporte,
            'total_general': total_general,
            'pedidos_generales': pedidos_generales
        })
        
    except Exception as e:
        current_app.logger.error(f"Error generando reporte por cliente: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al generar reporte: {str(e)}'}), 500

@panaderia_bp.route('/api/reporte_por_producto', methods=['POST'])
@login_required
def api_reporte_por_producto():
    """API para generar reporte de ventas agrupadas por producto."""
    try:
        data = request.get_json()
        
        # Parámetros de filtro
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        cliente_ids = data.get('clientes', [])
        producto_ids = data.get('productos', [])  # Lista de IDs de productos
        filtro_estado = data.get('filtro_estado', 'ENTREGADO_PAGADO')  # Por defecto solo pagados
        
        # Construir query base
        query = ItemPedidoPanaderia.query.join(PedidoPanaderia)
        
        # Filtrar por fechas
        if fecha_inicio:
            try:
                fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
                query = query.filter(PedidoPanaderia.fecha_pedido >= fecha_inicio_dt)
            except:
                pass
        
        if fecha_fin:
            try:
                fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
                # Agregar 23:59:59 para incluir todo el día
                fecha_fin_dt = fecha_fin_dt.replace(hour=23, minute=59, second=59)
                query = query.filter(PedidoPanaderia.fecha_pedido <= fecha_fin_dt)
            except:
                pass
        
        # Filtrar por clientes
        if cliente_ids:
            query = query.filter(PedidoPanaderia.cliente_id.in_(cliente_ids))
        
        # Filtrar por productos
        if producto_ids:
            query = query.filter(ItemPedidoPanaderia.producto_id.in_(producto_ids))
        
        # Filtrar por estado
        if filtro_estado == 'TODOS_ENTREGADOS':
            query = query.filter(PedidoPanaderia.estado.in_(['ENTREGADO_PAGADO', 'ENTREGADO_NO_PAGADO']))
        else:
            query = query.filter(PedidoPanaderia.estado == filtro_estado)
        
        # Obtener items
        items = query.all()
        
        # Procesar datos agrupados
        ventas_por_producto = {}
        for item in items:
            producto_nombre = item.producto.nombre if item.producto else 'Producto desconocido'
            
            if producto_nombre not in ventas_por_producto:
                ventas_por_producto[producto_nombre] = {
                    'nombre': producto_nombre,
                    'cantidad_total': 0,
                    'total_ventas': 0.0,
                    'pedidos_distintos': set()
                }
            
            ventas_por_producto[producto_nombre]['cantidad_total'] += item.cantidad
            ventas_por_producto[producto_nombre]['total_ventas'] += item.subtotal
            ventas_por_producto[producto_nombre]['pedidos_distintos'].add(item.pedido_id)
        
        # Convertir sets a cantidades
        for producto in ventas_por_producto.values():
            producto['pedidos_distintos'] = len(producto['pedidos_distintos'])
        
        # Convertir a lista ordenada
        reporte = sorted(ventas_por_producto.values(), key=lambda x: x['total_ventas'], reverse=True)
        
        # Calcular totales
        total_general = sum(item['total_ventas'] for item in reporte)
        productos_vendidos = len(reporte)
        
        return jsonify({
            'success': True,
            'reporte': reporte,
            'total_general': total_general,
            'productos_vendidos': productos_vendidos
        })
        
    except Exception as e:
        current_app.logger.error(f"Error generando reporte por producto: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al generar reporte: {str(e)}'}), 500

@panaderia_bp.route('/api/imprimir_reporte_80mm', methods=['POST'])
@login_required
def api_imprimir_reporte_80mm():
    """API para imprimir reporte en impresora térmica de 80mm."""
    try:
        from app.thermal_printer import imprimir_reporte_escpos
        
        data = request.get_json()
        tipo_reporte = data.get('tipo')  # 'vendedor' o 'producto'
        reporte_data = data.get('reporte')
        total_general = data.get('total_general', 0)
        fecha_inicio = data.get('fecha_inicio', '')
        fecha_fin = data.get('fecha_fin', '')
        filtro_estado = data.get('filtro_estado', 'ENTREGADO_PAGADO')
        
        # Generar comando ESC/POS para el reporte
        comando_escpos = imprimir_reporte_escpos(
            tipo_reporte=tipo_reporte,
            reporte_data=reporte_data,
            total_general=total_general,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            filtro_estado=filtro_estado
        )
        
        # Enviar a impresora
        if not current_app.config.get('IMPRESORA_HABILITADA', False):
            return jsonify({
                'success': False,
                'skipped': True,
                'message': 'Impresora deshabilitada en configuración'
            })
        
        impresora_ip = current_app.config.get('IMPRESORA_IP', '192.168.1.100')
        impresora_puerto = current_app.config.get('IMPRESORA_PUERTO', 9100)
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        current_app.logger.info(f"Imprimiendo reporte en {impresora_ip}:{impresora_puerto}")
        sock.connect((impresora_ip, impresora_puerto))
        sock.sendall(comando_escpos)
        sock.close()
        
        current_app.logger.info("Reporte impreso exitosamente")
        return jsonify({
            'success': True,
            'message': 'Reporte impreso exitosamente'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error imprimiendo reporte: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al imprimir: {str(e)}'}), 500


@panaderia_bp.route('/api/imprimir_lista_precios', methods=['POST'])
@login_required
def api_imprimir_lista_precios():
    try:
        productos = ProductoPanaderia.query.order_by(ProductoPanaderia.nombre.asc()).all()
        if not productos:
            return jsonify({'success': False, 'error': 'No hay productos registrados para imprimir.'}), 400

        resultado = imprimir_lista_precios(productos)
        if resultado.get('success'):
            return jsonify(resultado)

        status_code = 200 if resultado.get('skipped') else 500
        return jsonify(resultado), status_code
    except Exception as e:
        current_app.logger.error(f"Error imprimiendo lista de precios: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al imprimir lista de precios: {str(e)}'}), 500

# --- APIs para Mensajes a Cocina ---
@panaderia_bp.route('/api/enviar_mensaje_cocina', methods=['POST'])
@login_required
def api_enviar_mensaje_cocina():
    """API para enviar un mensaje a la cocina."""
    try:
        data = request.get_json()
        
        if not data or 'mensaje' not in data:
            return jsonify({'success': False, 'error': 'El mensaje es obligatorio'}), 400
        
        mensaje_texto = data.get('mensaje', '').strip()
        if not mensaje_texto:
            return jsonify({'success': False, 'error': 'El mensaje no puede estar vacío'}), 400
        
        prioridad = data.get('prioridad', 'normal')
        if prioridad not in ['normal', 'alta', 'urgente']:
            prioridad = 'normal'
        
        # Crear mensaje
        mensaje = MensajeCocina(
            mensaje=mensaje_texto,
            prioridad=prioridad,
            usuario_id=current_user.id
        )
        
        db.session.add(mensaje)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensaje_id': mensaje.id,
            'message': 'Mensaje enviado a la cocina exitosamente',
            'imprimir_automatico': False  # Se puede configurar para imprimir automáticamente
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error enviando mensaje a cocina: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al enviar mensaje: {str(e)}'}), 500

@panaderia_bp.route('/api/listar_mensajes_cocina')
@login_required
def api_listar_mensajes_cocina():
    """API para listar los últimos mensajes a la cocina."""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        mensajes = MensajeCocina.query.order_by(
            MensajeCocina.fecha_creacion.desc()
        ).limit(limit).all()
        
        mensajes_data = []
        for msg in mensajes:
            mensajes_data.append({
                'id': msg.id,
                'mensaje': msg.mensaje,
                'prioridad': msg.prioridad,
                'fecha_creacion': msg.fecha_creacion.isoformat(),
                'usuario': msg.usuario.nombre_completo if msg.usuario else 'Desconocido',
                'leido': msg.leido
            })
        
        return jsonify({'success': True, 'mensajes': mensajes_data})
        
    except Exception as e:
        current_app.logger.error(f"Error listando mensajes de cocina: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al listar mensajes: {str(e)}'}), 500

@panaderia_bp.route('/api/imprimir_mensaje_cocina/<int:mensaje_id>', methods=['POST'])
@login_required
def api_imprimir_mensaje_cocina(mensaje_id):
    """API para imprimir un mensaje a la cocina."""
    try:
        from app.thermal_printer import imprimir_mensaje_cocina
        
        mensaje = MensajeCocina.query.get_or_404(mensaje_id)
        
        # Intentar imprimir
        resultado = imprimir_mensaje_cocina(mensaje.id)
        
        if resultado.get('success'):
            return jsonify({
                'success': True,
                'message': 'Mensaje impreso exitosamente'
            })
        else:
            return jsonify({
                'success': False,
                'error': resultado.get('error', 'Error al imprimir mensaje')
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Error imprimiendo mensaje de cocina: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al imprimir: {str(e)}'}), 500

@panaderia_bp.route('/pantalla_cocina')
@login_required
def pantalla_cocina():
    """Pantalla para mostrar mensajes a la cocina en tiempo real."""
    return render_template('panaderia/pantalla_cocina.html', title='Pantalla de Cocina')