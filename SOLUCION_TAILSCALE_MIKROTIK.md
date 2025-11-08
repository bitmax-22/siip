# Solución: Instalar Tailscale en MikroTik RouterOS v7

## Problema
El paquete de Tailscale no está disponible directamente en la URL de descarga para RouterOS v7.16.

## Soluciones

---

## ✅ **SOLUCIÓN 1: Usar Containers (RouterOS v7.6+)**

Tu MikroTik hEX es compatible con containers en RouterOS v7.16.

### Paso 1: Instalar Paquete "Extra packages"

**En Winbox:**
1. System → Packages
2. Check For Updates
3. Busca "extra" o "extra packages"
4. Download & Install

**O via Terminal:**
```bash
/system package update download-and-install extra-package
```

### Paso 2: Habilitar Container Mode

```bash
/system device-mode/update container=yes
```
**IMPORTANTE:** Tu router se reiniciará automáticamente. Espera 2-3 minutos.

### Paso 3: Configurar Interfaz Virtual

```bash
/interface/veth/add name=veth1 address=172.17.0.2/24 gateway=172.17.0.1
/interface/bridge/add name=dockers
/interface/bridge/port/add bridge=dockers interface=veth1
/ip/address/add address=172.17.0.1/24 interface=dockers
```

### Paso 4: Crear y Ejecutar Container de Tailscale

```bash
# Agregar container de Tailscale
/container/add remote-image=tailscale/tailscale:latest interface=veth1 root-dir=usb1/tailscale hostname=tailscale start-on-boot=yes

# Iniciar container
/container/start tailscale

# Verificar estado
/container print
```

### Paso 5: Configurar Tailscale en el Container

```bash
# Acceder al container
/container/exec tailscale command="tailscale up --authkey=TU_AUTH_KEY_AQUI --advertise-routes=192.168.88.0/24 --accept-routes"
```

**Reemplaza `TU_AUTH_KEY_AQUI` con tu auth key de Tailscale.**

---

## ✅ **SOLUCIÓN 2: Instalar Tailscale Localmente (Windows)**

**OPCIÓN MÁS FÁCIL:** Si no quieres configurar containers, puedes instalar Tailscale en un PC Windows de la red local y usarlo como "exit node" o "relay".

### En la PC Windows de la red:
```powershell
# Instalar Tailscale
Invoke-WebRequest -Uri "https://pkgs.tailscale.com/stable/windows/tailscale-setup-latest.exe" -OutFile "$env:TEMP\tailscale-setup.exe"
Start-Process -FilePath "$env:TEMP\tailscale-setup.exe" -ArgumentList "-q" -Wait

# Configurar como subnet router
tailscale up --advertise-routes=192.168.88.0/24
```

### En el VPS Windows Server:
```powershell
# Instalar Tailscale
tailscale up

# Aceptar rutas
tailscale up --accept-routes
```

**Desventaja:** La PC Windows debe estar encendida siempre.

---

## ✅ **SOLUCIÓN 3: Usar WireGuard Manualmente (Avanzado)**

Si nada de lo anterior funciona, puedes configurar WireGuard manualmente en el MikroTik (la base de Tailscale).

**Pero es MUCHO más complejo que Tailscale.**

---

## 🎯 **RECOMENDACIÓN**

**Para RouterOS v7, la SOLUCIÓN 2 (PC Windows local) es la más rápida:**

1. Ya instalaste Tailscale en tu VPS ✅
2. Solo necesitas:
   - Instalar Tailscale en un PC Windows de tu red local
   - Configurarlo como subnet router
   - Listo ✅

**¿Prefieres esta solución o quieres intentar containers?**

