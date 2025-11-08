# SIIP - Sistema Integrado de Información Penitenciaria
## Documentación Técnica Completa

### Índice
1. [Descripción General](#descripción-general)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Tecnologías Utilizadas](#tecnologías-utilizadas)
4. [Estructura del Proyecto](#estructura-del-proyecto)
5. [Módulos del Sistema](#módulos-del-sistema)
6. [Base de Datos](#base-de-datos)
7. [Servicios de IA](#servicios-de-ia)
8. [API y Endpoints](#api-y-endpoints)
9. [Configuración](#configuración)
10. [Despliegue](#despliegue)

---

## Descripción General

El **Sistema Integrado de Información Penitenciaria (SIIP)** es una aplicación web desarrollada para el Ministerio del Poder Popular para el Servicio Penitenciario de Venezuela. El sistema integra múltiples módulos para la gestión completa de información penitenciaria, incluyendo:

- **Gestión de Privados de Libertad (PDL)**
- **Sistema de Chat Inteligente con IA**
- **Gestión de Recursos Humanos (RRHH)**
- **Módulo de Panadería**
- **Generación de Reportes**
- **Consulta Legal con RAG**

---

## Arquitectura del Sistema

### Patrón de Arquitectura
- **Backend**: Flask (Python) con arquitectura modular
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Base de Datos**: SQLite con SQLAlchemy ORM
- **IA**: Google Gemini 2.5 Pro + LangChain
- **Procesamiento**: Pandas para análisis de datos

### Diagrama de Arquitectura
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Base de       │
│   (Bootstrap)   │◄──►│   (Flask)       │◄──►│   Datos         │
│                 │    │                 │    │   (SQLite)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Servicios     │
                       │   de IA        │
                       │   (Gemini)      │
                       └─────────────────┘
```

---

## Tecnologías Utilizadas

### Backend
- **Python 3.x**: Lenguaje principal
- **Flask 2.x**: Framework web
- **SQLAlchemy**: ORM para base de datos
- **Flask-Login**: Gestión de sesiones
- **Flask-Migrate**: Migraciones de BD
- **APScheduler**: Tareas programadas
- **Pandas**: Análisis de datos
- **Werkzeug**: Utilidades de seguridad

### Frontend
- **HTML5**: Estructura
- **CSS3**: Estilos personalizados
- **JavaScript (ES6+)**: Interactividad
- **Bootstrap 5.1.3**: Framework CSS
- **Font Awesome 5.15.3**: Iconos
- **Chart.js**: Gráficos (inferido)

### Base de Datos
- **SQLite**: Base de datos principal
- **ChromaDB**: Base de datos vectorial para RAG

### Servicios de IA
- **Google Gemini 2.5 Pro**: Modelo de lenguaje
- **LangChain**: Framework para aplicaciones con IA
- **Google Generative AI**: API de Google
- **FuzzyWuzzy**: Búsqueda difusa de texto

### Integración Externa
- **Google Sheets API**: Sincronización de datos
- **Google OAuth2**: Autenticación
- **PyPDF2**: Procesamiento de PDFs

### Herramientas de Desarrollo
- **Flask-Migrate**: Migraciones
- **python-dotenv**: Variables de entorno
- **dateutil**: Procesamiento de fechas
- **pytz**: Zonas horarias

---

## Estructura del Proyecto

```
SIIP CON FOTO/
├── app/                          # Aplicación principal
│   ├── __init__.py              # Factory de la aplicación
│   ├── models.py                # Modelos de base de datos
│   ├── extensions.py            # Extensiones de Flask
│   ├── config.py                # Configuración
│   ├── auth.py                  # Autenticación
│   ├── utils.py                 # Utilidades
│   ├── reports.py               # Generación de reportes
│   ├── data_loader.py           # Carga de datos de Google Sheets
│   ├── legal_engine.py          # Motor legal
│   ├── legal_rag_service.py     # Servicio RAG legal
│   ├── pdl_management.py        # Gestión de PDL
│   ├── chat/                    # Módulo de chat
│   │   ├── __init__.py
│   │   ├── routes.py            # Rutas principales del chat
│   │   ├── message_logic.py     # Lógica de procesamiento
│   │   ├── report_processing.py # Procesamiento de reportes
│   │   ├── dashboard_routes.py  # Dashboard
│   │   ├── general_routes.py    # Rutas generales
│   │   ├── image_routes.py      # Gestión de imágenes
│   │   └── reseña_routes.py     # Reseña fotográfica
│   ├── panaderia/               # Módulo de panadería
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── forms.py
│   │   └── templates/
│   ├── rrhh/                    # Módulo RRHH
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── forms.py
│   │   └── templates/
│   ├── templates/               # Plantillas HTML
│   ├── static/                  # Archivos estáticos
│   ├── photos/                  # Fotos de PDL
│   └── resources/               # Recursos del sistema
├── migrations/                  # Migraciones de BD
├── reports/                     # Reportes generados
├── documentos_legales/          # Documentos para RAG
├── chroma_db/                   # Base de datos vectorial
├── config.py                    # Configuración principal
├── run.py                       # Punto de entrada
└── siip_database.db            # Base de datos SQLite
```

---

## Módulos del Sistema

### 1. Módulo de Chat Inteligente
**Propósito**: Interfaz conversacional con IA para consultas sobre PDL

**Características**:
- Chat interactivo con el asistente "Sucre"
- Búsqueda por cédula o nombre de PDL
- Generación automática de fichas jurídicas
- Procesamiento de lenguaje natural
- Historial de conversaciones persistente

**Tecnologías**:
- Google Gemini 2.5 Pro
- LangChain para RAG
- FuzzyWuzzy para búsqueda difusa
- Pandas para análisis de datos

### 2. Módulo de Gestión de PDL
**Propósito**: Administración de información de privados de libertad

**Características**:
- Registro y actualización de PDL
- Gestión de familiares
- Sincronización con Google Sheets
- Búsqueda avanzada
- Generación de reportes

### 3. Módulo de RRHH
**Propósito**: Gestión de recursos humanos del personal penitenciario

**Características**:
- Registro de funcionarios
- Gestión de estatus laboral
- Carga masiva desde Excel
- Gestión de documentos de reposo
- Fotos de perfil
- Reportes de personal

**Tecnologías**:
- Pandas para procesamiento de Excel
- Pillow para manejo de imágenes
- Werkzeug para seguridad de archivos

### 4. Módulo de Panadería
**Propósito**: Gestión de producción y ventas de la panadería penitenciaria

**Características**:
- Gestión de productos
- Control de vendedores
- Registro de producción diaria
- Sistema de ventas
- Control de movimientos financieros
- Reportes de producción y ventas

**Entidades**:
- ProductoPanaderia
- Vendedor
- ProduccionDiaria
- VentaDiaria
- MovimientoVendedor

### 5. Módulo de Reportes
**Propósito**: Generación de reportes en múltiples formatos

**Características**:
- Reportes PDF con gráficos
- Fichas jurídicas en JPG
- Reportes de estadísticas
- Exportación a CSV
- Dashboard interactivo

**Tecnologías**:
- ReportLab para PDFs
- Pillow para imágenes
- Pandas para análisis

### 6. Servicio RAG Legal
**Propósito**: Consultas sobre legislación penitenciaria

**Características**:
- Base de conocimientos legal
- Búsqueda semántica en documentos
- Respuestas contextualizadas
- Integración con ChromaDB

**Tecnologías**:
- LangChain
- ChromaDB
- Google Generative AI Embeddings

---

## Base de Datos

### Modelos Principales

#### User
```python
- id: Integer (PK)
- username: String(80)
- password_hash: String(256)
- is_admin: Boolean
- nombre_completo: String(120)
- cargo: String(80)
- conversations: Relationship
```

#### PDL (Privado de Libertad)
```python
- id: Integer (PK)
- cedula: String(25)
- nombre_completo: String(200)
- familiares: Relationship
```

#### Funcionario
```python
- id: Integer (PK)
- nombres: String(100)
- apellidos: String(100)
- cedula: String(25)
- tipo_personal: String(50)
- estatus_actual: String(50)
- # ... más campos de información personal y laboral
```

#### Conversation
```python
- id: Integer (PK)
- user_id: Integer (FK)
- history_data: JSON
- created_at: DateTime
- last_updated: DateTime
```

#### Modelos de Panadería
- **ProductoPanaderia**: Productos de la panadería
- **Vendedor**: Vendedores del sistema
- **ProduccionDiaria**: Registros de producción
- **VentaDiaria**: Registros de ventas
- **MovimientoVendedor**: Movimientos financieros

### Relaciones
- User → Conversation (1:N)
- PDL → Familiar (1:N)
- Funcionario → Reposo (1:N)
- ProductoPanaderia → ProduccionDiaria (1:N)
- Vendedor → VentaDiaria (1:N)

---

## Servicios de IA

### Google Gemini 2.5 Pro
**Uso**: Procesamiento de lenguaje natural para el chat

**Configuración**:
```python
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('models/gemini-2.5-pro')
```

**Características**:
- Comprensión de consultas en español
- Generación de respuestas contextuales
- Análisis de intenciones del usuario
- Procesamiento de consultas legales

### LangChain RAG
**Uso**: Sistema de recuperación aumentada para consultas legales

**Componentes**:
- **Document Loader**: PyPDFLoader para documentos legales
- **Text Splitter**: RecursiveCharacterTextSplitter
- **Vector Store**: ChromaDB
- **Embeddings**: GoogleGenerativeAIEmbeddings
- **LLM**: ChatGoogleGenerativeAI

**Flujo**:
1. Carga de documentos PDF
2. División en chunks
3. Generación de embeddings
4. Almacenamiento en ChromaDB
5. Búsqueda semántica
6. Generación de respuesta contextual

---

## API y Endpoints

### Autenticación
- `POST /login` - Inicio de sesión
- `GET /logout` - Cierre de sesión
- `GET /register` - Registro de usuarios

### Chat
- `POST /send_message` - Envío de mensajes
- `GET /chat` - Interfaz del chat
- `GET /get_history` - Historial de conversación

### PDL
- `GET /pdl` - Lista de PDL
- `POST /pdl` - Crear PDL
- `GET /pdl/<id>` - Ver PDL específico
- `PUT /pdl/<id>` - Actualizar PDL
- `DELETE /pdl/<id>` - Eliminar PDL

### RRHH
- `GET /rrhh/` - Dashboard RRHH
- `GET /rrhh/seguridad-custodia` - Personal de seguridad
- `GET /rrhh/administrativos` - Personal administrativo
- `POST /rrhh/registrar` - Registrar funcionario
- `GET /rrhh/funcionario/<id>` - Ver funcionario

### Panadería
- `GET /panaderia/` - Dashboard panadería
- `GET /panaderia/productos` - Gestión de productos
- `GET /panaderia/vendedores` - Gestión de vendedores
- `GET /panaderia/produccion` - Registro de producción
- `GET /panaderia/ventas` - Registro de ventas

### Reportes
- `GET /reports/<filename>` - Descarga de reportes
- `GET /dashboard` - Dashboard de estadísticas

---

## Configuración

### Variables de Entorno
```bash
SECRET_KEY=tu_clave_secreta_aqui
DATABASE_URL=sqlite:///siip_database.db
GOOGLE_API_KEY=tu_api_key_de_google
SERVICE_ACCOUNT_FILE=credentials.json
SPREADSHEET_ID=id_del_google_sheet
SHEET_RANGE=rango_del_sheet
```

### Configuración de la Aplicación
```python
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    # ... más configuraciones
```

### Carpetas del Sistema
- `REPORTS_FOLDER`: Reportes generados
- `RESOURCES_FOLDER`: Recursos estáticos
- `PHOTOS_FOLDER`: Fotos de PDL
- `FUNCIONARIOS_FOTOS_FOLDER`: Fotos de funcionarios
- `REPOSOS_FOLDER`: Documentos de reposo
- `LEGAL_DOCS_FOLDER`: Documentos legales

---

## Despliegue

### Requisitos del Sistema
- Python 3.8+
- SQLite 3
- Navegador web moderno

### Dependencias Python
```txt
Flask==2.3.3
SQLAlchemy==2.0.21
Flask-Login==0.6.3
Flask-Migrate==4.0.5
pandas==2.0.3
google-generativeai==0.3.2
langchain==0.0.350
langchain-google-genai==0.0.6
chromadb==0.4.15
fuzzywuzzy==0.18.0
APScheduler==3.10.4
python-dotenv==1.0.0
Werkzeug==2.3.7
```

### Instalación
1. Clonar el repositorio
2. Crear entorno virtual: `python -m venv venv`
3. Activar entorno: `venv\Scripts\activate` (Windows)
4. Instalar dependencias: `pip install -r requirements.txt`
5. Configurar variables de entorno
6. Ejecutar migraciones: `flask db upgrade`
7. Iniciar aplicación: `python run.py`

### Configuración de Producción
- Cambiar `debug=False` en `run.py`
- Configurar servidor web (Nginx + Gunicorn)
- Configurar HTTPS
- Configurar backup de base de datos
- Configurar monitoreo de logs

---

## Características Técnicas Destacadas

### Seguridad
- Autenticación con Flask-Login
- Hash de contraseñas con Werkzeug
- Validación de archivos subidos
- Protección contra inyección SQL (SQLAlchemy ORM)

### Rendimiento
- Caché de datos con APScheduler
- Sincronización automática con Google Sheets
- Optimización de consultas SQL
- Compresión de imágenes

### Escalabilidad
- Arquitectura modular con Blueprints
- Separación de responsabilidades
- Base de datos normalizada
- API RESTful

### Mantenibilidad
- Código bien documentado
- Patrones de diseño consistentes
- Separación de lógica de negocio
- Sistema de logging integrado

---

## Conclusión

El SIIP es un sistema integral que combina tecnologías modernas de IA, gestión de datos y desarrollo web para crear una solución completa para la administración penitenciaria. Su arquitectura modular permite fácil mantenimiento y extensión, mientras que la integración de IA proporciona una experiencia de usuario avanzada para consultas y análisis de datos.

El sistema está diseñado para ser robusto, seguro y escalable, cumpliendo con los requisitos específicos del sector penitenciario venezolano mientras mantiene estándares técnicos modernos.

