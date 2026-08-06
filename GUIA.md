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
   - El escaneo consulta automáticamente todas las interfaces físicas y inalámbricas activas en la máquina (Ethernet, WiFi, antenas, USB, VLANs).
2. **Filtrado en Tiempo Real ("Filter")**:
   - Escribe en el cuadro de búsqueda para filtrar al instante por IP, MAC, Modelo, Estado, Número de Serie o Versión de Firmware.
3. **Traducción Inteligente de Tipos de Dispositivo**:
   - Muestra el tipo de equipo de forma clara en español: `Cámara IP`, `Cámara PTZ`, `NVR`, `DVR`, `Videoportero` o `Switch PoE`.
4. **Abrir Interfaz Web de la Cámara**:
   - Haz **doble clic sobre la Dirección IP** de un registro para abrir su panel web de administración (`http://<IP>`) directamente en el navegador por defecto.
5. **Exportación a CSV ("Export")**:
   - Haz clic en **Export** para guardar la lista de dispositivos detectados en un archivo `.csv`. Un cuadro de diálogo te permitirá elegir el nombre y directorio de destino.

---

## 🌐 Funcionamiento Técnico de Red (Fuera de Subred y Multi-Interfaz)

SADP (Search Active Devices Protocol) utiliza paquetes **UDP Multicast** a la dirección `239.255.255.250:37020`.

- **Cámaras fuera de rango de IP**: Las cámaras Hikvision responden a nivel de Capa 2 (difusión por MAC) independientemente de si su dirección IP coincide con la subred del computador. Para evitar que el Kernel de Linux bloquee estas respuestas, el instalador configura `net.ipv4.conf.all.rp_filter=2` (Loose Mode).
- **Múltiples Tarjetas de Red / Antenas**: El lanzador `sadp-gui` y la app habilitan rutas multicast en **todas las interfaces de red activas** (`state UP`), permitiendo encontrar cámaras en entornos con múltiples subredes o radioenlaces.

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
