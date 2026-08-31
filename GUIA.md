# Guía Técnica de SADP GUI para Linux

Documentación de arquitectura, instalación, operación de red y solución de problemas para **SADP GUI para Linux**.

---

## Requisitos del sistema

- **Sistema operativo**: Ubuntu 20.04 LTS o superior (Debian y derivados compatibles).
- **Entorno de ejecución**: Python 3.8+ con paquete `PyQt6`.
- **Compilador**: Go 1.16+ (necesario durante la instalación para compilar el módulo ejecutable de comandos de modificación).
- **Permisos de red**: Capacidad `cap_net_raw` asignada al binario de modificación y acceso a reglas UFW / sysctl.

---

## Instalación y desinstalación

### Instalación en producción

Ejecutar el script de instalación desde el directorio raíz del repositorio sin anteponer `sudo`:

```bash
bash setup-produccion.sh
```

El script ejecuta las siguientes tareas:
1. Instalación de dependencias del sistema (`python3-pyqt6`, `golang-go`, `ufw`, `libcap2-bin`).
2. Compilación del ejecutable secundario en Go (`sadp-linux-amd64`).
3. Asignación de la capacidad de red `cap_net_raw=ep` al binario compilado.
4. Configuración de reglas UFW: puerto de destino `37020/udp`, tráfico de respuesta `from any port 37020 proto udp` y tráfico multicast saliente `224.0.0.0/4`.
5. Ajuste de parámetros del kernel (`net.ipv4.conf.all.rp_filter=2`) para recepción de respuestas fuera de subred.
6. Instalación del ejecutable `sadp_discover.py` y configuración del lanzador `sadp-gui` en `~/.local/bin/`.
7. Creación del acceso directo `.desktop` en `~/.local/share/applications/`.

### Ejecución de la aplicación

- Desde la terminal:
  ```bash
  sadp-gui
  ```
- Desde la interfaz gráfica: Buscar **"SADP GUI"** en el menú de aplicaciones del sistema.

### Desinstalación limpia

Para remover los binarios, lanzadores y accesos directos instalados:

```bash
bash clean-install.sh
```

---

## Manual de operación

### 1. Escaneo y descubrimiento ("Refresh")
- Al pulsar **Refresh**, el sistema ejecuta el motor nativo `sadp_discover.py`.
- Se envían sondas XML en paralelo a través de todas las interfaces de red activas en estado `UP` (Ethernet, WiFi, adaptadores USB, VLANs).
- La tabla actualiza en tiempo real el conteo total de dispositivos detectados.

### 2. Modificación de parámetros de red ("Modificar Red")
- Seleccionar un dispositivo en la tabla para cargar su información en el panel lateral.
- Habilitar o deshabilitar DHCP según los requerimientos del segmento.
- Definir Dirección IP, Máscara de subred, Puerta de enlace y Puertos (HTTP / SDK).
- Ingresar la contraseña del usuario administrador (`admin`) en la sección de verificación de seguridad.
- Pulsar **Modify**. La aplicación enviará la trama SADP `update` firmada y refrescará el listado al recibir confirmación del equipo.

### 3. Desvinculación de servicios en la nube ("Unbind")
- Seleccionar el dispositivo objetivo.
- Ingresar la contraseña de administrador.
- Pulsar **Unbind** para desvincular el dispositivo de cuentas Hik-Connect o Ezviz asociadas.

### 4. Filtrado en tiempo real ("Filter")
- El cuadro de búsqueda filtra instantáneamente por cualquiera de las columnas: IP, MAC, Modelo, Estado, Puerto, Número de Serie o Versión de Firmware.

### 5. Navegación directa a la interfaz web
- Hacer doble clic sobre la celda de dirección IP de cualquier dispositivo activo para abrir su interfaz de administración HTTP en el navegador predeterminado.

### 6. Exportación de datos a CSV ("Export")
- Pulsar **Export** para guardar la lista de dispositivos detectados en formato `.csv`.
- El archivo generado incluye la totalidad de parámetros técnicos: IP, MAC, Tipo traducido, Estado, Puerto SDK, Puerto HTTP, Número de serie, Versión de firmware, Máscara de subred, Gateway y estado DHCP.

---

## Arquitectura de red y protocolo SADP

El protocolo SADP (Search Active Devices Protocol) opera mediante tramas UDP multicast hacia la dirección `239.255.255.250:37020` y difusiones broadcast hacia `255.255.255.255:37020`.

### Consideraciones técnicas implementadas

- **Enlace de puerto fijo (37020/udp)**: El motor de descubrimiento se enlaza explícitamente al puerto 37020. Esto asegura que las respuestas enviadas por los dispositivos desde el puerto fuente 37020 coincidan con las reglas de filtrado del firewall UFW.
- **Filtrado de ruta inversa (rp_filter)**: El kernel de Linux descarta por defecto paquetes entrantes cuyo origen no coincida con la tabla de ruteo de la interfaz de entrada. Se establece `net.ipv4.conf.all.rp_filter=2` (Loose Mode) para permitir la recepción de tramas provenientes de subredes distintas.
- **Multicast en múltiples interfaces**: Las sondas se transmiten especificando cada interfaz activa mediante `IP_MULTICAST_IF`, evitando que las consultas queden restringidas únicamente a la ruta por defecto del sistema.

---

## Diagnóstico y resolución de problemas

### Ejecución del script de diagnóstico automatizado

El proyecto incluye un script de auditoría de red y sistema que verifica 9 puntos críticos:

```bash
bash diagnostico.sh
```

El script evalúa:
1. Existencia y permisos del binario SADP.
2. Asignación de la capacidad `cap_net_raw=ep`.
3. Estado operativo e direcciones IP asignadas a las interfaces de red.
4. Reglas del firewall UFW y cadenas iptables para UDP 37020.
5. Valor de `rp_filter` en el kernel para la totalidad de interfaces.
6. Existencia de rutas para el grupo multicast `239.255.255.250`.
7. Permisos NOPASSWD en `/etc/sudoers.d/sadp-gui-routing`.
8. Ejecución directa del motor de descubrimiento por consola.
9. Inspección de tráfico en tiempo real mediante `tcpdump`.

### Prueba directa del módulo de descubrimiento por consola

Para verificar la detección de equipos fuera de la interfaz gráfica:

```bash
python3 sadp_discover.py --debug --timeout 10
```

Para inspeccionar la estructura binaria y XML de las respuestas sin parsear:

```bash
python3 sadp_discover.py --raw --timeout 10
```
