import sys
import subprocess
import csv
import io
import webbrowser
import os
import shutil
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QMessageBox, QLabel, QProgressBar,
                             QFrame, QScrollArea, QCheckBox, QLineEdit, QFileDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QFont


class SortableItem(QTableWidgetItem):
    """QTableWidgetItem que soporta clave de ordenación personalizada."""
    def __init__(self, text: str, sort_key=None):
        super().__init__(text)
        self.sort_key = sort_key if sort_key is not None else text

    def __lt__(self, other):
        try:
            # Comparar por la clave de ordenación si existe
            return self.sort_key < other.sort_key
        except Exception:
            return super().__lt__(other)

def traducir_tipo_dispositivo(tipo_code: str, serial_model: str = "") -> str:
    """Traduce códigos numéricos SADP y prefijos de modelo Hikvision a nombres comprensibles en español."""
    tipo_str = str(tipo_code).strip()
    model_upper = str(serial_model).upper()
    
    # 1. Mapa de códigos numéricos Hikvision SADP conocidos
    MAPA_CODIGOS = {
        # Cámaras IP (DS-2CD...)
        "141938": "Cámara IP",
        "147479": "Cámara IP",
        "141904": "Cámara IP",
        "141937": "Cámara IP",
        "141939": "Cámara IP",
        "141950": "Cámara IP",
        "147456": "Cámara IP",
        # Cámaras PTZ / Speed Dome (DS-2SE, DS-2DE...)
        "196607": "Cámara PTZ",
        "196608": "Cámara PTZ",
        "196609": "Cámara PTZ",
        # NVR (DS-96, DS-76...)
        "46877": "NVR",
        "46848": "NVR",
        "46849": "NVR",
        "46876": "NVR",
        "46878": "NVR",
        # DVR (DS-72, DS-71...)
        "42240": "DVR",
        "42241": "DVR",
        "42242": "DVR",
        # Videoporteros / Control de Acceso
        "262144": "Videoportero",
        "262145": "Videoportero",
        # Switches PoE
        "393216": "Switch PoE",
    }
    
    if tipo_str in MAPA_CODIGOS:
        return f"{MAPA_CODIGOS[tipo_str]} ({tipo_str})"
        
    # 2. Inferencia inteligente por prefijo de modelo/serial
    if "DS-2SE" in model_upper or "DS-2DE" in model_upper or "DS-2DF" in model_upper or "PTZ" in model_upper:
        return f"Cámara PTZ ({tipo_str})" if tipo_str.isdigit() else "Cámara PTZ"
    elif "DS-2CD" in model_upper or "DS-2CV" in model_upper or "IPC" in model_upper:
        return f"Cámara IP ({tipo_str})" if tipo_str.isdigit() else "Cámara IP"
    elif "DS-96" in model_upper or "DS-76" in model_upper or "DS-77" in model_upper or "NVR" in model_upper:
        return f"NVR ({tipo_str})" if tipo_str.isdigit() else "NVR"
    elif "DS-71" in model_upper or "DS-72" in model_upper or "DS-73" in model_upper or "DVR" in model_upper:
        return f"DVR ({tipo_str})" if tipo_str.isdigit() else "DVR"
    elif "DS-KD" in model_upper or "DS-KV" in model_upper or "DS-KH" in model_upper:
        return f"Videoportero ({tipo_str})" if tipo_str.isdigit() else "Videoportero"
    elif "DS-3E" in model_upper:
        return f"Switch PoE ({tipo_str})" if tipo_str.isdigit() else "Switch PoE"

    # Si es numérico sin mapeo específico
    if tipo_str.isdigit():
        return f"Dispositivo ({tipo_str})"
    return tipo_str if tipo_str else "N/A"

