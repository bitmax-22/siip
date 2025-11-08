# Instalación Rápida de Tailscale para Impresión Remota

## 🎯 Objetivo
Conectar tu VPS Windows Server a la impresora local `192.168.88.128:9100` usando Tailscale.

---

## ⚡ Configuración para VPS Windows Server

### Paso 0: Instalar Tailscale en Windows Server

1. **Descargar Tailscale para Windows:**
   - Ve a: https://tailscale.com/download/windows
   - Descarga el instalador `.exe`
   - O usa este comando en PowerShell:
   ```powershell
   # Descargar
   Invoke-WebRequest -Uri "https://pkgs.tailscale.com/stable/windows/tailscale-setup-latest.exe" -OutFile "$env:TEMP\tailscale-setup.exe"
   
   # Instalar (ejecutar como Administrador)
   Start-Process -FilePath "$env:TEMP\tailscale-setup.exe" -ArgumentList "-q" -Wait
   ```

2. **Iniciar sesión:**
   - Abre **Tailscale** desde el menú Inicio
   - Click "Sign in" → Inicia sesión con Google/Microsoft
   - Click "Connect"

3. **Verificar instalación:**
   ```powershell
   tailscale status
   # Deberías ver tu servidor con IP tipo 100.x.x.x
   ```

**¡Ya tienes Tailscale instalado en tu VPS!** ✅

---

## Opción 1: Tailscale en MikroTik (RECOMENDADA) ⭐

Esta opción expone toda tu red local `192.168.88.x` a través de Tailscale.

### Paso 1: Preparar Auth Key

1. Abre: https://login.tailscale.com/admin/settings/keys
2. Click "Generate auth key"
3. Desmarca "Ephemeral" (para conexión permanente)
4. Opcional: configura "Reusable" si quieres reutilizar la key
5. Click "Generate key"
6. **COPIA la key** (es algo como `tskey-auth-xxxxxxxxxxxxxxxxx`)
7. Click "Close" (después de esta pantalla ya no podrás ver la key de nuevo)

### Paso 2: Instalar Tailscale en MikroTik

**Usando Winbox:**

1. Abre Winbox y conéctate a tu MikroTik
2. Ve a **System → Packages**
3. Click **Check For Updates** (espera a que cargue la lista)
4. Busca "tailscale" en la lista
5. Si aparece:
   - Click en "tailscale"
   - Click "Download & Install"
6. Si NO aparece:
   - Ve a **Terminal** en Winbox
   - Ejecuta:
   ```
   /tool fetch url="https://pkgs.tailscale.com/stable/mikrotik/tailscale-latest-arm64.ipk" dst="tailscale.ipk"
   /system package install file-name=tailscale.ipk
   ```
   - Si `arm64` no funciona, intenta `tailscale-latest-i386.ipk` (arquitectura de 32 bits)

### Paso 3: Configurar Subnet Router

**En Terminal de MikroTik (Winbox → Terminal):**

```bash
# Crear interfaz Tailscale
/interface/tailscale add name="tailscale1" mtu=1420

# Configurar con tu auth key
/interface/tailscale set tailscale1 auth-key=tskey-auth-xxxxxxxxxxxxxxxxx advertise-routes=192.168.88.0/24

# Habilitar interfaz
/interface/tailscale set tailscale1 disabled=no

# Ver estado
/interface/tailscale print
/ip address print
```

**Reemplaza `tskey-auth-xxxxxxxxxxxxxxxxx` con TU auth key real.**

### Paso 4: Verificar en Dashboard de Tailscale

1. Abre: https://login.tailscale.com/admin/machines
2. Deberías ver:
   - Tu **MikroTik** listado
   - Con rutas: `192.168.88.0/24`
3. Anota la **IP de Tailscale** del MikroTik (algo como `100.101.102.103`)

### Paso 5: Configurar VPS Windows Server para Aceptar Rutas

**Si ya instalaste Tailscale en tu VPS Windows Server (Paso 0), ahora configura:**

```powershell
# Abrir PowerShell como Administrador
# Y ejecutar:

# Configurar para aceptar rutas de otros dispositivos Tailscale
tailscale up --accept-routes
```

**Esto permitirá que tu VPS acceda a la red 192.168.88.x anunciada por el MikroTik.**

### Paso 6: Verificar Conectividad desde VPS

**En PowerShell del VPS:**

```powershell
# Ver todos los dispositivos Tailscale
tailscale status

# Verificar conectividad al MikroTik
Test-Connection 192.168.88.1

# Verificar conectividad a la impresora
Test-Connection 192.168.88.128
```

### Paso 7: Probar Conexión

