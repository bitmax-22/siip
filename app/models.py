# c:\Users\Administrator\Desktop\SIIP CON FOTO\app\models.py
from .extensions import db # Importar db desde extensions
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm.attributes import flag_modified # Para marcar el JSON como modificado
from datetime import datetime # Asegúrate de que datetime esté importado si usas db.Date o db.DateTime
from flask_login import UserMixin

# Si usas Flask-Login, UserMixin es común:
# from flask_login import UserMixin
# class User(UserMixin, db.Model):
class User(UserMixin, db.Model):
    __tablename__ = 'user' # Es una buena práctica definir explícitamente el nombre de la tabla

    id = db.Column(db.Integer, primary_key=True) # Clave primaria estándar
    # 'username' es el código/username para login, como estaba antes.
    # Si quieres que el campo de login se llame 'user_id' como en la discusión previa,
    # puedes cambiar 'username' a 'user_id' aquí y en app/auth.py en User.query.filter_by(username=username)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) # Longitud aumentada para hashes modernos
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # Nuevos campos solicitados
    nombre_completo = db.Column(db.String(120), nullable=False) # Nombre real del usuario
    cargo = db.Column(db.String(80), nullable=True) # Cargo del usuario, puede ser opcional

    # Permisos granulares por módulo
    permiso_chat = db.Column(db.Boolean, default=True, nullable=False)  # Chat Asistente
    permiso_dashboard = db.Column(db.Boolean, default=True, nullable=False)  # Situación Actual
    permiso_resena = db.Column(db.Boolean, default=True, nullable=False)  # Reseña Fotográfica
    permiso_usuarios = db.Column(db.Boolean, default=False, nullable=False)  # Gestionar Usuarios
    permiso_familiares = db.Column(db.Boolean, default=False, nullable=False)  # Gestionar Familiares PDL
    permiso_rrhh = db.Column(db.Boolean, default=False, nullable=False)  # Gestión RRHH
    permiso_panaderia = db.Column(db.Boolean, default=False, nullable=False)  # Gestión Panadería

    # Relación con las conversaciones
    # cascade="all, delete-orphan" asegura que las conversaciones se borren si el usuario se borra.
    conversations = db.relationship('Conversation', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        # password_hash no debería ser None debido a nullable=False, pero es una buena comprobación.
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False

    def __repr__(self):
        return f'<User {self.username} ({self.nombre_completo})>'

class Conversation(db.Model):
    __tablename__ = 'conversation'
    id = db.Column(db.Integer, primary_key=True)
    # user_id es la ForeignKey a la tabla 'user', columna 'id'.
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_conversation_user_id'), nullable=False, index=True)
    # Usaremos JSON para almacenar la lista de mensajes. SQLite lo soporta.
    # Usar lambda para default asegura que se cree una nueva lista para cada instancia.
    history_data = db.Column(db.JSON, nullable=False, default=lambda: [])

    created_at = db.Column(db.DateTime, default=datetime.utcnow) # Usar utcnow para consistencia
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # El backref 'user' ya está definido en la relación de User.
    # No es necesario definir db.relationship aquí de nuevo si ya está en User.
    # Si se define, debe ser consistente. Por simplicidad, se maneja desde User.

    def __repr__(self):
        return f'<Conversation id={self.id} user_id={self.user_id} messages={len(self.history_data) if isinstance(self.history_data, list) else 0}>'

    def get_history(self):
        return self.history_data if isinstance(self.history_data, list) else []

    def add_message(self, role, content):
        if not isinstance(self.history_data, list):
            self.history_data = [] # Asegurar que sea una lista si por alguna razón no lo es
        
        # Limitar la longitud del mensaje si es necesario antes de añadirlo
        max_msg_length = 10000 # Ejemplo, ajusta según necesidad
        truncated_content = content[:max_msg_length] + '...' if len(content) > max_msg_length else content

        self.history_data.append(f"{role}: {truncated_content}")
        flag_modified(self, "history_data") # Asegurar que SQLAlchemy detecte el cambio en JSON

# --- Modelo para Privados de Libertad (PDL) ---
class PDL(db.Model):
    __tablename__ = 'pdl'
    id = db.Column(db.Integer, primary_key=True)
    # Asumimos que la cédula es el identificador principal del PDL proveniente del Google Sheet
    cedula = db.Column(db.String(25), unique=True, nullable=False, index=True)
    nombre_completo = db.Column(db.String(200), nullable=False)
    # Puedes añadir otros campos relevantes del PDL que quieras persistir desde el Google Sheet
    # Ejemplo:
    # establecimiento_actual = db.Column(db.String(150))
    # delito_principal = db.Column(db.String(250))

    # Relación con los familiares
    familiares = db.relationship('Familiar', backref='pdl_asociado', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<PDL {self.cedula} - {self.nombre_completo}>'

# --- Modelo para Familiares ---
class Familiar(db.Model):
    __tablename__ = 'familiar'
    id = db.Column(db.Integer, primary_key=True)
    pdl_id = db.Column(db.Integer, db.ForeignKey('pdl.id', name='fk_familiar_pdl_id'), nullable=False, index=True)
    nombre_completo = db.Column(db.String(200), nullable=False)
    cedula_familiar = db.Column(db.String(25), nullable=True) # Cédula del familiar, opcional y no necesariamente única globalmente
    parentesco = db.Column(db.String(50), nullable=False) # Ej: Madre, Padre, Hermano/a, Hijo/a, Cónyuge, Otro
    telefono = db.Column(db.String(30), nullable=True)
    direccion = db.Column(db.String(250), nullable=True)
    ultima_visita_fecha = db.Column(db.Date, nullable=True) # Fecha de la última visita

    def __repr__(self):
        return f'<Familiar {self.nombre_completo} (PDL ID: {self.pdl_id})>'

# --- Modelo para Funcionarios (NUEVO) ---
class Funcionario(db.Model):
    __tablename__ = 'funcionario'
    id = db.Column(db.Integer, primary_key=True)
    
    # Información Personal
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    cedula = db.Column(db.String(25), unique=True, nullable=False, index=True)
    sexo = db.Column(db.String(10), nullable=True)
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    direccion_habitacion = db.Column(db.String(250), nullable=True)
    estado_residencia = db.Column(db.String(100), nullable=True)
    telefono = db.Column(db.String(30), nullable=True)
    correo_electronico = db.Column(db.String(120), nullable=True)
    foto_path = db.Column(db.String(255), nullable=True) # Ruta a la foto del funcionario

    # Información Laboral
    region = db.Column(db.String(100), nullable=True)
    estado_establecimiento = db.Column(db.String(100), nullable=True)
    nombre_establecimiento = db.Column(db.String(150), nullable=True)
    direccion_adscripcion = db.Column(db.String(250), nullable=True)
    fecha_ingreso_admon_publica = db.Column(db.Date, nullable=True)
    fecha_ingreso_mppsp = db.Column(db.Date, nullable=True)
    anos_servicio = db.Column(db.Integer, nullable=True)
    cargo_adscripcion = db.Column(db.String(100), nullable=True)
    cargo_funcional = db.Column(db.String(100), nullable=True)
    tipo_personal = db.Column(db.String(50), nullable=False) # 'Seguridad y Custodia' o 'Administrativo'
    grado_instruccion = db.Column(db.String(50), nullable=True)
    profesion = db.Column(db.String(100), nullable=True)

    # Información de Tallas y Pago
    talla_camisa = db.Column(db.String(10), nullable=True)
    talla_pantalon = db.Column(db.String(10), nullable=True)
    talla_zapatos = db.Column(db.String(10), nullable=True)
    numero_cuenta = db.Column(db.String(20), nullable=True)
    pago_movil_cedula = db.Column(db.String(25), nullable=True)
    pago_movil_banco = db.Column(db.String(50), nullable=True)
    pago_movil_telefono = db.Column(db.String(30), nullable=True)

    # Estatus Laboral
    estatus_actual = db.Column(db.String(50), nullable=False, default='Activo') # Ej: Activo, De Guardia, Permiso, Reposo, Vacaciones, Baja
    fecha_inicio_estatus = db.Column(db.Date, nullable=True)
    fecha_fin_estatus = db.Column(db.Date, nullable=True)
    observaciones_estatus = db.Column(db.Text, nullable=True) # Para discapacidad u otras observaciones

    # Relación con Reposo
    reposos = db.relationship('Reposo', backref='funcionario', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Funcionario {self.cedula} - {self.nombres} {self.apellidos}>'

class Reposo(db.Model):
    """Modelo para los documentos de reposo de los funcionarios."""
    __tablename__ = 'reposo'
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(255), nullable=False)
    descripcion = db.Column(db.String(255))
    fecha_carga = db.Column(db.DateTime, default=datetime.utcnow)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)

    def __repr__(self):
        return f"<Reposo {self.id} - {self.file_path}>"

# --- Modelos para Leyes y Artículos (si los tienes en este archivo) ---
# class Ley(db.Model):
#     __tablename__ = 'ley'
#     id = db.Column(db.Integer, primary_key=True)
#     nombre_ley = db.Column(db.String(255), unique=True, nullable=False)
#     articulos = db.relationship('Articulo', backref='ley', lazy='dynamic', cascade="all, delete-orphan")

#     def __repr__(self):
#         return f'<Ley {self.nombre_ley}>'

# class Articulo(db.Model):
#     __tablename__ = 'articulo'
#     id = db.Column(db.Integer, primary_key=True)
#     ley_id = db.Column(db.Integer, db.ForeignKey('ley.id', name='fk_articulo_ley_id'), nullable=False)
#     numero_articulo = db.Column(db.String(50), nullable=False) # Ej: "Artículo 1", "Art. 15 bis"
#     contenido = db.Column(db.Text, nullable=False)
#     # Para búsqueda textual completa si tu DB lo soporta (ej. PostgreSQL)
#     # contenido_tsv = db.Column(TSVectorType('contenido', regconfig='pg_catalog.spanish'))

#     # Índice compuesto para asegurar que un artículo sea único dentro de una ley
#     __table_args__ = (db.UniqueConstraint('ley_id', 'numero_articulo', name='uq_ley_articulo'),
#                       # db.Index('idx_articulo_contenido_tsv', 'contenido_tsv', postgresql_using='gin') # Ejemplo para FTS
#                      )

# --- Modelos para la Panadería ---

class ProductoPanaderia(db.Model):
    __tablename__ = 'producto_panaderia'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    costo_produccion = db.Column(db.Float, nullable=False)
    precio_regular = db.Column(db.Float, nullable=False)
    precio_minimo = db.Column(db.Float, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    producciones = db.relationship('ProduccionDiaria', backref='producto', lazy=True, cascade="all, delete-orphan")
    ventas = db.relationship(
        'VentaDiaria',
        secondary='produccion_diaria', # Esta es la tabla de asociación
        primaryjoin='ProductoPanaderia.id == ProduccionDiaria.producto_id',
        secondaryjoin='ProduccionDiaria.id == VentaDiaria.produccion_id',
        lazy=True
    )

    def __repr__(self):
        return f'<ProductoPanaderia {self.nombre}>'

class Vendedor(db.Model):
    __tablename__ = 'vendedor'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    telefono = db.Column(db.String(30), nullable=True)
    direccion = db.Column(db.String(250), nullable=True)

    ventas = db.relationship('VentaDiaria', backref='vendedor', lazy=True, cascade="all, delete-orphan")
    movimientos = db.relationship('MovimientoVendedor', backref='vendedor_movimiento', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Vendedor {self.nombre}>'

class ProduccionDiaria(db.Model):
    __tablename__ = 'produccion_diaria'
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto_panaderia.id'), nullable=False)
    fecha_produccion = db.Column(db.Date, nullable=False, default=datetime.utcnow().date()) # Solo fecha
    cantidad_producida = db.Column(db.Integer, nullable=False)
    costo_total_produccion = db.Column(db.Float, nullable=False) # Calculado al guardar

    ventas_asociadas = db.relationship('VentaDiaria', backref='produccion_origen', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<ProduccionDiaria {self.producto.nombre} - {self.fecha_produccion} - {self.cantidad_producida}>'

class VentaDiaria(db.Model):
    __tablename__ = 'venta_diaria'
    id = db.Column(db.Integer, primary_key=True)
    produccion_id = db.Column(db.Integer, db.ForeignKey('produccion_diaria.id'), nullable=False)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('vendedor.id'), nullable=False)
    cantidad_vendida = db.Column(db.Integer, nullable=False)
    precio_total_venta = db.Column(db.Float, nullable=False) # Calculado al guardar
    fecha_venta = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    tipo_venta = db.Column(db.String(50), nullable=False, default='DESPACHO')

    # Relación con MovimientoVendedor para el despacho
    movimiento_despacho = db.relationship('MovimientoVendedor', backref='venta_asociada', lazy=True, uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<VentaDiaria {self.produccion_origen.producto.nombre} - {self.cantidad_vendida} a {self.vendedor.nombre}>'

class MovimientoVendedor(db.Model):
    __tablename__ = 'movimiento_vendedor'
    id = db.Column(db.Integer, primary_key=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('vendedor.id'), nullable=False)
    fecha_movimiento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    tipo_movimiento = db.Column(db.String(50), nullable=False) # 'DESPACHO' o 'PAGO'
    monto = db.Column(db.Float, nullable=False) # Positivo para despacho, negativo para pago
    venta_id = db.Column(db.Integer, db.ForeignKey('venta_diaria.id'), nullable=True) # Opcional, solo para tipo 'DESPACHO'
    descripcion = db.Column(db.String(250), nullable=True)

    def __repr__(self):
        return f'<MovimientoVendedor {self.tipo_movimiento} - {self.monto} para {self.vendedor_movimiento.nombre}>'

# --- Modelos para el Sistema de Pedidos de Panadería ---

class ClientePanaderia(db.Model):
    __tablename__ = 'cliente_panaderia'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False) # Nombre del cliente
    telefono = db.Column(db.String(30), nullable=True) # Teléfono del cliente
    direccion = db.Column(db.String(500), nullable=True) # Dirección del cliente
    fecha_registro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    activo = db.Column(db.Boolean, nullable=False, default=True) # Si el cliente está activo
    
    # Tipo de precio
    precio_minimo = db.Column(db.Boolean, nullable=False, default=False) # Usar precio mínimo del producto
    precio_regular = db.Column(db.Boolean, nullable=False, default=True) # Usar precio regular (default)
    precio_regalia = db.Column(db.Boolean, nullable=False, default=False) # Todo a precio 0
    
    # Relaciones
    pedidos = db.relationship('PedidoPanaderia', backref='cliente', lazy=True)
    
    def __repr__(self):
        return f'<ClientePanaderia {self.nombre} - {self.telefono or "Sin teléfono"}>'

class PedidoPanaderia(db.Model):
    __tablename__ = 'pedido_panaderia'
    id = db.Column(db.Integer, primary_key=True)
    numero_pedido = db.Column(db.String(50), unique=True, nullable=False, index=True) # Ej: PED-001-20250101
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente_panaderia.id'), nullable=True)
    fecha_pedido = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    fecha_entrega = db.Column(db.DateTime, nullable=True) # Fecha programada de entrega
    estado = db.Column(db.String(50), nullable=False, default='CONFIRMADO') # CONFIRMADO, ENTREGADO_PAGADO, ENTREGADO_NO_PAGADO, CANCELADO
    total = db.Column(db.Float, nullable=False, default=0.0)
    observaciones = db.Column(db.Text, nullable=True) # Observaciones del pedido
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Usuario que creó el pedido
    
    # Relaciones
    items = db.relationship('ItemPedidoPanaderia', backref='pedido', lazy=True, cascade="all, delete-orphan")
    usuario = db.relationship('User', backref='pedidos_panaderia')
    
    def __repr__(self):
        return f'<PedidoPanaderia {self.numero_pedido} - Cliente ID: {self.cliente_id} - {self.estado}>'

class ItemPedidoPanaderia(db.Model):
    __tablename__ = 'item_pedido_panaderia'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido_panaderia.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto_panaderia.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False) # Precio al momento de hacer el pedido
    subtotal = db.Column(db.Float, nullable=False) # Calculado: cantidad * precio_unitario
    
    # Relación con producto
    producto = db.relationship('ProductoPanaderia', backref='items_pedidos')
    
    def __repr__(self):
        return f'<ItemPedidoPanaderia {self.producto.nombre} x{self.cantidad}>'

# --- Modelo para Mensajes a Cocina ---
class MensajeCocina(db.Model):
    __tablename__ = 'mensaje_cocina'
    id = db.Column(db.Integer, primary_key=True)
    mensaje = db.Column(db.Text, nullable=False)
    prioridad = db.Column(db.String(20), nullable=False, default='normal')  # normal, alta, urgente
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    leido = db.Column(db.Boolean, nullable=False, default=False)
    fecha_leido = db.Column(db.DateTime, nullable=True)
    
    # Relación con usuario
    usuario = db.relationship('User', backref='mensajes_cocina')
    
    def __repr__(self):
        return f'<MensajeCocina {self.id} - {self.prioridad} - {self.fecha_creacion}>'
