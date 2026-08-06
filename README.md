# SADP GUI para Linux - Descubridor de Cámaras Hikvision

Aplicación gráfica nativa para Linux que descubre y lista cámaras IP y equipos Hikvision en la red local.

## 🚀 Instalación rápida

```bash
# Ejecuta SIN sudo (el instalador pedirá sudo cuando sea necesario)
bash setup-produccion.sh

# Después de la instalación abre la app desde el menú de Ubuntu o con:
sadp-gui
```

## 📋 Requisitos

- Ubuntu 20.04 LTS o superior (Debian y derivados compatibles)
- Acceso a la red donde estén las cámaras Hikvision

## ✨ Características principales

- **Descubrimiento automático de dispositivos**: Escaneo multicast SADP en toda la red.
- **Soporte fuera de subred**: Detecta cámaras independientemente de si están en un rango de IP distinto al del equipo.
- **Escaneo multi-interfaz**: Soporta múltiples tarjetas de red, WiFi, radioenlaces, adaptadores USB y VLANs.
- **Traducción de tipo de equipo**: Muestra categorías comprensibles en español (`Cámara IP`, `Cámara PTZ`, `NVR`, `DVR`, `Videoportero`, etc.).
- **Tabla interactiva**: Ordenamiento avanzado y filtro de búsqueda en tiempo real.
- **Acceso web directo**: Doble clic sobre la IP para abrir la interfaz web del dispositivo en el navegador.
- **Exportar datos a CSV**: Guarda la lista detectada eligiendo ruta de destino.
- **Configuración automática**: Ajuste de firewall (`ufw`) y capacidades de red (`setcap`) automáticas.

## 🖥️ Integración como aplicación

El instalador crea un lanzador de usuario en `~/.local/share/applications/sadp-gui.desktop` y un comando `sadp-gui`, por lo que la aplicación aparecerá en el menú de Ubuntu como cualquier otra app de usuario.

## 📚 Documentación

- [Guía Completa de Uso e Instalación](docs/GUIA.md)

## 📄 Licencia

MIT License — ver [LICENSE](LICENSE)

## 👨‍💻 Autor

Mnxx29

---

**Nota**: Esta aplicación usa internamente [hikvision-tooling](https://github.com/cameronnewman/hikvision-tooling) para realizar el descubrimiento SADP.