**Desde PowerShell del VPS:**

```powershell
# Ping a la impresora vía Tailscale
Test-Connection 192.168.88.128

# Probar puerto de impresora (PowerShell)
Test-NetConnection -ComputerName 192.168.88.128 -Port 9100
```

**¡Si ambos comandos muestran "Success", YA ESTÁS LISTO!** ✅

### Paso 8: Actualizar SIIP

**NO necesitas cambiar nada en `config.py`** - la IP `192.168.88.128` seguirá funcionando.

**Reiniciar SIIP:**
```powershell
# Desde la carpeta del proyecto en PowerShell
python run.py
```

---

## Opción 2: Tailscale Solo en Dispositivos (Alternativa)

Si no puedes instalar Tailscale en el MikroTik, puedes instalarlo solo en los dispositivos.

### Paso 1: Ya Instalado en VPS Windows

**Ya lo hiciste en el Paso 0 anterior.** ✅

### Paso 2: Instalar en Tablet/PC de Panadería

**Android:**
- Descargar: https://play.google.com/store/apps/details?id=com.tailscale.ipn
- Iniciar sesión
- Activar "Connect"

**Windows:**
- Descargar: https://tailscale.com/download/windows
- Instalar e iniciar sesión
- Click "Connect"

### Paso 3: Obtener IPs de Tailscale

```powershell
# En PowerShell del VPS
tailscale status

# Verás algo como:
# 100.101.102.103   vps-siip      your-email@gmail.com
# 100.104.105.106   tablet        your-email@gmail.com
```

### Paso 4: Configurar Impresora en Tablet

1. Descargar **PrintShare** o similar en la tablet
2. Agregar impresora: IP `192.168.88.128` puerto `9100`
3. Probar impresión

**LIMITACIÓN:** La impresión seguirá siendo local en la tablet. El VPS NO podrá imprimir directamente.

---

## Comparación

| Característica | Opción 1 (Subnet Router) | Opción 2 (Solo Apps) |
|----------------|-------------------------|---------------------|
| VPS puede imprimir | ✅ SÍ | ❌ NO |
| Facilidad | ⭐⭐⭐ Media | ⭐⭐⭐⭐⭐ Fácil |
| Configuración MikroTik | Requerida | No necesaria |
| Acceso a red completa | ✅ Sí | ❌ No |
| Recomendación | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## Solución de Problemas

### ❌ Error: "arm64 package not found" en MikroTik

**Verifica arquitectura:**
```bash
/system resource print
```

**Architectura correcta:**
- `arm64` → usa `tailscale-latest-arm64.ipk`
- `mipsbe` → usa `tailscale-latest-mipsbe.ipk`
- `i386` o `x86` → usa `tailscale-latest-i386.ipk`

### ❌ "Auth key invalid"

1. Genera una nueva auth key
2. Asegúrate de copiar toda la key completa
3. No uses una key "Ephemeral" deja desmarcada

### ❌ VPS no puede hacer ping a 192.168.88.128

**Verificar:**
```bash
# En VPS
tailscale status

# Asegúrate de ver tu MikroTik listado
# Si no aparece, verifica que Tailscale esté corriendo en MikroTik:
```

**En MikroTik:**
```bash
/interface/tailscale print
# Debe mostrar "R" (running)
```

### ❌ Tailscale no permite anunciar rutas

**En Tailscale Admin:**
1. Ve a: https://login.tailscale.com/admin/machines
2. Click en tu MikroTik
3. Click "..." → "Edit route settings"
4. Activa "Advertise Subnet Routes"
5. Marca `192.168.88.0/24`
6. Click "Save"

### ❌ No aparece rutas en Dashboard

**Verificar logs en MikroTik:**
```bash
/log print where topics~"tailscale"
```

**Reiniciar interfaz:**
```bash
/interface/tailscale disable tailscale1
/interface/tailscale enable tailscale1
```

---

## Verificación Final

**Checklist:**
- [ ] MikroTik aparece en https://login.tailscale.com/admin/machines
- [ ] Rutas `192.168.88.0/24` están anunciadas
- [ ] VPS aparece en la lista de máquinas
- [ ] Desde VPS: `ping 192.168.88.128` funciona
- [ ] Desde VPS: `telnet 192.168.88.128 9100` conecta
- [ ] SIIP reiniciado
- [ ] Pedido de prueba imprime correctamente

---

## Siguiente Paso

Una vez verificada la conectividad:
1. Reinicia SIIP
2. Haz un pedido de prueba
3. Verifica que la impresora imprima automáticamente

**Si todo funciona → ¡ÉXITO! 🎉**

