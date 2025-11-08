# 🗄️ Sistema de Respaldos Automáticos - SIIP

## Descripción General

El sistema SIIP ahora cuenta con una **rutina de respaldos automáticos** que se ejecuta periódicamente sin intervención manual. Esta funcionalidad está integrada con **APScheduler** y garantiza la protección continua de tus datos críticos.

## ✅ Características

- ✅ **Respaldos Automáticos**: Se ejecutan periódicamente según configuración
- ✅ **Respaldos Multi-Localización**: Respaldos locales + Google Drive
- ✅ **Notificaciones por Email**: Recibes un correo con el resultado de cada backup
- ✅ **Respaldos Incrementales**: Cada backup tiene timestamp único
- ✅ **Configuración Flexible**: Fácil de habilitar/deshabilitar y ajustar frecuencia

## ⚙️ Configuración

### En `config.py`

```python
# Configuración de Backup Automático
BACKUP_ENABLED = True  # Habilitar o deshabilitar backups automáticos
BACKUP_INTERVAL_HOURS = 24  # Frecuencia de backups (en horas)
BACKUP_LOCAL_DIR = os.path.join(app_dir, 'chat', 'temp_backups')
BACKUP_DRIVE_SERVICE_ACCOUNT_FILE = os.path.join('C:\\KEYS', 'proyecto-excel-cfhn-ef8feac76292.json')
BACKUP_DRIVE_FOLDER_ID = '1me9w0CtF_YhvFSjIcEh2CEOBv38qGeON'

# Configuración de Email para Notificaciones de Backup
BACKUP_SMTP_SERVER = 'smtp.gmail.com'
BACKUP_SMTP_PORT = 587
BACKUP_SMTP_USER = 'americovargas22@gmail.com'
BACKUP_SMTP_PASSWORD = 'oiqs iugt bald egsk'
BACKUP_EMAIL_TO = 'americovargas22@gmail.com'
```

### Parámetros Importantes

| Parámetro | Descripción | Valor Recomendado |
|-----------|-------------|-------------------|
| `BACKUP_ENABLED` | Habilita/deshabilita backups automáticos | `True` |
| `BACKUP_INTERVAL_HOURS` | Frecuencia de backups en horas | `24` (diario) |
| `BACKUP_LOCAL_DIR` | Carpeta local para respaldos temporales | `app/chat/temp_backups` |
| `BACKUP_DRIVE_FOLDER_ID` | ID de carpeta en Google Drive | Configurar según tu Drive |

## 📁 Estructura de Archivos

```
SIIP CON FOTO/
├── config.py                     # Configuración de backup
├── app/
│   ├── __init__.py              # Integración con APScheduler
│   └── chat/
│       ├── backup_routine.py    # Script principal de backup
│       └── temp_backups/        # Respaldos locales
│           └── YYYYMMDD_HHMMSS_run/
│               ├── siip_database_YYYYMMDD_HHMMSS.db
│               └── SIIP_Project_Backup_YYYYMMDD_HHMMSS.zip
├── test_backup.py               # Script de prueba
└── BACKUP_AUTOMATICO.md         # Esta documentación
```

## 🔄 Cómo Funciona

### Proceso de Backup Automático

1. **APScheduler** inicia la tarea según el intervalo configurado
2. Se crea un directorio temporal con timestamp
3. Se respalda la base de datos `siip_database.db`
4. Se comprime todo el proyecto (excepto archivos excluidos)
5. Los archivos se suben a Google Drive
6. Se envía notificación por email con el resultado

### Archivos Excluidos

Los siguientes archivos/directorios **NO** se incluyen en los respaldos:

- `__pycache__/` (caché de Python)
- `*.pyc` (bytecode compilado)
- `.git/` (si existe repositorio Git)
- `venv/` (entorno virtual)
- `app/chat/temp_backups/` (respaldos anteriores)

## 🚀 Uso

### Automático (Configurado por Defecto)

Los backups se ejecutan automáticamente cuando inicias la aplicación:

```bash
python run.py
```

Verás este mensaje en consola:
```
APScheduler configurado para backups automáticos cada 24 horas.
```

### Manual (Para Pruebas)

