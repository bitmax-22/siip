# Sistema de Control de Pedidos de Panadería

## Descripción General

Sistema de pedidos online para la panadería que permite:
- Crear pedidos desde tablet Android
- Imprimir comandas automáticamente en impresora térmica WiFi de 80mm
- Gestionar estado de pedidos
- Realizar seguimiento de pedidos en tiempo real

## Arquitectura del Sistema

### Opción 1: Impresora WiFi + VPN (RECOMENDADA)
```
[SIIP en VPS Cloud] 
         ↓ (VPN/Tailscale)
    [Red WiFi Local]
         ↓
[Tablet Android en Panadería] ←→ [Impresora Térmica WiFi 80mm @ 192.168.88.128:9100]
```

### Opción 2: Impresora Bluetooth
```
[SIIP Principal en PC Servidor]
         ↓
    [Red WiFi Local]
         ↓
[Tablet Android en Panadería] ←→ [Impresora Térmica Bluetooth 80mm]
```

### Opción 3: Fallback PDF (Actual)
```
[SIIP en VPS] → [Falla TCP] → [Genera PDF] → [Descarga en Tablet] → [Impresión Manual]
```

**Flujo de Trabajo**:
1. Usuario en tablet Android abre interfaz web de SIIP
2. Selecciona productos del catálogo de panadería
3. Confirma pedido
4. Sistema imprime automáticamente comanda en impresora térmica
5. Pedido queda registrado en base de datos

## Requisitos de Hardware

### 1. Tablet Android
**Especificaciones recomendadas**:
- Sistema: Android 8.0 (Oreo) o superior
- Pantalla: 10 pulgadas o superior
- RAM: 3GB mínimo
- Conectividad: WiFi
- Batería: Duración de 6+ horas

