# SADP GUI para Linux

Aplicación gráfica nativa para Linux para el descubrimiento, diagnóstico y gestión de red de cámaras IP y dispositivos Hikvision en redes locales y subredes múltiples.

## Instalación

```bash
bash setup-produccion.sh
```

Ejecutar sin `sudo`. El instalador solicitará privilegios de superusuario únicamente cuando sea necesario para la configuración de red y dependencias.

Para ejecutar la aplicación después de instalar:

```bash
sadp-gui
```

## Requisitos del sistema

- Ubuntu 20.04 LTS o superior (o distribuciones basadas en Debian/Ubuntu).
- Python 3.8+ con `PyQt6`.
- Go (requerido para la compilación del binario auxiliar de modificaciones de red).
- Interfaz de red activa conectada al segmento o VLAN de los dispositivos.

## Arquitectura y características técnicas

- **Motor de descubrimiento nativo (Python)**: Implementación directa del protocolo SADP vía UDP multicast (`239.255.255.250:37020`) y broadcast, enlazada directamente al puerto 37020 para garantizar la recepción de respuestas a través de reglas de firewall.
- **Soporte multi-interfaz y VLAN**: Envío de sondas en todas las interfaces de red activas de forma simultánea.
- **Soporte fuera de subred**: Detección de dispositivos sin importar si se encuentran en un segmento IP distinto al del equipo local, mediante configuración del kernel (`rp_filter=2`).
- **Modificación de parámetros de red**: Cambio de IP, máscara de subred, puerta de enlace, puertos HTTP/SDK y DHCP mediante firma de contraseña de administrador.
- **Desvinculación Hik-Connect (Unbind)**: Liberación de equipos asociados a cuentas de usuario mediante comandos de control SADP.
- **Traducción de tipo de dispositivo**: Identificación de códigos numéricos SADP y prefijos de modelo (`Cámara IP`, `Cámara PTZ`, `NVR`, `DVR`, `Videoportero`, `Switch PoE`).
- **Exportación CSV completa**: Generación de reportes CSV estructurados con la totalidad de atributos de red detectados (`ip`, `mac`, `tipo`, `estado`, `puerto`, `http_port`, `serial`, `version`, `subnet`, `gateway`, `dhcp`).
- **Herramienta de diagnóstico integrada**: Script `diagnostico.sh` para auditoría de sockets, reglas UFW, permisos `cap_net_raw`, capturas `tcpdump` y pruebas del protocolo.

## Integración con el sistema

El instalador genera el comando global `sadp-gui` en `~/.local/bin/` y crea el archivo de escritorio `~/.local/share/applications/sadp-gui.desktop` para integración directa en el menú de aplicaciones.

## Documentación detallada

Consulte la [Guía Técnica de Uso y Red](GUIA.md) para especificaciones del protocolo, troubleshooting y configuración avanzada.

## Licencia

MIT License — consulte el archivo [LICENSE](LICENSE) para más detalles.
