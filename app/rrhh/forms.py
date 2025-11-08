from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, DateField, IntegerField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, Regexp

class RegistrarFuncionarioForm(FlaskForm):
    # Información Laboral
    region = StringField('Región', validators=[DataRequired()])
    estado_establecimiento = StringField('Estado del Establecimiento', validators=[DataRequired()])
    nombre_establecimiento = StringField('Nombre del Establecimiento', validators=[DataRequired()])
    direccion_adscripcion = StringField('Dirección de Adscripción', validators=[DataRequired()])
    fecha_ingreso_admon_publica = DateField('Fecha de Ingreso a la Adm. Pública', format='%d/%m/%Y', validators=[Optional()])
    fecha_ingreso_mppsp = DateField('Fecha de Ingreso al MPPSP', format='%d/%m/%Y', validators=[Optional()])
    cargo_adscripcion = StringField('Cargo de Adscripción', validators=[DataRequired()])
    cargo_funcional = StringField('Cargo Funcional', validators=[DataRequired()])
    tipo_personal = SelectField('Tipo de Personal', choices=[
        ('Seguridad y Custodia', 'Seguridad y Custodia'),
        ('Administrativo', 'Administrativo')
    ], validators=[DataRequired()])
    grado_instruccion = SelectField('Grado de Instrucción', choices=[
        ('Basico', 'Básico'), ('Bachiller', 'Bachiller'), ('TSU', 'TSU'), ('Universitario', 'Universitario')
    ], validators=[Optional()])
    profesion = StringField('Profesión', validators=[Optional()])

    # Información Personal
    nombres = StringField('Nombres', validators=[DataRequired(), Length(min=2, max=100)])
    apellidos = StringField('Apellidos', validators=[DataRequired(), Length(min=2, max=100)])
    cedula = StringField('Cédula', validators=[DataRequired(), Regexp('^[0-9]+$', message='Solo se permiten números en la cédula.')])
    sexo = SelectField('Sexo', choices=[('M', 'Masculino'), ('F', 'Femenino')], validators=[DataRequired()])
    fecha_nacimiento = DateField('Fecha de Nacimiento', format='%d/%m/%Y', validators=[Optional()])
    direccion_habitacion = StringField('Dirección de Habitación', validators=[Optional()])
    # Campos para la foto
    foto_subida = FileField('Cargar Foto de Perfil', validators=[FileAllowed(['jpg', 'jpeg', 'png'], '¡Solo imágenes!')])
    foto_tomada = HiddenField('Foto Tomada (Base64)')
    estado_residencia = StringField('Estado de Residencia', validators=[Optional()])
    telefono = StringField('Número Telefónico', validators=[Optional()])
    correo_electronico = StringField('Correo Electrónico', validators=[Optional()])

    # Información de Tallas y Pago
    talla_camisa = StringField('Talla de Camisa', validators=[Optional()])
    talla_pantalon = StringField('Talla de Pantalón', validators=[Optional()])
    talla_zapatos = StringField('Talla de Zapatos', validators=[Optional()])
    numero_cuenta = StringField('Número de Cuenta (20 dígitos)', validators=[Optional(), Length(min=20, max=20)])
    pago_movil_cedula = StringField('Pago Móvil (Cédula)', validators=[Optional()])
    pago_movil_banco = StringField('Pago Móvil (Banco)', validators=[Optional()])
    pago_movil_telefono = StringField('Pago Móvil (Teléfono)', validators=[Optional()])

    # Estatus
    observaciones_estatus = TextAreaField('Observaciones de Estatus (Discapacidad, etc.)', validators=[Optional()])

    submit = SubmitField('Registrar Funcionario')

class ActualizarEstatusForm(FlaskForm):
    """Formulario para actualizar el estatus de un funcionario."""
    estatus_actual = SelectField('Nuevo Estatus', choices=[
        ('Activo', 'Activo'),
        ('De Reposo', 'De Reposo'),
        ('De Permiso', 'De Permiso'),
        ('Retardo', 'Retardo'),
        ('Jubilado', 'Jubilado'),
        ('Egresado', 'Egresado'),
        ('Pasivo', 'Pasivo')
    ], validators=[DataRequired()])
    observaciones_estatus = TextAreaField('Observaciones', validators=[Optional(), Length(max=255)])
    submit = SubmitField('Actualizar Estatus')

class CargarReposoForm(FlaskForm):
    """Formulario para cargar un documento de reposo."""
    reposo_file = FileField('Seleccionar Documento', validators=[
        DataRequired(),
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], '¡Solo se permiten imágenes (JPG, PNG) y PDF!')
    ])
    descripcion = TextAreaField('Descripción (Opcional)', validators=[Optional(), Length(max=255)])
    submit = SubmitField('Cargar Documento')