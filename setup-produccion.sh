#!/bin/bash

# SADP GUI para Linux - Script de Instalación de Producción (Versión Definitiva)
# Uso: bash setup-produccion.sh

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║    SADP GUI para Linux - Instalación de Producción        ║"
echo "║    Descubridor de Cámaras Hikvision                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if [[ "$EUID" -eq 0 ]]; then
    echo "❌ ERROR: Este script NO debe ejecutarse con sudo"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/bin/sadp"
mkdir -p "$INSTALL_DIR"

echo "📋 Sistema: $(grep PRETTY_NAME /etc/os-release | cut -d'"' -f2)"
echo "📁 Instalación en: $INSTALL_DIR"
echo ""

# FUNCIÓN: Configurar firewall base
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
configure_ufw() {
    echo "🔐 Configurando firewall base..."
    if command -v ufw &> /dev/null; then
        sudo ufw allow 37020/udp 2>/dev/null
        sudo ufw allow out proto udp to 224.0.0.0/4 2>/dev/null
        if ! sudo ufw status | grep -q "Status: active"; then
            sudo ufw --force enable 2>/dev/null
        fi
    fi
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Paso 1: Instalación de dependencias
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Paso 1: Instalando dependencias..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sudo apt update >/dev/null 2>&1 || true
sudo apt install -y python3 python3-pyqt6 golang-go git ufw libcap2-bin >/dev/null 2>&1
GO_VERSION=$(go version 2>/dev/null | grep -oP 'go\K[0-9]+\.[0-9]+' | head -1)
echo "✅ Dependencias instaladas (Go $GO_VERSION)"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Paso 2: Compilar binario SADP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Paso 2: Compilando binario SADP..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TEMP_BUILD="/tmp/sadp-build-$$"
mkdir -p "$TEMP_BUILD"
cd "$TEMP_BUILD"
git clone --depth 1 https://github.com/cameronnewman/hikvision-tooling.git >/dev/null 2>&1
cd hikvision-tooling

BUILD_OUTPUT=$(CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o sadp-linux-amd64 ./cmd/sadp 2>&1) || true

if [[ -f "sadp-linux-amd64" ]]; then
    cp sadp-linux-amd64 "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/sadp-linux-amd64"
    echo "✅ Binario compilado exitosamente"
else
    echo "❌ Error compilando el binario"
    rm -rf "$TEMP_BUILD"
    exit 1
fi
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Paso 3: Copiar GUI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Paso 3: Instalando interfaz gráfica..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ -f "$SCRIPT_DIR/gui_sadp.py" ]]; then
    cp "$SCRIPT_DIR/gui_sadp.py" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/gui_sadp.py"
    echo "✅ GUI instalada"
else
    echo "❌ No se pudo encontrar gui_sadp.py"
    exit 1
fi
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Paso 4: Configurar permisos silenciosos
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Paso 4: Configurando permisos de red automatizados..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
SUDOERS_FILE="/etc/sudoers.d/sadp-gui-routing"
echo "ALL ALL=(root) NOPASSWD: /usr/sbin/ip route add 239.255.255.250/32 *, /usr/sbin/ip route change 239.255.255.250/32 *, /bin/ip route add 239.255.255.250/32 *, /bin/ip route change 239.255.255.250/32 *, /usr/sbin/ufw allow in on *, /sbin/sysctl *, /usr/sbin/sysctl *" | sudo tee "$SUDOERS_FILE" >/dev/null
sudo chmod 0440 "$SUDOERS_FILE"
echo "✅ Permisos silenciosos configurados"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Paso 5: Crear Lanzador Inteligente Multi-Interfaz
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Paso 5: Creando lanzador inteligente multi-interfaz..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
LAUNCHER="$HOME/.local/bin/sadp-gui"

cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/bin/bash
# 1. Configurar rp_filter=2 (modo laxo) para permitir recibir respuestas UDP de subredes distintas
sudo sysctl -w net.ipv4.conf.all.rp_filter=2 >/dev/null 2>&1 || true
sudo sysctl -w net.ipv4.conf.default.rp_filter=2 >/dev/null 2>&1 || true

# 2. Detectar TODAS las interfaces de red activas (Ethernet, WiFi, USB, VLANs, etc.)
IFACES=$(ip -o link show | awk -F': ' '$2 !~ /^lo/ && $3 ~ /state (UP|UNKNOWN)/ {print $2}' | cut -d'@' -f1)

# 3. Forzar ruta multicast y abrir firewall en CADA interfaz activa
for IFACE in $IFACES; do
    [ -z "$IFACE" ] && continue
    sudo ip route add 239.255.255.250/32 dev "$IFACE" 2>/dev/null || \
    sudo ip route change 239.255.255.250/32 dev "$IFACE" 2>/dev/null || true
    
    sudo ufw allow in on "$IFACE" to any port 37020 proto udp 2>/dev/null || true
done

# 4. Iniciar GUI
cd "$HOME/.local/bin/sadp"
python3 gui_sadp.py
LAUNCHER_EOF

chmod +x "$LAUNCHER"
echo "✅ Lanzador inteligente creado"

APPLICATIONS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPLICATIONS_DIR"
DESKTOP_FILE="$APPLICATIONS_DIR/sadp-gui.desktop"
cat > "$DESKTOP_FILE" << DESKTOP_EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=SADP GUI
Comment=Descubrir cámaras Hikvision en la red local
Exec=$LAUNCHER
Terminal=false
Icon=network-workgroup
Categories=Network;Utility;
StartupNotify=true
DESKTOP_EOF
chmod +x "$DESKTOP_FILE"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Paso 6: Configurar firewall inicial y setcap
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
configure_ufw
if command -v setcap &> /dev/null; then
    sudo setcap cap_net_raw=ep "$INSTALL_DIR/sadp-linux-amd64" 2>/dev/null
fi

rm -rf "$TEMP_BUILD"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║            ✅ INSTALACIÓN COMPLETADA                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo "   El sistema está listo para producción. El firewall gestionará"
echo "   las interfaces automáticamente de forma silenciosa."