**Tablets recomendadas**:
- Samsung Galaxy Tab A8 (10.5") - $200-250 USD
- Lenovo Tab M10 Plus (Gen 3) - $180-220 USD
- Amazon Fire HD 10 (con GApps) - $150 USD

### 2. Impresora Térmica

#### Opción A: Impresora WiFi
**Características mínimas**:
- WiFi integrado (802.11n o superior)
- Ancho de papel: 80mm
- Resolución: 203 DPI
- Velocidad: Mínimo 10 líneas/segundo
- Compatible con ESC/POS
- Puerto de red: TCP/IP puerto 9100 (RAW)
- Bufer de impresión

**Modelos recomendados**:
- **Epson TM-T20II WiFi** - $350-400 USD (Excelente calidad)
- **Star TSP143III** - $250-300 USD (Económica)
- **Bixolon SRP-350III** - $280-320 USD (Buena relación precio-calidad)
- **Zebra ZD220** - $400-450 USD (Profesional, robusta)

**Ventajas**:
- No requiere configuración de Bluetooth
- Puede usarse desde múltiples dispositivos
- Más estable para impresión remota

#### Opción B: Impresora Bluetooth (Más económica)
**Características mínimas**:
- Bluetooth 4.0 o superior
- Ancho de papel: 80mm
- Resolución: 203 DPI
- Velocidad: Mínimo 10 líneas/segundo
- Compatible con ESC/POS
- Batería recargable opcional

**Modelos recomendados**:
- **Bixolon SRP-332B** - $150-180 USD (Bluetooth + WiFi)
- **Xprinter XP-58C** - $60-80 USD (Económica, solo BT)
- **Star Micronics TSP100LAN** - $180-220 USD (BT + WiFi)
- **Epson TM-T82II** - $200-250 USD (Con BT integrado)

**Ventajas**:
- Más económica
- No requiere red WiFi
- Emparejamiento simple
- Ideal para uso en tablet dedicada

**Desventajas**:
- Solo puede usarse desde un dispositivo a la vez
- Requiere app adicional para controlar Bluetooth desde web
- Rango limitado (10m aprox)

**Recomendación**: Para una tablet dedicada en la panadería, usar impresora Bluetooth es la opción más económica y sencilla.

### 3. Red WiFi
- Router WiFi con estándar 802.11n o superior
- Alcance: cubrir área de panadería y ubicación de impresora
- Configuración: Red interna de trabajo
- Ancho de banda: 2.4GHz o 5GHz

### 4. Servidor (PC Principal donde corre SIIP)
- Conexión a la misma red WiFi
- SIIP ya instalado y configurado
- Acceso a base de datos

## Configuración Rápida

### **⚠️ IMPORTANTE: Impresión Remota (VPS → Impresora Local)**

Si SIIP corre en un VPS fuera de tu red local, necesitas una VPN para que el VPS acceda a la impresora.

> 📖 **Ver guía completa:** `GUIA_VPN_STARLINK_MIKROTIK.md`

#### **🔍 Paso 1: Verificar si Tienes IP Pública (Starlink CGNAT)**

En MikroTik, ejecuta en Terminal:
```bash
/ip address print
```

Verifica la IP pública obtenida vía DHCP:
```bash
/ip dhcp-client print
```

**Luego abre una terminal/powershell y verifica:**
```bash
# Ver tu IP pública real
curl ifconfig.me

# Comparar con la IP que el MikroTik dice tener
```

**Si las IPs NO coinciden** → Estás en **CGNAT**, usa **Opción A (Tailscale)**  
**Si las IPs SÍ coinciden** → Tienes IP pública, puedes usar **Opción B (VPN nativa)**

---

#### **Opción A: Tailscale (RECOMENDADA - Funciona con Starlink CGNAT)**
1. Crear cuenta en [tailscale.com](https://tailscale.com)
2. En VPS (Linux):
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   # Seguir instrucciones para autenticar
   ```
3. En Tablet o PC de la Panadería:
   - Descargar Tailscale: https://tailscale.com/download
   - Iniciar sesión con la misma cuenta
   - Anotar la IP de Tailscale asignada (ej: `100.x.x.x`)
4. **Actualizar `config.py`**:
   ```python
   IMPRESORA_IP = os.environ.get('IMPRESORA_IP', '100.x.x.x')  # IP de Tailscale
   ```
5. **Ventajas**: Funciona detrás de NAT/CGNAT, gratis 100 dispositivos, sin configuración de router

#### **Opción B: VPN MikroTik L2TP/IPsec (Solo si tienes IP pública)**
> ⚠️ **IMPORTANTE**: Con Starlink CGNAT, esta opción **NO funcionará**.

**Si tu MikroTik tiene IP pública** (no detrás de Starlink CGNAT):

1. **En MikroTik (Winbox o WebFig)**:
   ```bash
   # 1. Habilitar L2TP Server
   /ppp profile add name=vpn-impresora local-address=192.168.88.1 remote-address=192.168.88.10-192.168.88.20
   
   # 2. Habilitar servidor L2TP
   /interface l2tp-server server set enabled=yes default-profile=vpn-impresora use-ipsec=yes ipsec-secret=TuClaveSecretaSegura2024
   
   # 3. Crear usuario VPN
   /ppp secret add name=vps-siip password=TuPasswordSeguro2024 service=l2tp profile=vpn-impresora
   
   # 4. Configurar firewall para L2TP/IPsec
   /ip firewall filter add chain=input protocol=udp dst-port=1701 action=accept
   /ip firewall filter add chain=input protocol=udp dst-port=500 action=accept
   /ip firewall filter add chain=input protocol=udp dst-port=4500 action=accept
   /ip firewall filter add chain=input protocol=ipsec-esp action=accept
   ```

2. **En VPS (Linux)**:
   ```bash
   # Instalar cliente
   sudo apt-get install strongswan xl2tpd
   
   # Configurar (archivos en /etc)
   # Editar /etc/ipsec.conf y /etc/xl2tpd/xl2tpd.conf
   # IP pública del MikroTik, usuario, password y secret
   ```

**Si usas Starlink CGNAT** (no tienes IP pública):
- **Usa Tailscale** (Opción A) - Funciona detrás de cualquier NAT

**⚠️ Sin VPN**: El sistema actual usará **fallback PDF** (descarga manual)

### **Cómo Cambiar la IP de la Impresora**

#### Método 1: Editar `config.py` (Recomendado)
1. Abrir archivo `config.py` en la raíz del proyecto
2. Buscar línea 54: `IMPRESORA_IP = os.environ.get('IMPRESORA_IP', '192.168.88.128')`
3. Cambiar `'192.168.88.128'` por la IP de tu impresora
4. Guardar archivo
5. Reiniciar SIIP

#### Método 2: Crear archivo `.env`
1. Crear archivo `.env` en la raíz del proyecto
2. Agregar:
   ```
   IMPRESORA_HABILITADA=True
   IMPRESORA_IP=192.168.88.128
   IMPRESORA_PUERTO=9100
   IMPRESORA_ANCHO_MM=80
   ```
3. Reiniciar SIIP

### 1. Configurar Impresora Térmica

#### Paso 1: Conectar a WiFi
1. Encender la impresora térmica
2. Acceder al menú de configuración
3. Ir a "Red" → "WiFi Settings"
4. Seleccionar la red WiFi del establecimiento
5. Ingresar contraseña
6. Confirmar que se asigna una IP (ej: 192.168.1.100)

#### Paso 2: Configurar Puerto de Impresión
1. En el menú de la impresora, ir a "Puerto" o "Network Settings"
2. Configurar puerto TCP/IP: **9100** (RAW)
3. Guardar configuración

#### Paso 3: Obtener IP de la Impresora
1. Imprimir hoja de configuración desde el menú
2. Anotar la IP asignada (ej: `192.168.1.100`)
3. Verificar conectividad: desde PC abrir `http://[IP_IMPRESORA]`

### 2. Configurar SIIP

#### Paso 1: Configurar IP de Impresora

**Editar archivo `config.py` (líneas 52-56):**

```52:56:config.py
    # Configuración de Impresión Térmica para Pedidos
    IMPRESORA_HABILITADA = os.environ.get('IMPRESORA_HABILITADA', 'False').lower() == 'true'
    IMPRESORA_IP = os.environ.get('IMPRESORA_IP', '192.168.1.100')  # ⬅️ CAMBIAR AQUÍ
    IMPRESORA_PUERTO = int(os.environ.get('IMPRESORA_PUERTO', '9100'))
    IMPRESORA_ANCHO_MM = int(os.environ.get('IMPRESORA_ANCHO_MM', '80'))
```

**O crear archivo `.env` en la raíz del proyecto:**
```env
# Impresión Térmica WiFi
IMPRESORA_HABILITADA=True
IMPRESORA_IP=192.168.1.105  # Cambia esta IP por la de tu impresora
IMPRESORA_PUERTO=9100
IMPRESORA_ANCHO_MM=80
```

**Cómo obtener la IP de la impresora:**
1. Imprimir hoja de configuración desde el menú de la impresora
2. Anotar la IP asignada (ej: `192.168.1.105`)
3. O desde Windows: abrir menú impresora → `Network Settings` → ver IP

**Para deshabilitar la impresión temporalmente:**
```python
IMPRESORA_HABILITADA = False  # Cambiar a False
```

**⚠️ IMPORTANTE sobre Bluetooth:**
- La impresión Bluetooth **NO está implementada** actualmente
- Requiere Web Bluetooth API (disponible en Chrome Android pero complejo)
- **Alternativa recomendada**: Usar impresora WiFi para simplicidad y estabilidad
- Si necesitas Bluetooth, considera desarrollar una app Android nativa con React Native

#### Paso 2: Verificar Configuración
```bash
# Desde el servidor SIIP, verificar conectividad
ping 192.168.1.100

# O usando telnet
telnet 192.168.1.100 9100
```

#### Paso 3: Restart SIIP
```bash
# Reiniciar aplicación
# En Windows: cerrar y abrir run.py
# En Linux: sudo systemctl restart siip
```

### 3. Configurar Tablet Android

#### Paso 1: Instalar Navegador
- Instalar **Chrome** o **Firefox** desde Google Play
- Recomendado: Chrome (mejor rendimiento)

#### Paso 2: Acceder a SIIP
1. Conectar tablet a la misma red WiFi
2. Abrir navegador Chrome
3. Ir a `http://[IP_SERVIDOR]:5000/panaderia/pedidos`
4. Hacer login

#### Paso 3: Agregar a Pantalla de Inicio (PWA)
1. En Chrome, menú (⋮) → "Instalar app"
2. Aceptar instalación
3. Ahora SIIP se abre como app nativa

### 4. Verificar Impresión

#### Test Manual
1. Abrir SIIP en tablet
2. Ir a Módulo de Pedidos
3. Crear un pedido de prueba
4. Verificar que la comanda se imprima

#### Troubleshooting

**Problema**: La comanda no se imprime
- Verificar que `IMPRESORA_HABILITADA=true` en config
- Verificar IP de impresora
- Verificar que impresora esté encendida
- Verificar conectividad WiFi: `ping [IP_IMPRESORA]`

**Problema**: La impresora imprime caracteres extraños
- Verificar que use puerto 9100 (RAW)
- Verificar compatibilidad ESC/POS
- Revisar logs: `app.log`

**Problema**: La tablet no puede acceder a SIIP
- Verificar que tablet esté en misma red WiFi
- Verificar firewall del servidor
- Verificar que SIIP esté corriendo

## ¿Puedo usar una Impresora Bluetooth?

**Respuesta**: Sí, pero requiere desarrollo adicional.

### Estado Actual
- ✅ **WiFi**: Completamente implementado y funcional
- ❌ **Bluetooth**: NO implementado actualmente

### Opciones para Bluetooth

#### Opción 1: Usar WiFi (Recomendado)
- **Ventaja**: Ya implementado, funciona sin cambios
- **Desventaja**: Impresoras WiFi son más caras ($250-400 USD)

#### Opción 2: Impresora con Bluetooth + App Android Nativa
**Requisitos**:
1. Desarrollar app Android nativa con React Native o Cordova
2. App intercepta impresión desde la web
3. App se comunica con impresora Bluetooth vía Serial Port Profile (SPP)

**Esfuerzo**: 2-3 semanas de desarrollo

#### Opción 3: Impresora Dual (WiFi + Bluetooth)
**Modelos**:
- Bixolon SRP-332B ($150-180 USD): WiFi + Bluetooth
- Star Micronics TSP100LAN ($180-220 USD): BT + WiFi
- Epson TM-T82II ($200-250 USD): Con BT integrado

**Ventaja**: Usar WiFi ahora, Bluetooth después si se necesita

### Recomendación

**Para uso inmediato**: Comprar impresora **WiFi** (ya implementado)
**Si tienes impresora Bluetooth**: Considerar desarrollo de app Android nativa

**Solución temporal**: Usar app de terceros como "PrintHand" o "Star CloudPRNT" para imprimir desde la tablet por Bluetooth

## Estructura del Código

### Archivos Principales

```
app/
├── models.py                          # Modelos: PedidoPanaderia, ItemPedidoPanaderia
├── thermal_printer.py                 # Lógica de impresión ESC/POS
└── panaderia/
    ├── routes.py                      # APIs REST para pedidos
    └── templates/
        └── panaderia/
            └── pedidos.html           # Interfaz optimizada para tablet

config.py                              # Configuración de impresora
SISTEMA_PEDIDOS_PANADERIA.md           # Esta documentación
```

### APIs Disponibles

#### GET `/panaderia/api/productos_disponibles`
Obtiene lista de productos para crear pedidos.

**Respuesta**:
```json
{
  "success": true,
  "productos": [
    {
      "id": 1,
      "nombre": "Pan de Trigo",
      "precio_regular": 5.50,
      "precio_minimo": 5.00
    }
  ]
}
```

#### POST `/panaderia/api/crear_pedido`
Crea un nuevo pedido y lo imprime.

**Request**:
```json
{
  "cliente_nombre": "Juan Pérez",
  "cliente_telefono": "0424-1234567",
  "observaciones": "Sin azúcar",
  "items": [
    {
      "producto_id": 1,
      "cantidad": 2,
      "precio_unitario": 5.50
    }
  ]
}
```

**Respuesta**:
```json
{
  "success": true,
  "pedido_id": 45,
  "numero_pedido": "PED-001-20250128",
  "total": 11.00,
  "message": "Pedido PED-001-20250128 creado exitosamente",
  "impresion": {
    "success": true,
    "message": "Comanda imprimida exitosamente"
  }
}
```

#### GET `/panaderia/api/listar_pedidos`
Lista pedidos con filtros opcionales.

**Query Params**:
- `estado`: PENDIENTE, CONFIRMADO, EN_PREPARACION, LISTO, ENTREGADO, CANCELADO
- `limit`: Número máximo de resultados (default: 50)

#### POST `/panaderia/api/reimprimir_comanda/<pedido_id>`
Reimprime una comanda existente.

### Comanda Impresa

La comanda se imprime en formato ESC/POS con el siguiente diseño:

```
    ╔════════════════════════════════════╗
    ║     PANADERIA SIIP                 ║
    ║   ════════════════════════════     ║
    ║                                    ║
    ║  PEDIDO: PED-001-20250128          ║
    ║  Fecha: 28/01/2025 14:30           ║
    ║  ────────────────────────────────   ║
    ║                                    ║
    ║  CLIENTE:                           ║
    ║  Juan Pérez                         ║
    ║  Tel: 0424-1234567                  ║
    ║  ────────────────────────────────   ║
    ║                                    ║
    ║  DETALLE:                           ║
    ║  ────────────────────────────────   ║
    ║                                    ║
    ║  1. Pan de Trigo                    ║
    ║     Qty: 2 x 5.50 Bs.               ║
    ║                        11.00 Bs.    ║
    ║                                    ║
    ║  ────────────────────────────────   ║
    ║                         TOTAL:      ║
    ║                        11.00 Bs.    ║
    ║                                    ║
    ║     Gracias por su compra!          ║
    ╚════════════════════════════════════╝
```

## Comparación WiFi vs Bluetooth

| Característica | WiFi | Bluetooth |
|----------------|------|-----------|
| **Costo** | $250-400 USD | $60-180 USD |
| **Instalación** | Requiere red WiFi | Emparejamiento simple |
| **Compatibilidad** | Múltiples dispositivos | Un dispositivo a la vez |
| **Rango** | 50m+ (depende del router) | 10m aprox |
| **Velocidad** | Alta | Media |
| **Estabilidad** | Excelente | Muy buena |
| **Desarrollo** | ✅ Implementado | ⚠️ Requiere Web Bluetooth API |
| **Configuración** | IP estática necesaria | Emparejamiento MAC |

**Recomendación**: Para uso con tablet dedicada, **Bluetooth es más económica y simple**, pero requiere desarrollo adicional.

## Costos Estimados

### Opción WiFi
| Componente | Modelo | Precio |
|------------|--------|--------|
| Tablet Android | Lenovo Tab M10 Plus | $200 USD |
| Impresora Térmica WiFi | Star TSP143III | $280 USD |
| Papel térmico 80mm (100 rollos) | Genérico | $50 USD |
| **Total** | | **$530 USD** |

### Opción Bluetooth (Recomendada para tablet dedicada)
| Componente | Modelo | Precio |
|------------|--------|--------|
| Tablet Android | Lenovo Tab M10 Plus | $200 USD |
| Impresora Térmica BT | Bixolon SRP-332B | $150 USD |
| Papel térmico 80mm (100 rollos) | Genérico | $50 USD |
| **Total** | | **$400 USD** |

**Ahorro con Bluetooth**: $130 USD

## Ventajas de Esta Arquitectura

### Comparado con soluciones tradicionales:

1. **Sin dependencia de PC**: Solo tablet Android
2. **Impresión directa**: Sin intermediarios
3. **Interfaz táctil**: Optimizada para tablets
4. **Escalable**: Fácil agregar más impresoras
5. **Económico**: Total hardware ~$530 USD
6. **Rápido**: Impresión instantánea
7. **Robusto**: Menos puntos de falla

## Mantenimiento

### Diario
- Verificar papel en impresora
- Limpiar cabezal térmico
- Revisar conectividad WiFi

### Semanal
- Verificar logs de errores
- Revisar pedidos pendientes
- Limpiar tablet

### Mensual
- Actualizar SIIP si hay nuevas versiones
- Respaldar base de datos
- Verificar rendimiento de red

## Soporte

Para problemas o dudas:
1. Revisar logs: `app/logs/app.log`
2. Verificar configuración en `config.py`
3. Consultar documentación técnica
4. Contactar al equipo de soporte

## Futuras Mejoras

- [ ] App Android nativa (React Native)
- [ ] Sincronización offline
- [ ] Notificaciones push
- [ ] Dashboard de ventas en tiempo real
- [ ] Integración con sistema de inventario
- [ ] Reportes automáticos
