from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, DateField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, Optional
from datetime import date

class ProductoPanaderiaForm(FlaskForm):
    nombre = StringField('Nombre del Producto', validators=[DataRequired()])
    costo_produccion = FloatField('Costo de Producción', validators=[DataRequired(), NumberRange(min=0)])
    precio_regular = FloatField('Precio Regular', validators=[DataRequired(), NumberRange(min=0)])
    precio_minimo = FloatField('Precio Mínimo', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Guardar Producto')

class VendedorForm(FlaskForm):
    nombre = StringField('Nombre del Vendedor', validators=[DataRequired()])
    telefono = StringField('Teléfono', validators=[Optional()])
    direccion = TextAreaField('Dirección', validators=[Optional()])
    submit = SubmitField('Guardar Vendedor')

class ProduccionDiariaForm(FlaskForm):
    producto_id = SelectField('Producto', coerce=int, validators=[DataRequired()])
    fecha_produccion = DateField('Fecha de Producción', format='%Y-%m-%d', default=date.today, validators=[DataRequired()])
    cantidad_producida = IntegerField('Cantidad Producida', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Registrar Producción')

class VentaDiariaForm(FlaskForm):
    produccion_id = SelectField('Producción Origen', coerce=int, validators=[DataRequired()])
    vendedor_id = SelectField('Vendedor', coerce=int, validators=[DataRequired()])
    cantidad_vendida = IntegerField('Cantidad Vendida', validators=[DataRequired(), NumberRange(min=1)])
    fecha_venta = DateField('Fecha de Venta', format='%Y-%m-%d', default=date.today, validators=[DataRequired()])
    submit = SubmitField('Registrar Venta')

class MovimientoVendedorForm(FlaskForm):
    vendedor_id = SelectField('Vendedor', coerce=int, validators=[DataRequired()])
    tipo_movimiento = SelectField('Tipo de Movimiento', choices=[('DESPACHO', 'Despacho'), ('PAGO', 'Pago')], validators=[DataRequired()])
    monto = FloatField('Monto', validators=[DataRequired()])
    descripcion = TextAreaField('Descripción', validators=[Optional()])
    submit = SubmitField('Registrar Movimiento')