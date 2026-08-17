# Guía Completa de SADP GUI para Linux

Esta guía contiene toda la información sobre la instalación, uso, arquitectura de red y solución de problemas de **SADP GUI para Linux**.

---

## 📋 Requisitos del Sistema

- **Sistema Operativo**: Ubuntu 20.04 LTS o superior (Debian y derivados compatibles).
- **Red**: Conexión a la red local donde se encuentren las cámaras o equipos Hikvision (Ethernet, WiFi, radioenlaces, adaptadores USB, etc.).
- **Dependencias**: Python 3 con `PyQt6` y Go (el script de instalación se encarga de instalarlas automáticamente mediante `apt`).

---

## 🚀 Instalación y Desinstalación

### Instalación Rápida
Ejecuta el script instalador desde la carpeta del proyecto **SIN utilizar `sudo`** (el script solicitará permisos cuando sea necesario):

```bash
bash setup-produccion.sh
```

El instalador realiza lo siguiente automáticamente:
1. Instala dependencias (`python3-pyqt6`, `golang-go`, `ufw`, `libcap2-bin`).
2. Compila el binario ejecutable subyacente en Go (`sadp-linux-amd64`).
3. Le asigna permisos de red `setcap cap_net_raw=ep` al binario para operar sockets sin requerir ser root.
4. Configura el firewall (`ufw`) en el puerto UDP **37020** y multicast (`224.0.0.0/4`).
5. Configura el kernel (`rp_filter=2`) para recibir tramas de cámaras en subredes distintas.
6. Crea el comando `sadp-gui` en `~/.local/bin/` y el acceso directo de escritorio `.desktop` para el menú de Ubuntu.

### Cómo Iniciar la Aplicación
Una vez instalado, puedes abrir la aplicación de dos formas:
- Desde el menú de aplicaciones de Ubuntu buscando **"SADP GUI"**.
- Desde la terminal ejecutando:
  ```bash
  sadp-gui
  ```

### Desinstalación
Si deseas eliminar la aplicación del sistema:
```bash
bash clean-install.sh
```
*(O manualmente borrando `~/.local/bin/sadp/`, `~/.local/bin/sadp-gui` y `~/.local/share/applications/sadp-gui.desktop`)*.

---

## 🖥️ Manual de Uso

1. **Escaneo y Refresco ("Refresh")**:
   - Presiona **Refresh** para iniciar el escaneo de red.
   - El escaneo consulta automáticamente todas las interfaces físicas e inalámbricas activas en la máquina (Ethernet, WiFi, antenas, USB, VLANs).
2. **Modificación de Parámetros de Red ("Modificar Red")**:
   - Haz clic sobre un dispositivo de la lista para seleccionarlo y abrir el panel **Modify Network Parameters**.
   - **Cambiar IP y Gateway**: Modifica la dirección IP, Máscara de subred, Gateway o Puerto SDK/HTTP según las necesidades del nuevo sitio.
   - **Soporte fuera de subred**: Puedes cambiar la IP de cámaras traídas de otros centros aunque estén en un rango de IP/subred completamente distinto al de tu computador, sin necesidad de entrar a la interfaz web ni cambiar la IP de tu PC.
   - **Verificación de Seguridad**: Introduce la contraseña del usuario administrador del dispositivo (`admin`) en el campo **Administrator Password** y haz clic en **Modify**.
   - Al confirmarse el cambio, la aplicación notificará el éxito y refrescará la lista automáticamente mostrando el nuevo rango de IP.
3. **Desvincular Dispositivo ("Unbind")**:
   - Para liberar cámaras vinculadas a cuentas Hik-Connect / Ezviz en otros centros, selecciona el equipo, ingresa la contraseña de administrador y presiona **Unbind**.
4. **Filtrado en Tiempo Real ("Filter")**:
   - Escribe en el cuadro de búsqueda para filtrar al instante por IP, MAC, Modelo, Estado, Número de Serie o Versión de Firmware.
5. **Traducción Inteligente de Tipos de Dispositivo**:
   - Muestra el tipo de equipo de forma clara en español: `Cámara IP`, `Cámara PTZ`, `NVR`, `DVR`, `Videoportero` o `Switch PoE`.
6. **Abrir Interfaz Web de la Cámara**:
   - Haz **doble clic sobre la Dirección IP** de un registro para abrir su panel web de administración (`http://<IP>`) directamente en el navegador por defecto.
7. **Exportación a CSV ("Export")**:
   - Haz clic en **Export** para guardar la lista de dispositivos detectados en un archivo `.csv`.

---

## 🌐 Funcionamiento Técnico de Red (Fuera de Subred y Multi-Interfaz)

SADP (Search Active Devices Protocol) utiliza paquetes **UDP Multicast** a la dirección `239.255.255.250:37020` y difusión broadcast `255.255.255.255:37020`.

- **Modificación y Descubrimiento fuera de subred**: Las cámaras Hikvision responden y procesan órdenes SADP a nivel de Capa 2 (asociadas a la dirección MAC del dispositivo), independientemente de si la IP asignada coincide o no con la subred de la computadora.
- **Protocolo SADP Update**: Al modificar parámetros de red, la app envía un paquete de control SADP (`update`) firmado con la contraseña de administrador y referenciado a la MAC del equipo objetivo.
- **Configuración de Kernel (rp_filter)**: Para evitar que el Kernel de Linux bloquee respuestas de equipos en subredes distintas, el instalador configura `net.ipv4.conf.all.rp_filter=2` (Loose Mode).
- **Múltiples Tarjetas de Red / Antenas**: El lanzador `sadp-gui` y la app habilitan rutas multicast en **todas las interfaces de red activas** (`state UP`), permitiendo encontrar y configurar cámaras en entornos con múltiples subredes o radioenlaces.

---

## ❓ Solución de Problemas (Troubleshooting)

### 1. No se encuentran dispositivos en la red
- Verifica que el cable de red o enlace de radio esté correctamente conectado y la interfaz esté activa.
- Comprueba el estado del firewall:
  ```bash
  sudo ufw status verbose
  ```
  Asegúrate de que el puerto UDP `37020` esté permitido.

### 2. Probar el binario directamente por consola
Si deseas realizar una prueba directa de bajo nivel en la consola sin la interfaz gráfica:
```bash
~/.local/bin/sadp/sadp-linux-amd64 discover:sadp
```
Esto imprimirá por consola la salida en texto plano de las cámaras encontradas.

### 3. Error de permisos al ejecutar el binario
Si el binario no puede enviar paquetes raw, asegúrate de reinstalar `libcap2-bin` y asignar capabilities:
```bash
sudo apt install -y libcap2-bin
sudo setcap cap_net_raw=ep ~/.local/bin/sadp/sadp-linux-amd64
```
