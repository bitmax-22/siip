# Sistema de Permisos Granulares - SIIP

## 📋 Descripción

El sistema SIIP ahora cuenta con un sistema de permisos granulares que permite controlar el acceso de cada usuario a módulos específicos del sistema.

## 🔐 Permisos Disponibles

Cada usuario puede tener acceso individual a los siguientes módulos:

1. **Chat Asistente** (`permiso_chat`)
   - Acceso al chat con inteligencia artificial
   - Consultas sobre información penitenciaria

2. **Situación Actual - Dashboard** (`permiso_dashboard`)
   - Visualización de gráficos y estadísticas
   - Resumen de la situación penitenciaria actual

3. **Reseña Fotográfica** (`permiso_resena`)
   - Captura de fotografías de PDLs
   - Gestión de reseñas fotográficas

4. **Gestionar Usuarios** (`permiso_usuarios`)
   - Crear, editar y gestionar usuarios del sistema
   - Asignar permisos a otros usuarios

5. **Gestionar Familiares PDL** (`permiso_familiares`)
   - Registro y gestión de familiares
   - Administración de visitas

6. **Gestión RRHH** (`permiso_rrhh`)
   - Gestión de recursos humanos
   - Administración de funcionarios

7. **Gestión Panadería** (`permiso_panaderia`)
   - Control de producción
   - Gestión de ventas y productos

## 👤 Gestión de Usuarios

### Crear Nuevo Usuario

1. Acceder a "Gestionar Usuarios" (requiere `permiso_usuarios` o ser administrador)
2. Llenar el formulario con:
   - Nombre de usuario
   - Nombre completo
   - Cargo
   - Contraseña
   - Checkbox "Es Administrador" (opcional)
   - Seleccionar permisos específicos para cada módulo

3. Click en "Crear Usuario"

### Editar Usuario Existente

1. En la lista de usuarios, click en "Editar"
2. Modificar los datos necesarios
3. Marcar/desmarcar los permisos según sea necesario
4. Click en "Actualizar Usuario"

### Permisos por Defecto

**Usuarios nuevos:**
- ✅ Chat Asistente
- ✅ Situación Actual
- ✅ Reseña Fotográfica
- ❌ Gestionar Usuarios
- ❌ Gestionar Familiares PDL
- ❌ Gestión RRHH
- ❌ Gestión Panadería

**Usuarios administradores:**
- ✅ Todos los permisos habilitados automáticamente

## 🛡️ Seguridad

### Decoradores de Permisos

El sistema incluye decoradores en el código para proteger rutas:

```python
from app.auth import chat_required, dashboard_required, resena_required

@bp.route('/chat')
@chat_required
def chat_route():
    # Solo accesible si el usuario tiene permiso_chat
    pass
```

### Decoradores Disponibles:

- `@chat_required` - Chat Asistente
- `@dashboard_required` - Dashboard
- `@resena_required` - Reseña Fotográfica
- `@usuarios_required` - Gestión de Usuarios
- `@familiares_required` - Gestión de Familiares
- `@rrhh_required` - Gestión RRHH
- `@panaderia_required` - Gestión Panadería
- `@admin_required` - Solo administradores

## 📊 Base de Datos

### Campos Agregados a la Tabla `user`:

```sql
permiso_chat BOOLEAN DEFAULT TRUE NOT NULL
permiso_dashboard BOOLEAN DEFAULT TRUE NOT NULL
permiso_resena BOOLEAN DEFAULT TRUE NOT NULL
permiso_usuarios BOOLEAN DEFAULT FALSE NOT NULL
permiso_familiares BOOLEAN DEFAULT FALSE NOT NULL
permiso_rrhh BOOLEAN DEFAULT FALSE NOT NULL
permiso_panaderia BOOLEAN DEFAULT FALSE NOT NULL
```

## 🎯 Mejores Prácticas

1. **Principio de Mínimo Privilegio**: Asignar solo los permisos necesarios para cada usuario

2. **Revisión Periódica**: Revisar regularmente los permisos asignados

3. **Documentación**: Mantener registro de quién tiene acceso a qué módulos

4. **Separación de Responsabilidades**: No todos los usuarios necesitan acceso a todos los módulos

## ⚠️ Importante

- Los **administradores** (`is_admin = True`) tienen acceso automático a todos los módulos
- Si un usuario no tiene permisos para ningún módulo, no podrá acceder al sistema
- Los enlaces del menú de navegación solo aparecen si el usuario tiene el permiso correspondiente
- Intentar acceder directamente a una URL sin permisos redirige con mensaje de error

## 🔄 Migración

Los usuarios existentes en la base de datos fueron actualizados automáticamente:

- Usuarios regulares: permisos básicos (chat, dashboard, reseña)
- Administradores: todos los permisos habilitados

---

**Última actualización:** Octubre 2025
**Versión:** 2.0