Puedes ejecutar un backup manual para probar:

```bash
python test_backup.py
```

O ejecutar el script de backup directamente:

```bash
python -m app.chat.backup_routine
```

## 📧 Notificaciones por Email

Después de cada backup (exitoso o con errores), recibirás un email con:

- ✅ **Estado del backup** (exitoso o con errores)
- 📋 **Lista de archivos respaldados**
- 🔗 **Enlaces a Google Drive** (si está configurado)
- ⚠️ **Mensajes de error** (si ocurrieron)

### Ejemplo de Email

```
Asunto: [SIIP Backup] Respaldo SIIP Completado Exitosamente

La rutina de respaldo del SIIP se completó exitosamente.

Archivos en este respaldo:
- siip_database_20250115_120000.db (Drive: https://drive.google.com/...)
- SIIP_Project_Backup_20250115_120001.zip (Drive: https://drive.google.com/...)
```

## 🔧 Troubleshooting

### Los backups no se están ejecutando

1. Verifica que `BACKUP_ENABLED = True` en `config.py`
2. Revisa los logs de la aplicación en consola
3. Asegúrate de que APScheduler esté configurado correctamente

### Error al subir a Google Drive

1. Verifica que el archivo de credenciales existe en `C:\KEYS\proyecto-excel-cfhn-ef8feac76292.json`
2. Asegúrate de tener las librerías instaladas:
   ```bash
   pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
   ```
3. Verifica que el `BACKUP_DRIVE_FOLDER_ID` sea correcto

### Error al enviar email

1. Verifica las credenciales SMTP en `config.py`
2. Para Gmail, asegúrate de usar una "Contraseña de aplicación"
3. Revisa el firewall y puerto SMTP (587)

### Backup no encuentra la base de datos

1. Verifica que `siip_database.db` existe en la raíz del proyecto
2. Asegúrate de que la aplicación SIIP esté detenida durante el backup

## 📊 Monitoreo

### Logs de APScheduler

Los logs del scheduler aparecen en la consola:

```
INFO - Iniciando tarea programada: Backup automático del sistema SIIP.
INFO - Base de datos respaldada en: app/chat/temp_backups/20250115_120000_run/siip_database_20250115_120000.db
INFO - Proyecto archivado en: app/chat/temp_backups/20250115_120000_run/SIIP_Project_Backup_20250115_120001.zip
INFO - Tarea de backup completada exitosamente.
```

### Limpieza de Respaldos Antiguos

Actualmente los respaldos locales se mantienen indefinidamente. Para limpiar respaldos antiguos:

1. Edita `app/chat/backup_routine.py`
2. Descomenta las líneas 250-257 en la función `main()`
3. O configura una tarea programada del sistema para limpiar carpetas antiguas

## 🔒 Seguridad

### Datos Sensibles

Los siguientes datos están en `config.py`:

- Credenciales de Google Drive
- Credenciales SMTP para emails
- Contraseñas de aplicación

**⚠️ IMPORTANTE**: No subas `config.py` a repositorios públicos. Usa variables de entorno o `.env` para producción.

### Recomendaciones

1. Usa variables de entorno para credenciales sensibles
2. Limita el acceso a la carpeta `temp_backups`
3. Configura permisos apropiados en Google Drive
4. Monitorea regularmente los espacios en disco

## 🎯 Próximas Mejoras

- [ ] Respaldos incrementales (solo cambios)
- [ ] Compresión automática de archivos antiguos
- [ ] Logs de respaldo persistentes
- [ ] Interfaz web para monitoreo
- [ ] Almacenamiento en múltiples ubicaciones (OneDrive, Dropbox, etc.)
- [ ] Restauración automática desde backup

## 📝 Notas Finales

- Los backups automáticos se ejecutan mientras la aplicación esté en ejecución
- Si la aplicación se reinicia, el scheduler se reinicializa automáticamente
- Los respaldos locales son una copia de seguridad inmediata en caso de fallos de Drive
- Se recomienda mantener la aplicación ejecutándose en un servidor con alta disponibilidad

---

**Creado**: Enero 2025  
**Mantenido por**: Equipo SIIP  
**Versión**: 1.0.0

