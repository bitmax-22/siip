# 📄 Configurar Apariencia y Tamaño de Tickets de Impresión

## Ubicaciones de Configuración

### 1. **Ancho del Papel** (config.py)

```python
IMPRESORA_ANCHO_MM = 80  # Cambiar a 58mm o 80mm
```

**Archivo:** `config.py` línea 56

---

### 2. **Formato y Estilo** (app/thermal_printer.py)

El archivo `app/thermal_printer.py` contiene TODO el formato del ticket.

#### **Caracteres por línea:**

```python
# Línea 43: Separadores horizontales
comando.extend(('=' * 32 + '\n').encode('utf-8'))  # Cambiar 32 por el ancho deseado

# Línea 52, 63, 70: Líneas divisorias
comando.extend(('-' * 32 + '\n').encode('utf-8'))

# Línea 78-79: Longitud de nombre de producto
if len(producto_nombre) > 28:  # Cambiar 28
    producto_nombre = producto_nombre[:25] + '...'  # Cambiar 25

# Línea 90: Alineación de subtotales
espacios = 32 - len(subtotal_str)  # Cambiar 32

# Línea 102: Alineación de total
espacios = 32 - len(total_str)  # Cambiar 32

# Línea 116: Longitud de observaciones
obs_lines = [pedido.observaciones[i:i+32] for i in range(0, len(pedido.observaciones), 32)]
# Cambiar 32
```

---

## Tabla de Referencia por Ancho de Papel

| Ancho Papel | Caracteres por Línea | IMPRESORA_ANCHO_MM |
|-------------|----------------------|---------------------|
| **58mm** | 32 caracteres | `58` |
| **80mm** | 48 caracteres | `80` |

---

## Comandos ESC/POS Importantes

| Código | Función | Línea en código |
|--------|---------|-----------------|
| `b'\x1B\x21\x38'` | Texto GRANDE + NEGRITA | 38 |
| `b'\x1B\x21\x08'` | Solo NEGRITA | 47, 55, 67, etc |
| `b'\x1B\x21\x00'` | Reset formato | 40, 49, etc |
| `b'\x1B\x61\x01'` | CENTRAR texto | 35, 42, 124 |
| `b'\x1B\x61\x00'` | Alinear IZQUIERDA | 44, 126 |
| `b'\x1D\x56\x00'` | CORTAR papel | 132 |

---

## Ejemplos de Cambios

### Cambiar a Impresora 58mm

```python
# config.py
IMPRESORA_ANCHO_MM = 58

# app/thermal_printer.py
comando.extend(('=' * 32 + '\n').encode('utf-8'))  # Ya está en 32, OK
```

### Cambiar a Impresora 80mm (tickets más anchos)

```python
# config.py
IMPRESORA_ANCHO_MM = 80

# app/thermal_printer.py - Cambiar todos los 32 por 48:
comando.extend(('=' * 48 + '\n').encode('utf-8'))
comando.extend(('-' * 48 + '\n').encode('utf-8'))
if len(producto_nombre) > 40:  # Aumentar de 28
    producto_nombre = producto_nombre[:37] + '...'  # Aumentar de 25
espacios = 48 - len(subtotal_str)  # Aumentar de 32
# etc...
```

---

## Cambiar Logo/Encabezado

**Línea 39 de app/thermal_printer.py:**

```python
comando.extend('PANADERIA SIIP\n'.encode('utf-8'))
# Cambiar a:
comando.extend('TU NOMBRE DE EMPRESA\n'.encode('utf-8'))
```

---

## Cambiar Mensaje Final

**Línea 125:**

```python
comando.extend('Gracias por su compra!\n'.encode('utf-8'))
# Cambiar a lo que quieras
```

---

## Ajustar Espaciado

```python
# Líneas vacías - agregar/quitar según necesites:
comando.extend('\n'.encode('utf-8'))  # Copiar esta línea
```

---

## Agregar Imagen (Avanzado)

Actualmente NO se imprimen imágenes en el ticket térmico.
Para agregar logo/imagen, necesitarías modificar el código ESC/POS para
incluir comandos de impresión de imagen raster (muy complejo).

---

## Después de Cambiar

1. Guardar archivos
2. **REINICIAR SIIP:**
   ```powershell
   python run.py
   ```
3. Hacer pedido de prueba
4. Verificar impresión

---

## Archivos Clave

| Archivo | Líneas Importantes | Qué Cambiar |
|---------|-------------------|-------------|
| `config.py` | 56 | Ancho de papel (mm) |
| `app/thermal_printer.py` | 35-134 | TODO el formato del ticket |

---

## Troubleshooting

**Problema:** Texto se corta al final  
**Solución:** Reducir caracteres por línea en app/thermal_printer.py

**Problema:** Ticket se ve muy pequeño  
**Solución:** Cambiar `IMPRESORA_ANCHO_MM` a 80 en config.py

**Problema:** No imprime después de cambios  
**Solución:** Reiniciar SIIP completamente

