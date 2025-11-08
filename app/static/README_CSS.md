# Estructura de CSS del Proyecto SIIP

## Archivos CSS Independientes por Módulo

Este proyecto utiliza archivos CSS separados para cada módulo principal, lo que garantiza que los cambios visuales en una página no afecten a las demás.

### Archivos CSS Disponibles:

1. **style.css** - Estilos globales comunes
   - Estilos básicos del login
   - Estilos compartidos por todas las páginas

2. **chat.css** - Módulo de Chat Asistente
   - Layout del chat con fondo degradado azul
   - Estilos de mensajes (usuario y bot)
   - Área de input y botones
   - Responsive para móviles

3. **dashboard.css** - Módulo de Situación Actual (Dashboard)
   - Fondo degradado azul
   - Estilos de tarjetas de conteo
   - Contenedores de gráficos
   - Layout del dashboard

4. **resena.css** - Módulo de Reseña Fotográfica
   - Fondo degradado azul
   - Estilos del video feed
   - Previsualizaciones de fotos
   - Botones personalizados
   - Formularios con tema oscuro

### Cómo Usar:

Cada plantilla HTML carga su CSS específico en el bloque `{% block styles %}`:

```html
{% block styles %}
    <!-- CSS específico del módulo -->
    <link rel="stylesheet" href="{{ url_for('static', filename='nombre_modulo.css') }}">
{% endblock %}
```

### Ventajas de esta Estructura:

✅ **Independencia**: Los cambios en un módulo no afectan a otros
✅ **Mantenibilidad**: Más fácil encontrar y modificar estilos específicos
✅ **Performance**: Solo se cargan los estilos necesarios por página
✅ **Organización**: Código más limpio y estructurado
✅ **Escalabilidad**: Fácil añadir nuevos módulos

### Agregar un Nuevo Módulo:

1. Crear archivo `app/static/nuevo_modulo.css`
2. Definir estilos específicos del módulo
3. Cargar en la plantilla HTML:
   ```html
   <link rel="stylesheet" href="{{ url_for('static', filename='nuevo_modulo.css') }}">
   ```

---
**Última actualización:** Octubre 2025