class ScanThread(QThread):
    """Thread para ejecutar el escaneo sin congelar la interfaz"""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    devices = pyqtSignal(list)
    
    def run(self):
        try:
            # 0. En sistemas Linux, aplicar sysctl para rp_filter (permitir subredes distintas)
            # y habilitar la ruta multicast en TODAS las interfaces de red activas
            if sys.platform.startswith('linux'):
                try:
                    cmd_prep = (
                        "sudo sysctl -w net.ipv4.conf.all.rp_filter=2 >/dev/null 2>&1 || true; "
                        "sudo sysctl -w net.ipv4.conf.default.rp_filter=2 >/dev/null 2>&1 || true; "
                        "for iface in $(ip -o link show | awk -F': ' '$2 !~ /^lo/ && $3 ~ /state (UP|UNKNOWN)/ {print $2}' | cut -d'@' -f1); do "
                        "  [ -z \"$iface\" ] && continue; "
                        "  sudo ip route add 239.255.255.250/32 dev \"$iface\" 2>/dev/null || "
                        "  sudo ip route change 239.255.255.250/32 dev \"$iface\" 2>/dev/null || true; "
                        "done"
                    )
                    subprocess.run(cmd_prep, shell=True, timeout=5)
                except Exception as prep_err:
                    print(f"[DEBUG ScanThread] Aviso preparando interfaces: {prep_err}")

            # Obtener la ruta del directorio donde está este script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 1. Intentar buscar primero el binario directamente en el PATH del sistema
            binario_path = shutil.which("sadp-linux-amd64")
            
            if not binario_path:
                # Rutas posibles del binario (en orden de preferencia)
                posibles_rutas = [
                    os.path.join(script_dir, "sadp-linux-amd64"),
                    os.path.join(script_dir, "sadp-linux-amd64-real"),
                    os.path.expanduser("~/.local/bin/sadp/sadp-linux-amd64"),
                    os.path.expanduser("~/.local/bin/sadp-linux-amd64"),
                    "/usr/local/bin/sadp-linux-amd64",
                    "./sadp-linux-amd64",
                    "./sadp-linux-amd64-real",
                ]
                
                for ruta in posibles_rutas:
                    if os.path.exists(ruta):
                        binario_path = ruta
                        break
            
            if not binario_path:
                self.error.emit(f"No se encontró el binario SADP.\n\nAsegúrate de que el archivo 'sadp-linux-amd64' esté en el mismo directorio que gui_sadp.py o instalado en ~/.local/bin/sadp/")
                self.finished.emit()
                return
            
            # Ejecutar el binario Go directamente
            resultado = subprocess.run(
                [binario_path, "discover:sadp"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )
            
            if resultado.returncode != 0:
                error_msg = resultado.stderr.strip() if resultado.stderr else "Código de salida no cero sin mensaje de error."
                self.error.emit(f"Error al ejecutar sadp (Código {resultado.returncode}):\n{error_msg}")
                self.finished.emit()
                return
            
            # Parsear la salida de forma robusta y tolerante a fallos
            dispositivos = []
            lineas = resultado.stdout.splitlines()
            
            for linea in lineas:
                linea_clean = linea.strip()
                # Ignorar líneas vacías, comentarios o cabeceras obvias
                if not linea_clean or linea_clean.startswith('#') or 'descubierto' in linea_clean.lower():
                    continue
                
                partes = linea_clean.split()
                if len(partes) < 6:
                    continue
                
                # Identificar dinámicamente cuál columna contiene la IP (por si hay o no una columna de índice al inicio)
                idx_ip = -1
                for i in range(min(3, len(partes))):
                    subpartes = partes[i].split('.')
                    if len(subpartes) == 4 and all(s.isdigit() for s in subpartes):
                        idx_ip = i
                        break
                
                if idx_ip == -1:
                    continue  # No se localizó una estructura de IP en los primeros campos, saltar línea
                
                # Si encontramos la IP, extraemos los datos de manera relativa desde su posición
                start_data = idx_ip
                if len(partes) - start_data >= 6:
                    try:
                        ip      = partes[start_data]
                        mac     = partes[start_data + 1]
                        tipo    = partes[start_data + 2]
                        estado  = partes[start_data + 3]
                        puerto  = partes[start_data + 4]
                        serial  = partes[start_data + 5]
                        # La versión puede contener espacios, unimos el residuo del split
                        version = " ".join(partes[start_data + 6:]) if len(partes) > start_data + 6 else 'N/A'
                        
                        dispositivos.append({
                            'ip': ip,
                            'mac': mac,
                            'tipo': tipo,
                            'estado': estado,
                            'puerto': puerto,
                            'serial': serial,
                            'version': version
                        })
                    except Exception as parse_err:
                        print(f"[DEBUG Parser] Error procesando línea: {linea_clean}. Detalle: {parse_err}")
                        pass
            
            self.devices.emit(dispositivos)
            self.finished.emit()
            
        except subprocess.TimeoutExpired:
            self.error.emit("Timeout: el escaneo tardó demasiado tiempo (límite de 30 segundos)")
            self.finished.emit()
        except Exception as e:
            self.error.emit(f"Error inesperado en el subproceso: {str(e)}")
            self.finished.emit()


class SADPGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SADP Tool para Linux - Hikvision")
        self.setGeometry(100, 100, 1100, 650)
        self.scan_thread = None
        self.settings = QSettings("sadp", "sadp-gui-v2")
        
        # --- Aplicar QSS Estilos Premium ---
        self.setStyleSheet("""
            QMainWindow {
                background-color: #FFFFFF;
            }
            QLabel {
                font-family: 'Segoe UI', 'Inter', 'Ubuntu', 'Arial', sans-serif;
                font-size: 12px;
                color: #374151;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 6px;
                color: #111827;
                font-family: 'Segoe UI', 'Inter', 'Ubuntu', sans-serif;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #0F83E6;
            }
            QLineEdit:disabled {
                background-color: #F3F4F6;
                color: #9CA3AF;
                border: 1px solid #E5E7EB;
            }
            QCheckBox {
                font-family: 'Segoe UI', 'Inter', 'Ubuntu', sans-serif;
                font-size: 12px;
                color: #374151;
                spacing: 5px;
            }
            QPushButton.btn-coral {
                background-color: #E58B8B;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                font-family: 'Segoe UI', 'Inter', 'Ubuntu', sans-serif;
                font-size: 12px;
            }
            QPushButton.btn-coral:hover {
                background-color: #DB7A7A;
            }
            QPushButton.btn-coral:pressed {
                background-color: #C66B6B;
            }
            QPushButton.btn-coral:disabled {
                background-color: #F3D8D8;
                color: #F9C0C0;
            }
            QPushButton.btn-outline {
                background-color: #FFFFFF;
                color: #374151;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 8px 16px;
                font-family: 'Segoe UI', 'Inter', 'Ubuntu', sans-serif;
                font-size: 12px;
            }
            QPushButton.btn-outline:hover {
                background-color: #F9FAFB;
                border-color: #9CA3AF;
            }
            QPushButton.btn-outline:pressed {
                background-color: #F3F4F6;
            }
            QPushButton.btn-outline:disabled {
                background-color: #FFFFFF;
                color: #D1D5DB;
                border-color: #E5E7EB;
            }
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                gridline-color: #F3F4F6;
                font-family: 'Segoe UI', 'Inter', 'Ubuntu', sans-serif;
                font-size: 12px;
                color: #111827;
            }
            QHeaderView::section {
                background-color: #47505A;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 11px;
                padding: 6px;
                border: 1px solid #3C444D;
            }
            QTableWidget::item:selected {
                background-color: #E0F2FE;
                color: #0369A1;
            }
            QProgressBar {
                border: 1px solid #E5E7EB;
                border-radius: 4px;
                text-align: center;
                background-color: #F3F4F6;
            }
            QProgressBar::chunk {
                background-color: #0F83E6;
                border-radius: 3px;
            }
        """)

        # Main Layout Horizontal (Lado Izquierdo = Tabla, Lado Derecho = Parámetros de Red)
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_h_layout = QHBoxLayout(self.main_widget)
        self.main_h_layout.setContentsMargins(15, 15, 15, 15)
        self.main_h_layout.setSpacing(15)

        # ==========================================
        # --- COLUMNA IZQUIERDA (Dashboard + Tabla) ---
        # ==========================================
        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(10)

        # 1. Barra de herramientas superior (Estilo SADP original)
        self.top_layout = QHBoxLayout()
        
        # Etiqueta destacada en azul
        self.lbl_count = QLabel("Total number of online devices: <b style='color:#0F83E6; font-size:16px;'>0</b>")
        self.top_layout.addWidget(self.lbl_count)
        
        self.top_layout.addStretch()

        # Botón Unbind (Coral, deshabilitado por defecto)
        self.btn_unbind = QPushButton("Unbind")
        self.btn_unbind.setProperty("class", "btn-coral")
        self.btn_unbind.setMinimumHeight(35)
        self.btn_unbind.setEnabled(False)
        self.btn_unbind.clicked.connect(self.desvincular_dispositivo)
        self.top_layout.addWidget(self.btn_unbind)

        # Botón Export (Coral, deshabilitado por defecto)
        self.btn_export = QPushButton("Export")
        self.btn_export.setProperty("class", "btn-coral")
        self.btn_export.setMinimumHeight(35)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.exportar_csv)
        self.top_layout.addWidget(self.btn_export)

        # Botón Refresh (Outline, siempre habilitado)
        self.btn_scan = QPushButton("Refresh")
        self.btn_scan.setProperty("class", "btn-outline")
        self.btn_scan.setMinimumHeight(35)
        self.btn_scan.clicked.connect(self.ejecutar_escaneo)
        self.top_layout.addWidget(self.btn_scan)

        # Entrada de Filtrado (Filter)
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter")
        self.txt_filter.setMaximumWidth(160)
        self.txt_filter.setMinimumHeight(30)
        self.txt_filter.textChanged.connect(self.filtrar_tabla)
        self.top_layout.addWidget(self.txt_filter)

        # Botón Toggle Panel (Outline, para colapsar/desplegar el panel)
        self.btn_toggle_panel = QPushButton("✏️ Modificar Red")
        self.btn_toggle_panel.setProperty("class", "btn-outline")
        self.btn_toggle_panel.setMinimumHeight(35)
        self.btn_toggle_panel.clicked.connect(self.toggle_panel)
        self.top_layout.addWidget(self.btn_toggle_panel)

        self.left_layout.addLayout(self.top_layout)

        # 2. Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(0)  # Modo indeterminado
        self.progress_bar.setVisible(False)
        self.left_layout.addWidget(self.progress_bar)

        # 3. Etiqueta de estado
        self.status_label = QLabel("Presiona 'Refresh' para escanear la red")
        self.left_layout.addWidget(self.status_label)

        # 4. Tabla de dispositivos (8 columnas incluyendo el checkbox)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(8)
        self.tabla.setHorizontalHeaderLabels([
            "", 
            "Dirección IP", 
            "Dirección MAC", 
            "Tipo de Dispositivo", 
            "Estado", 
            "Puerto", 
            "Número de Serie",
            "Versión"
        ])
        
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.tabla.setColumnWidth(0, 35)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        
        self.tabla.setSelectionBehavior(self.tabla.SelectionBehavior.SelectRows)
        self.tabla.cellClicked.connect(self.seleccionar_fila)
        self.tabla.cellDoubleClicked.connect(self.doble_clic_celda)
        
        # Restaurar estado del encabezado si existe
        try:
            state = self.settings.value("headerStateV2")
            if state is not None:
                header.restoreState(state)
        except Exception:
            pass

        # Restaurar columna/orden de ordenación
        try:
            sort_col = self.settings.value("sortColumnV2")
            sort_order = self.settings.value("sortOrderV2")
            if sort_col is not None:
                sort_col = int(sort_col)
                sort_order = int(sort_order) if sort_order is not None else int(Qt.SortOrder.AscendingOrder)
                self.tabla.sortItems(sort_col, Qt.SortOrder(sort_order))
        except Exception:
            pass

        header.sectionMoved.connect(self.save_header_state)
        header.sectionResized.connect(self.save_header_state)
        header.sortIndicatorChanged.connect(self.save_sort_indicator)
        self.tabla.setSortingEnabled(True)
        self.left_layout.addWidget(self.tabla)

        # ==========================================
        # --- COLUMNA DERECHA (Panel Modificar - Desplegable) ---
        # ==========================================
        self.panel_modificar = QFrame()
        self.panel_modificar.setFrameShape(QFrame.Shape.StyledPanel)
        self.panel_modificar.setObjectName("PanelModificar")
        self.panel_modificar.setStyleSheet("""
            #PanelModificar {
                background-color: #F9FAFB;
                border-left: 1px solid #E5E7EB;
                border-radius: 4px;
            }
        """)
        
        self.right_layout = QVBoxLayout(self.panel_modificar)
        self.right_layout.setContentsMargins(10, 10, 10, 10)
        self.right_layout.setSpacing(10)

        # Cabecera del Panel (Título + Botón Cerrar)
        panel_header = QHBoxLayout()
        lbl_panel_title = QLabel("Modify Network Parameters")
        lbl_panel_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #111827;")
        panel_header.addWidget(lbl_panel_title)
        
        panel_header.addStretch()
        
        btn_close_panel = QPushButton("✕")
        btn_close_panel.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 14px;
                color: #9CA3AF;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #EF4444;
            }
        """)
        btn_close_panel.clicked.connect(self.panel_modificar.hide)
        btn_close_panel.clicked.connect(lambda: self.btn_toggle_panel.setText("✏️ Modificar Red"))
        panel_header.addWidget(btn_close_panel)
        
        self.right_layout.addLayout(panel_header)

        # Scroll Area para que todos los campos entren cómodamente
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("background-color: transparent;")
        
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: transparent;")
        self.scroll_layout = QVBoxLayout(scroll_widget)
        self.scroll_layout.setContentsMargins(0, 5, 0, 5)
        self.scroll_layout.setSpacing(10)

        # Checkboxes (DHCP / Hik-Connect)
        self.chk_dhcp = QCheckBox("Enable DHCP")
        self.chk_dhcp.setEnabled(False)
        self.chk_dhcp.stateChanged.connect(self.toggle_dhcp_fields)
        self.scroll_layout.addWidget(self.chk_dhcp)
        
        self.chk_hik = QCheckBox("Enable Hik-Connect")
        self.chk_hik.setEnabled(False)
        self.scroll_layout.addWidget(self.chk_hik)

        # Campos de texto individuales
        self.scroll_layout.addWidget(QLabel("Device Serial No.:"))
        self.txt_serial = QLineEdit()
        self.txt_serial.setReadOnly(True)
        self.txt_serial.setToolTip("El número de serie es de sólo lectura")
        self.scroll_layout.addWidget(self.txt_serial)

        self.scroll_layout.addWidget(QLabel("IP Address:"))
        self.txt_ip = QLineEdit()
        self.txt_ip.setEnabled(False)
        self.scroll_layout.addWidget(self.txt_ip)

        self.scroll_layout.addWidget(QLabel("Port:"))
        self.txt_port = QLineEdit()
        self.txt_port.setEnabled(False)
        self.scroll_layout.addWidget(self.txt_port)

        self.scroll_layout.addWidget(QLabel("Enhanced SDK Service Port:"))
        self.txt_sdk_port = QLineEdit()
        self.txt_sdk_port.setEnabled(False)
        self.scroll_layout.addWidget(self.txt_sdk_port)

        self.scroll_layout.addWidget(QLabel("Subnet Mask:"))
        self.txt_subnet = QLineEdit()
        self.txt_subnet.setEnabled(False)
        self.scroll_layout.addWidget(self.txt_subnet)

        self.scroll_layout.addWidget(QLabel("Gateway:"))
        self.txt_gateway = QLineEdit()
        self.txt_gateway.setEnabled(False)
        self.scroll_layout.addWidget(self.txt_gateway)

        self.scroll_layout.addWidget(QLabel("IPv6 Address:"))
        self.txt_ipv6 = QLineEdit()
        self.txt_ipv6.setEnabled(False)
        self.scroll_layout.addWidget(self.txt_ipv6)

        self.scroll_layout.addWidget(QLabel("IPv6 Gateway:"))
        self.txt_ipv6_gw = QLineEdit()
        self.txt_ipv6_gw.setEnabled(False)
        self.scroll_layout.addWidget(self.txt_ipv6_gw)

        self.scroll_layout.addWidget(QLabel("IPv6 Prefix Length:"))
        self.txt_ipv6_prefix = QLineEdit()
        self.txt_ipv6_prefix.setEnabled(False)
        self.scroll_layout.addWidget(self.txt_ipv6_prefix)

        self.scroll_layout.addWidget(QLabel("HTTP Port:"))
        self.txt_http_port = QLineEdit()
        self.txt_http_port.setEnabled(False)
        self.scroll_layout.addWidget(self.txt_http_port)

        # Línea divisoria para verificación de seguridad
        linea = QFrame()
        linea.setFrameShape(QFrame.Shape.HLine)
        linea.setFrameShadow(QFrame.Shadow.Sunken)
        linea.setStyleSheet("color: #E5E7EB;")
        self.scroll_layout.addWidget(linea)

        # Sección de Seguridad
        lbl_sec = QLabel("Security Verification")
        lbl_sec.setStyleSheet("font-weight: bold; color: #4B5563; margin-top: 5px;")
        self.scroll_layout.addWidget(lbl_sec)

        self.scroll_layout.addWidget(QLabel("Administrator Password:"))
        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setPlaceholderText("Enter admin password")
        self.txt_password.setEnabled(False)
        self.scroll_layout.addWidget(self.txt_password)

        # Botón Modificar
        self.btn_modify = QPushButton("Modify")
        self.btn_modify.setProperty("class", "btn-coral")
        self.btn_modify.setMinimumHeight(35)
        self.btn_modify.setEnabled(False)
        self.btn_modify.clicked.connect(self.ejecutar_modificacion)
        self.scroll_layout.addWidget(self.btn_modify)

        # Forgot Password Link
        lbl_forgot = QLabel('<a href="#forgot" style="color: #0F83E6; text-decoration: none; font-weight: 500;">Forgot Password</a>')
        lbl_forgot.setOpenExternalLinks(False)
        lbl_forgot.linkActivated.connect(self.recuperar_contrasena)
        lbl_forgot.setStyleSheet("margin-top: 5px;")
        self.scroll_layout.addWidget(lbl_forgot)

        scroll_area.setWidget(scroll_widget)
        self.right_layout.addWidget(scroll_area)

        # Agregar ambas columnas al layout horizontal
        self.main_h_layout.addWidget(self.left_widget, stretch=7)
        self.main_h_layout.addWidget(self.panel_modificar, stretch=3)

        # Ocultar panel lateral por defecto (requerido por el usuario)
        self.panel_modificar.hide()

        # Dispositivos en caché
        self.dispositivos = []

    def toggle_panel(self):
        """Muestra u oculta el panel lateral de modificación de red"""
        if self.panel_modificar.isVisible():
            self.panel_modificar.hide()
            self.btn_toggle_panel.setText("✏️ Modificar Red")
        else:
            self.panel_modificar.show()
            self.btn_toggle_panel.setText("✏️ Ocultar Panel")

    def toggle_dhcp_fields(self, state):
        """Habilita o deshabilita los campos de IP si DHCP está activo"""
        is_dhcp = (state == Qt.CheckState.Checked.value)
        # Si DHCP está activado, los campos de IP se autodefinen por la red, por ende se desactivan
        self.txt_ip.setDisabled(is_dhcp)
        self.txt_subnet.setDisabled(is_dhcp)
        self.txt_gateway.setDisabled(is_dhcp)

    def ejecutar_escaneo(self):
        """Inicia el escaneo en un thread aparte"""
        if self.scan_thread and self.scan_thread.isRunning():
            QMessageBox.warning(self, "Escaneo en curso", "Ya hay un escaneo en progreso")
            return
        
        self.tabla.setRowCount(0)
        self.dispositivos = []
        self.btn_scan.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_unbind.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Escaneando dispositivos... por favor espera")
        self.lbl_count.setText("Total number of online devices: <b style='color:#0F83E6; font-size:16px;'>0</b>")
        
        # Limpiar formulario
        self.txt_serial.clear()
        self.txt_ip.clear()
        self.txt_port.clear()
        self.txt_sdk_port.clear()
        self.txt_subnet.clear()
        self.txt_gateway.clear()
        self.txt_ipv6.clear()
        self.txt_ipv6_gw.clear()
        self.txt_ipv6_prefix.clear()
        self.txt_http_port.clear()
        self.txt_password.clear()
        self.chk_dhcp.setChecked(False)
        self.chk_hik.setChecked(False)
        
        # Deshabilitar controles del panel
        self.txt_ip.setEnabled(False)
        self.txt_port.setEnabled(False)
        self.txt_sdk_port.setEnabled(False)
        self.txt_subnet.setEnabled(False)
        self.txt_gateway.setEnabled(False)
        self.txt_http_port.setEnabled(False)
        self.txt_ipv6.setEnabled(False)
        self.txt_ipv6_gw.setEnabled(False)
        self.txt_ipv6_prefix.setEnabled(False)
        self.chk_dhcp.setEnabled(False)
        self.chk_hik.setEnabled(False)
        self.txt_password.setEnabled(False)
        self.btn_modify.setEnabled(False)
        
        self.scan_thread = ScanThread()
        self.scan_thread.devices.connect(self.mostrar_dispositivos)
        self.scan_thread.error.connect(self.mostrar_error)
        self.scan_thread.finished.connect(self.escaneo_finalizado)
        self.scan_thread.start()

    def mostrar_dispositivos(self, dispositivos):
        """Muestra los dispositivos en la tabla"""
        self.dispositivos = dispositivos
        self.lbl_count.setText(f"Total number of online devices: <b style='color:#0F83E6; font-size:16px;'>{len(dispositivos)}</b>")
        
        if not dispositivos:
            self.status_label.setText("⚠️ No se encontraron dispositivos Hikvision en la red")
            return
        
        # Desactivar ordenación mientras se insertan filas para evitar reordenados intermedios
        self.tabla.setSortingEnabled(False)
        for idx, disp in enumerate(dispositivos):
            row_position = self.tabla.rowCount()
            self.tabla.insertRow(row_position)
            
            # Checkbox en la columna 0 (SADP original style)
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            self.tabla.setItem(row_position, 0, chk_item)

            # IP (columna 1)
            ip_text = disp.get('ip', '')
            try:
                ip_key = tuple(int(x) for x in ip_text.split('.') if x != '')
            except Exception:
                ip_key = ip_text
            self.tabla.setItem(row_position, 1, SortableItem(ip_text, sort_key=ip_key))

            # MAC (columna 2)
            mac_text = disp.get('mac', '')
            mac_key = mac_text.replace(':', '').replace('-', '').lower()
            self.tabla.setItem(row_position, 2, SortableItem(mac_text, sort_key=mac_key))

            # Tipo (columna 3)
            tipo_raw = disp.get('tipo', '')
            serial_raw = disp.get('serial', '')
            tipo_text = traducir_tipo_dispositivo(tipo_raw, serial_raw)
            self.tabla.setItem(row_position, 3, SortableItem(tipo_text, sort_key=tipo_text))

            # Estado (columna 4)
            estado_text = disp.get('estado', '')
            self.tabla.setItem(row_position, 4, SortableItem(estado_text, sort_key=estado_text))

            # Puerto (columna 5)
            puerto_text = disp.get('puerto', '')
            try:
                puerto_key = int(puerto_text)
            except Exception:
                puerto_key = puerto_text
            self.tabla.setItem(row_position, 5, SortableItem(puerto_text, sort_key=puerto_key))

            # Serial (columna 6)
            serial_text = disp.get('serial', '')
            self.tabla.setItem(row_position, 6, SortableItem(serial_text, sort_key=serial_text))

            # Version (columna 7)
            version_text = disp.get('version', '')
            self.tabla.setItem(row_position, 7, SortableItem(version_text, sort_key=version_text))
        
        # Volver a activar ordenación después de insertar todas las filas
        self.tabla.setSortingEnabled(True)
        self.status_label.setText(f"✅ Se encontraron {len(dispositivos)} dispositivo(s)")

    def save_header_state(self, *args):
        try:
            header = self.tabla.horizontalHeader()
            state = header.saveState()
            self.settings.setValue("headerStateV2", state)
        except Exception:
            pass

    def save_sort_indicator(self, index: int, order: Qt.SortOrder):
        try:
            self.settings.setValue("sortColumnV2", int(index))
            self.settings.setValue("sortOrderV2", int(order))
        except Exception:
            pass

    def closeEvent(self, event):
        # Guardar estado al cerrar
        try:
            self.save_header_state()
        except Exception:
            pass
        super().closeEvent(event)

    def mostrar_error(self, mensaje):
        """Muestra un error"""
        QMessageBox.critical(self, "Error", f"Error en el escaneo:\n\n{mensaje}")
        self.status_label.setText("❌ Error durante el escaneo")

    def escaneo_finalizado(self):
        """Llamado cuando el escaneo termina"""
        self.btn_scan.setEnabled(True)
        if self.dispositivos:
            self.btn_export.setEnabled(True)
            self.btn_unbind.setEnabled(True)
        self.progress_bar.setVisible(False)

    def seleccionar_fila(self, row, column):
        """Selecciona una fila, marca su checkbox y rellena el panel lateral de modificación"""
        # Desactivar señales temporalmente para evitar loops
        self.tabla.blockSignals(True)
        try:
            # Desmarcar todos los checkboxes
            for r in range(self.tabla.rowCount()):
                item = self.tabla.item(r, 0)
                if item:
                    item.setCheckState(Qt.CheckState.Unchecked)
            # Marcar the checkbox del seleccionado
            curr_item = self.tabla.item(row, 0)
            if curr_item:
                curr_item.setCheckState(Qt.CheckState.Checked)
        finally:
            self.tabla.blockSignals(False)

        # Cargar datos desde la tabla
        ip = self.tabla.item(row, 1).text() if self.tabla.item(row, 1) else ""
        mac = self.tabla.item(row, 2).text() if self.tabla.item(row, 2) else ""
        tipo = self.tabla.item(row, 3).text() if self.tabla.item(row, 3) else ""
        estado = self.tabla.item(row, 4).text() if self.tabla.item(row, 4) else ""
        puerto = self.tabla.item(row, 5).text() if self.tabla.item(row, 5) else ""
        serial = self.tabla.item(row, 6).text() if self.tabla.item(row, 6) else ""
        version = self.tabla.item(row, 7).text() if self.tabla.item(row, 7) else ""

        # Poblar formulario lateral
        self.txt_serial.setText(serial)
        self.txt_ip.setText(ip)
        self.txt_port.setText(puerto)
        self.txt_sdk_port.setText("8000")  # Default SDK port
        self.txt_subnet.setText("255.255.255.0")
        
        # Inteligencia local: inferir puerta de enlace
        parts = ip.split('.')
        if len(parts) == 4:
            self.txt_gateway.setText(f"{parts[0]}.{parts[1]}.{parts[2]}.1")
        else:
            self.txt_gateway.setText("")
        
        self.txt_http_port.setText("80")
        self.txt_ipv6.setText("")
        self.txt_ipv6_gw.setText("")
        self.txt_ipv6_prefix.setText("64")
        self.txt_password.clear()
        
        # Habilitar controles del formulario
        self.txt_ip.setEnabled(True)
        self.txt_port.setEnabled(True)
        self.txt_sdk_port.setEnabled(True)
        self.txt_subnet.setEnabled(True)
        self.txt_gateway.setEnabled(True)
        self.txt_http_port.setEnabled(True)
        self.txt_ipv6.setEnabled(True)
        self.txt_ipv6_gw.setEnabled(True)
        self.txt_ipv6_prefix.setEnabled(True)
        self.chk_dhcp.setEnabled(True)
        self.chk_hik.setEnabled(True)
        self.txt_password.setEnabled(True)
        self.btn_modify.setEnabled(True)
        self.btn_unbind.setEnabled(True)

    def doble_clic_celda(self, row, column):
        """Maneja el doble clic en la IP (columna 1) para abrir en el navegador"""
        if column == 1:  # Columna de IP
            item_ip = self.tabla.item(row, column)
            if item_ip:
                ip = item_ip.text()
                url = f"http://{ip}"
                
                respuesta = QMessageBox.question(
                    self,
                    "Abrir en navegador",
                    f"¿Deseas abrir la interfaz web de {ip}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if respuesta == QMessageBox.StandardButton.Yes:
                    webbrowser.open(url)
                    self.status_label.setText(f"Abriendo {url} en el navegador...")

    def filtrar_tabla(self, texto):
        """Filtra en tiempo real los dispositivos mostrados según el texto de búsqueda"""
        texto = texto.lower().strip()
        for row in range(self.tabla.rowCount()):
            mostrar_fila = False
            if not texto:
                mostrar_fila = True
            else:
                # Comprobar si coincide con alguna columna (saltándonos la del checkbox)
                for col in range(1, self.tabla.columnCount()):
                    item = self.tabla.item(row, col)
                    if item and texto in item.text().lower():
                        mostrar_fila = True
                        break
            self.tabla.setRowHidden(row, not mostrar_fila)

    def ejecutar_modificacion(self):
        """Modulariza el procesamiento local de cambios de parámetros de red"""
        serial = self.txt_serial.text()
        ip = self.txt_ip.text()
        password = self.txt_password.text()

        if not serial:
            QMessageBox.warning(self, "Seleccionar Dispositivo", "Por favor, selecciona primero un dispositivo de la lista.")
            return

        if not password:
            QMessageBox.warning(self, "Contraseña Requerida", "Por favor, introduce la contraseña de administrador del dispositivo para aplicar los cambios.")
            return

        # Simular empaquetado XML y preparar modularmente el canal
        # En el futuro, aquí se llamará al comando de Go: `sadp modify:network --ip ... --pass ...`
        QMessageBox.information(
            self,
            "Modificación Local (Entorno Preparado)",
            f"<b>Canal de Red Modular Preparado</b><br><br>"
            f"Dispositivo Serial: <font color='#0F83E6'><b>{serial}</b></font><br>"
            f"Parámetros a aplicar:<br>"
            f"• Dirección IP: {ip}<br>"
            f"• Máscara de subred: {self.txt_subnet.text()}<br>"
            f"• Puerta de enlace: {self.txt_gateway.text()}<br>"
            f"• Puerto SDK: {self.txt_sdk_port.text()}<br>"
            f"• Puerto HTTP: {self.txt_http_port.text()}<br>"
            f"• DHCP: {'Habilitado' if self.chk_dhcp.isChecked() else 'Deshabilitado'}<br><br>"
            f"⚠️ <i>Nota: La aplicación de tramas UDP firmadas requiere extender la CLI 'hikvision-tooling' (sadp-linux-amd64) localmente en futuras versiones de producción.</i>"
        )

    def desvincular_dispositivo(self):
        """Modulariza la desvinculación local del dispositivo de la red"""
        serial = self.txt_serial.text()
        if not serial:
            QMessageBox.warning(self, "Seleccionar Dispositivo", "Por favor, selecciona primero un dispositivo de la lista.")
            return

        # Mensaje informativo elegante enfocado en local
        QMessageBox.information(
            self,
            "Desvincular Dispositivo (Unbind)",
            f"<b>Desvinculación Modular Preparada</b><br><br>"
            f"Has solicitado desvincular el dispositivo:<br>"
            f"• Número de Serie: {serial}<br><br>"
            f"⚠️ <i>Esta característica requiere la ejecución de tramas de control locales en el protocolo SADP y ha sido modularizada para su habilitación futura a nivel de red local.</i>"
        )

    def recuperar_contrasena(self, link=None):
        """Explica el flujo local offline para recuperar contraseña"""
        QMessageBox.information(
            self,
            "Restaurar Contraseña (Forgot Password)",
            f"<b>Restablecimiento de Contraseña Local Offline</b><br><br>"
            f"Para restaurar la contraseña de fábrica:<br>"
            f"1. Genera un archivo XML de solicitud de restablecimiento (.xml) desde la cámara física o su utilidad.<br>"
            f"2. Contacta al soporte oficial de Hikvision o utiliza la aplicación Hik-Partner Pro para obtener un código de desbloqueo.<br>"
            f"3. Importa el archivo XML de respuesta recibido para actualizar la contraseña del administrador.<br><br>"
            f"<i>Esta herramienta local modularizará el soporte offline en próximas compilaciones.</i>"
        )

    def exportar_csv(self):
        """Exporta los dispositivos a un archivo CSV"""
        if not self.dispositivos:
            QMessageBox.warning(self, "No hay datos", "No hay dispositivos para exportar")
            return
        
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar lista de dispositivos Hikvision",
                "dispositivos_hikvision.csv",
                "Archivos CSV (*.csv);;Todos los archivos (*)"
            )
            if not filename:
                return

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['ip', 'mac', 'tipo', 'estado', 'puerto', 'serial', 'version'])
                writer.writeheader()
                writer.writerows(self.dispositivos)
            
            QMessageBox.information(self, "Éxito", f"Datos exportados exitosamente a:\n'{filename}'")
            self.status_label.setText(f"Exportado: {os.path.basename(filename)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al exportar: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = SADPGui()
    ventana.show()
    sys.exit(app.exec())