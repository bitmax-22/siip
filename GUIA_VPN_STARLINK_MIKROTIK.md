# Guía Completa: Configurar VPN para Impresión Remota con MikroTik + Starlink

## 🎯 Objetivo
Permitir que tu VPS acceda a la impresora local `192.168.88.128:9100` a través de una VPN.

---

## 📋 Índice

1. [Verificar si tienes IP Pública o CGNAT](#1-verificar-si-tienes-ip-pública-o-cgnat)
2. [Solución A: Tailscale (Recomendada para Starlink)](#solución-a-tailscale-recomendada)
3. [Solución B: VPN MikroTik Nativa (Solo con IP pública)](#solución-b-vpn-mikrotik-l2tpipsec)
4. [Configurar SIIP para usar la VPN](#configurar-siip-para-usar-la-vpn)
5. [Pruebas y Solución de Problemas](#pruebas-y-solución-de-problemas)

---

## 1. Verificar si Tienes IP Pública o CGNAT

Starlink suele usar **CGNAT** (Carrier-Grade NAT), lo que significa que tu MikroTik **NO tiene una IP pública real** y las conexiones entrantes no funcionarán.

### Paso 1.1: Verificar IP en MikroTik

Conecta a tu MikroTik vía **Winbox** o **Terminal SSH**.

**En Terminal del MikroTik:**
```bash
/ip address print
```

Anota la IP de la interfaz WAN (generalmente `ether1` o `WAN`).

**Luego verifica la IP asignada vía DHCP:**
```bash
/ip dhcp-client print
```

### Paso 1.2: Comparar con IP Pública Real

**En Windows PowerShell o CMD:**
```powershell
curl ifconfig.me
```

**Comparar:**
- **Si la IP del MikroTik NO coincide** con `ifconfig.me` → **Estás en CGNAT**
- **Si la IP del MikroTik SÍ coincide** con `ifconfig.me` → **Tienes IP pública**

### Resultado

| Situación | IP MikroTik | IP ifconfig.me | Solución |
|-----------|-------------|----------------|----------|
| **CGNAT** | 100.65.x.x | 23.45.x.x | Tailscale ✅ |
| **IP Pública** | 23.45.x.x | 23.45.x.x | VPN MikroTik o Tailscale |

---

## Solución A: Tailscale (Recomendada)

Tailscale funciona perfectamente detrás de CGNAT/NAT sin configuración de router.

### Paso A.1: Instalar Tailscale en VPS

**Si tu VPS es Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

**Te pedirá autenticarte:**
1. Abre el enlace que te da en el navegador
2. Inicia sesión con Google/Microsoft
3. Acepta las autorizaciones
4. Vuelve a la terminal del VPS

**Verifica la conexión:**
```bash
tailscale status
# Verás algo como: 100.x.x.x nombre-del-vps
```

### Paso A.2: Instalar Tailscale en Tablet/PC Local

**En Android (Tablet):**
1. Descargar desde Play Store: [Tailscale](https://play.google.com/store/apps/details?id=com.tailscale.ipn)
2. Abrir la app
3. Iniciar sesión con la misma cuenta que usaste en el VPS
4. Activar "Connect"

**En Windows (PC de la panadería):**
1. Descargar: https://tailscale.com/download/windows
2. Instalar y ejecutar
3. Iniciar sesión con la misma cuenta
4. Click en "Connect"

### Paso A.3: Configurar Subnet Router (Opcional pero Recomendado)

Para que la impresora sea accesible vía Tailscale automáticamente:

**En MikroTik:**
```bash
# Descargar package de Tailscale (desde Winbox → System → Packages)
# O usar wget desde Terminal:
/tool fetch url="https://pkgs.tailscale.com/stable/mikrotik/tailscale-latest-arm64.ipk" dst="tailscale.ipk"

# Instalar:
/system package install file-name=tailscale.ipk

# Configurar:
/interface/tailscale add name="tailscale1" mtu=1420

# Crear secreto en https://login.tailscale.com/admin/settings/keys
# Pegar el secret:
/interface/tailscale set tailscale1 auth-key=tskey-auth-xxxxxxxxxxxxxxxxx advertise-routes=192.168.88.0/24

# Habilitar:
/interface/tailscale set tailscale1 disabled=no

# Verificar estado:
/interface/tailscale print
```

**Ahora el VPS podrá acceder a TODA la red 192.168.88.x directamente.**

### Paso A.4: Obtener IP de Tailscale

**Desde el VPS:**
```bash
tailscale ip
# Dará la IP del VPS vía Tailscale (ej: 100.101.102.103)

# Si configuraste subnet router:
tailscale status
# Verás las rutas anunciadas
```

**O desde la web:** https://login.tailscale.com/admin/machines

---

## Solución B: VPN MikroTik L2TP/IPsec

**⚠️ SOLO FUNCIONA si tienes IP pública. NO funciona con Starlink CGNAT.**

### Paso B.1: Configurar Servidor VPN en MikroTik

**Abre Winbox y sigue estos pasos:**

#### 1. Crear Perfil de Usuario

**PPP → Profiles → Click +**
- **Name:** `vpn-siip`
- **Local Address:** `192.168.88.1` (IP del router)
- **Remote Address:** `192.168.88.200` (IP que recibirá el VPS)
- **DNS:** `8.8.8.8` (opcional)
- **Click Apply → OK**

#### 2. Habilitar Servidor L2TP/IPsec

**PPP → Interfaces → L2TP Server → Check "Enabled"**
- **Default Profile:** `vpn-siip`
- **Check "Use IPsec"**
- **IPsec Secret:** `TuClaveSecretaSuperSegura2024!` (crea una clave fuerte)
- **Click Apply → OK**

#### 3. Crear Usuario VPN

**PPP → Secrets → Click +**
- **Name:** `vps-siip`
- **Password:** `TuPasswordSeguro123!` (crea una contraseña segura)
- **Service:** `l2tp`
- **Profile:** `vpn-siip`
- **Click OK**

#### 4. Configurar Firewall

**IP → Firewall → Filter Rules → Click +**

**Agregar estas 4 reglas:**

**Regla 1: Permitir L2TP**
- **Chain:** `input`
- **Protocol:** `udp`
- **Dst. Port:** `1701`
- **Action:** `accept`

**Regla 2: Permitir IPsec IKE**
- **Chain:** `input`
- **Protocol:** `udp`
- **Dst. Port:** `500`
- **Action:** `accept`

**Regla 3: Permitir IPsec NAT-Traversal**
- **Chain:** `input`
- **Protocol:** `udp`
- **Dst. Port:** `4500`
- **Action:** `accept`

**Regla 4: Permitir ESP (IPsec)**
- **Chain:** `input`
- **Protocol:** `ipsec-esp`
- **Action:** `accept`

**NOTA IMPORTANTE:** Las reglas de firewall deben ir **ANTES de la regla "drop"** general. Arrastra las nuevas reglas hasta arriba.

#### 5. Verificar IP Pública del MikroTik

**IP → DHCP Client → Ver la IP asignada**

Anota esta IP (ej: `23.45.67.89`). Esta será la IP a la que se conectará el VPS.

---

### Paso B.2: Configurar Cliente VPN en VPS

**En tu VPS (Linux):**

#### 1. Instalar Cliente VPN

```bash
sudo apt-get update
sudo apt-get install -y strongswan xl2tpd ppp lsof
```

#### 2. Configurar IPsec

**Editar `/etc/ipsec.conf`:**
```bash
sudo nano /etc/ipsec.conf
```

**Agregar al final del archivo:**
```
conn mikrotik-vpn
    type=transport
    keyexchange=ikev1
    left=%defaultroute
    leftprotoport=udp/l2tp
    right=23.45.67.89    # ⬅️ CAMBIAR por la IP pública de tu MikroTik
    rightprotoport=udp/l2tp
    ike=aes128-sha1-modp1024
    esp=aes128-sha1
    auto=start
    authby=secret
```

**Guardar:** Ctrl+O, Enter, Ctrl+X

#### 3. Configurar Secreto IPsec

**Editar `/etc/ipsec.secrets`:**
```bash
sudo nano /etc/ipsec.secrets
```

**Agregar:**
```
23.45.67.89 %any : PSK "TuClaveSecretaSuperSegura2024!"
```

**Guardar y asegurar archivo:**
```bash
sudo chmod 600 /etc/ipsec.secrets
```

#### 4. Configurar L2TP

**Editar `/etc/xl2tpd/xl2tpd.conf`:**
```bash
sudo nano /etc/xl2tpd/xl2tpd.conf
```

**Agregar:**
```
[lac mikrotik-vpn]
lns = 23.45.67.89
ppp debug = no
pppoptfile = /etc/ppp/options.l2tpd.client
length bit = yes
```

**Guardar**

#### 5. Configurar PPP

**Crear `/etc/ppp/options.l2tpd.client`:**
```bash
sudo nano /etc/ppp/options.l2tpd.client
```

**Agregar:**
```
ipcp-accept-local
ipcp-accept-remote
refuse-eap
require-chap
noccp
noauth
mtu 1280
mru 1280
noipdefault
defaultroute
usepeerdns
connect-delay 5000
name vps-siip
password TuPasswordSeguro123!
```

**Guardar y asegurar:**
```bash
sudo chmod 600 /etc/ppp/options.l2tpd.client
```

#### 6. Iniciar Servicios

```bash
sudo systemctl restart strongswan
sudo systemctl start xl2tpd

# Verificar estado
sudo systemctl status strongswan
sudo systemctl status xl2tpd

# Ver logs en tiempo real
sudo journalctl -f -u strongswan -u xl2tpd
```

#### 7. Conectar VPN

```bash
# Conectar
echo "c mikrotik-vpn" | sudo tee /var/run/xl2tpd/l2tp-control

# Esperar 5-10 segundos y verificar
ip addr show ppp0

# Deberías ver la IP 192.168.88.200
```

#### 8. Probar Conectividad

```bash
# Ping a la impresora
ping -c 5 192.168.88.128

# Si funciona, la VPN está lista
```

#### 9. Hacer la VPN Persistente (Auto-connect)

**Editar `/etc/systemd/system/xl2tpd-autostart.service`:**
```bash
sudo nano /etc/systemd/system/xl2tpd-autostart.service
```

**Agregar:**
```ini
[Unit]
Description=XL2TPD Auto-start
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'sleep 5 && echo "c mikrotik-vpn" > /var/run/xl2tpd/l2tp-control'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

**Activar:**
```bash
sudo systemctl enable xl2tpd-autostart.service
sudo systemctl enable strongswan
sudo systemctl enable xl2tpd
```

---

## Configurar SIIP para Usar la VPN

Una vez que la VPN está funcionando, debes actualizar la configuración de SIIP.

### Si usas Tailscale:

**Editar `config.py` línea 54:**
```python
IMPRESORA_IP = os.environ.get('IMPRESORA_IP', '100.101.102.103')  # IP de Tailscale
```

### Si usas VPN MikroTik:

**La IP ya es correcta:**
```python
IMPRESORA_IP = os.environ.get('IMPRESORA_IP', '192.168.88.128')
```

### Verificar Configuración

**Reiniciar SIIP:**
```bash
# Desde la carpeta del proyecto
python run.py
```

**Desde el VPS, probar conectividad:**
```bash
# Si usas Tailscale
ping 100.101.102.103

# Si usas VPN MikroTik
ping 192.168.88.128

# Probar puerto de impresora
telnet 192.168.88.128 9100
```

Si todo funciona, deberías poder hacer un pedido desde SIIP y la impresora se conectará automáticamente.

---

## Pruebas y Solución de Problemas

### Prueba 1: Verificar VPN Activa

**Tailscale:**
```bash
tailscale status
tailscale ping 192.168.88.128
```

**VPN MikroTik:**
```bash
ip addr show ppp0
ping 192.168.88.1
```

### Prueba 2: Conectividad de Puerto

```bash
# Desde el VPS
telnet 192.168.88.128 9100

# Si conecta, presiona Ctrl+] para salir
```

### Prueba 3: Crear Pedido de Prueba

1. Abrir SIIP en el navegador
2. Ir a "Panadería" → "Control de Pedidos"
3. Crear un pedido de prueba
4. Si imprime → **¡Funciona!** ✅
5. Si falla → Ver logs en `app/thermal_printer.py`

---

## Problemas Comunes

### ❌ VPN se desconecta después de X minutos

**Solución MikroTik:**
```bash
# En MikroTik, aumentar tiempo de keep-alive
/ppp profile set vpn-siip keepalive-timeout=60
```

**Solución Tailscale:**
```bash
# Tailscale es más estable, raramente se desconecta
tailscale set --advertise-exit-node
```

### ❌ Firewall bloquea conexión VPN

**Solución:**
```bash
# Ver reglas de firewall en MikroTik
/ip firewall filter print

# Verificar que las reglas de L2TP/IPsec estén ANTES de "drop"
# Arrastrarlas en Winbox para reordenar
```

### ❌ Error "No route to host"

**Solución:**
```bash
# Verificar rutas en VPS
ip route show

# Si falta ruta, agregar manualmente (VPN MikroTik):
sudo ip route add 192.168.88.0/24 dev ppp0
```

### ❌ Starlink CGNAT no permite conexión entrante

**Solución:** Usa Tailscale (funciona detrás de NAT)

---

## Comparación Final

| Característica | Tailscale | VPN MikroTik |
|----------------|-----------|--------------|
| **Funciona con CGNAT** | ✅ Sí | ❌ No |
| **Configuración** | 5 minutos | 30+ minutos |
| **Mantenimiento** | Automático | Manual |
| **Seguridad** | WireGuard (muy alta) | IPsec (alta) |
| **Velocidad** | Excelente | Buena |
| **Estabilidad** | Excelente | Depende de ISP |
| **Costo** | Gratis (100 dispositivos) | Incluido |
| **Recomendación** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## Resumen de Pasos Rápidos (Tailscale)

```bash
# 1. VPS
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# 2. Tablet/PC
# Descargar Tailscale e iniciar sesión

# 3. MikroTik (Opcional - subnet router)
/system package install file-name=tailscale.ipk
/interface/tailscale add name="tailscale1" auth-key=xxx advertise-routes=192.168.88.0/24 disabled=no

# 4. SIIP config.py
IMPRESORA_IP = '100.101.102.103'  # IP de Tailscale

# 5. Probar
tailscale ping 192.168.88.128
ping 192.168.88.128
telnet 192.168.88.128 9100
```

---

## Soporte

- Tailscale Docs: https://tailscale.com/kb/
- MikroTik VPN Docs: https://wiki.mikrotik.com/wiki/Manual:Interface/L2TP
- Logs SIIP: `app/logs/app.log`

---

**¿Necesitas ayuda?** Revisa los logs y verifica cada paso del proceso de conexión VPN.

