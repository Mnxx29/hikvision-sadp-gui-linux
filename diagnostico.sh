#!/bin/bash

# SADP GUI - Script de Diagnóstico Completo
# Ejecuta este script en el PC Ubuntu remoto para diagnosticar
# por qué no se encuentran dispositivos Hikvision.
# Uso: bash diagnostico.sh

echo "╔════════════════════════════════════════════════════════════╗"
echo "║       SADP GUI - Diagnóstico de Red Completo              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Fecha: $(date)"
echo "Usuario: $(whoami)"
echo "Sistema: $(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d'"' -f2 || uname -a)"
echo ""

ERRORS=0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. VERIFICAR BINARIO SADP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. VERIFICAR BINARIO SADP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BINARIO=""
RUTAS_POSIBLES=(
    "$HOME/.local/bin/sadp/sadp-linux-amd64"
    "$HOME/.local/bin/sadp-linux-amd64"
    "/usr/local/bin/sadp-linux-amd64"
    "./sadp-linux-amd64"
)

for ruta in "${RUTAS_POSIBLES[@]}"; do
    if [[ -f "$ruta" ]]; then
        BINARIO="$ruta"
        echo "✅ Binario encontrado en: $ruta"
        break
    fi
done

if [[ -z "$BINARIO" ]]; then
    BINARIO_WHICH=$(which sadp-linux-amd64 2>/dev/null || which sadp 2>/dev/null)
    if [[ -n "$BINARIO_WHICH" ]]; then
        BINARIO="$BINARIO_WHICH"
        echo "✅ Binario encontrado en PATH: $BINARIO"
    else
        echo "❌ ERROR: No se encontró el binario sadp-linux-amd64 en ninguna ruta conocida"
        ERRORS=$((ERRORS + 1))
    fi
fi

if [[ -n "$BINARIO" ]]; then
    echo "   Permisos: $(ls -la "$BINARIO")"
    
    if [[ -x "$BINARIO" ]]; then
        echo "   ✅ El binario tiene permisos de ejecución"
    else
        echo "   ❌ El binario NO tiene permisos de ejecución"
        ERRORS=$((ERRORS + 1))
    fi
    
    # Verificar capabilities (cap_net_raw)
    if command -v getcap &> /dev/null; then
        CAPS=$(getcap "$BINARIO" 2>/dev/null)
        if echo "$CAPS" | grep -qi "cap_net_raw"; then
            echo "   ✅ Capability cap_net_raw asignada: $CAPS"
        else
            echo "   ❌ FALTA cap_net_raw. El binario NO puede abrir sockets raw sin root."
            echo "      Solución: sudo setcap cap_net_raw=ep \"$BINARIO\""
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "   ⚠️  getcap no disponible. Instala libcap2-bin: sudo apt install libcap2-bin"
        ERRORS=$((ERRORS + 1))
    fi

    FILE_INFO=$(file "$BINARIO" 2>/dev/null || echo "N/A")
    echo "   Tipo de archivo: $FILE_INFO"
fi
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. INTERFACES DE RED
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. INTERFACES DE RED ACTIVAS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

IFACES=$(ip -o link show 2>/dev/null | awk -F': ' '$2 !~ /^lo/ && $3 ~ /state (UP|UNKNOWN)/ {print $2}' | cut -d'@' -f1)

if [[ -z "$IFACES" ]]; then
    echo "❌ ERROR: No se encontraron interfaces de red activas (UP)"
    echo "   Todas las interfaces:"
    ip -o link show 2>/dev/null || ifconfig 2>/dev/null
    ERRORS=$((ERRORS + 1))
else
    echo "Interfaces activas encontradas:"
    for iface in $IFACES; do
        echo ""
        echo "   ▸ Interfaz: $iface"
        IPS=$(ip -4 addr show dev "$iface" 2>/dev/null | grep -oP 'inet \K[\d./]+')
        if [[ -z "$IPS" ]]; then
            echo "     ⚠️  Sin dirección IPv4 asignada"
        else
            echo "     IPv4: $IPS"
        fi
        CARRIER=$(cat /sys/class/net/$iface/carrier 2>/dev/null || echo "?")
        OPERSTATE=$(cat /sys/class/net/$iface/operstate 2>/dev/null || echo "?")
        echo "     Estado operativo: $OPERSTATE | Carrier: $CARRIER"
    done
fi
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. FIREWALL (UFW / iptables)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. FIREWALL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v ufw &> /dev/null; then
    UFW_STATUS=$(sudo ufw status 2>/dev/null || echo "No se pudo verificar")
    echo "Estado UFW:"
    echo "$UFW_STATUS"
    
    if echo "$UFW_STATUS" | grep -q "37020"; then
        echo "✅ Puerto UDP 37020 permitido en UFW"
    else
        if echo "$UFW_STATUS" | grep -qi "inactive"; then
            echo "ℹ️  UFW está inactivo (no bloquea nada)"
        else
            echo "❌ Puerto UDP 37020 NO encontrado en las reglas UFW"
            echo "   Solución: sudo ufw allow 37020/udp"
            ERRORS=$((ERRORS + 1))
        fi
    fi
else
    echo "ℹ️  UFW no instalado"
fi

echo ""
echo "Reglas iptables relevantes (UDP 37020 y multicast):"
sudo iptables -L -n 2>/dev/null | grep -iE "37020|239\.255|multicast|DROP.*udp" || echo "   No se encontraron reglas específicas"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. KERNEL rp_filter
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. KERNEL rp_filter (Reverse Path Filtering)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RP_ALL=$(sysctl -n net.ipv4.conf.all.rp_filter 2>/dev/null || echo "?")
RP_DEFAULT=$(sysctl -n net.ipv4.conf.default.rp_filter 2>/dev/null || echo "?")

echo "   net.ipv4.conf.all.rp_filter     = $RP_ALL (necesita ser 0 o 2)"
echo "   net.ipv4.conf.default.rp_filter = $RP_DEFAULT (necesita ser 0 o 2)"

if [[ "$RP_ALL" == "1" || "$RP_DEFAULT" == "1" ]]; then
    echo "   ⚠️  ADVERTENCIA: rp_filter=1 (modo estricto) puede bloquear respuestas SADP"
    echo "      Solución: sudo sysctl -w net.ipv4.conf.all.rp_filter=2"
fi

for iface in $IFACES; do
    RP_IFACE=$(sysctl -n net.ipv4.conf.$iface.rp_filter 2>/dev/null || echo "?")
    if [[ "$RP_IFACE" == "1" ]]; then
        echo "   ⚠️  net.ipv4.conf.$iface.rp_filter = $RP_IFACE (estricto)"
    else
        echo "   ✅ net.ipv4.conf.$iface.rp_filter = $RP_IFACE"
    fi
done
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. RUTA MULTICAST 239.255.255.250
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. RUTA MULTICAST SADP (239.255.255.250)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RUTA_MCAST=$(ip route show 239.255.255.250 2>/dev/null)
if [[ -n "$RUTA_MCAST" ]]; then
    echo "✅ Ruta multicast encontrada: $RUTA_MCAST"
else
    echo "⚠️  No hay ruta explícita para 239.255.255.250"
    echo "   El lanzador sadp-gui la crea automáticamente."
    echo "   Ruta multicast genérica:"
    ip route show | grep -i "224\|multicast" 2>/dev/null || echo "   (ninguna)"
fi
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. SUDOERS SADP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. SUDOERS SADP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ -f /etc/sudoers.d/sadp-gui-routing ]]; then
    echo "✅ Archivo sudoers SADP existe"
    sudo cat /etc/sudoers.d/sadp-gui-routing 2>/dev/null || echo "   (sin permisos para leerlo)"
else
    echo "⚠️  No existe /etc/sudoers.d/sadp-gui-routing"
    echo "   Necesario para configurar rutas multicast sin pedir contraseña."
fi
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. PRUEBA DIRECTA DEL BINARIO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7. PRUEBA DIRECTA DEL BINARIO (discover:sadp)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ -n "$BINARIO" && -x "$BINARIO" ]]; then
    echo "Ejecutando: $BINARIO discover:sadp --csv"
    echo "Esperando 15 segundos para recibir respuestas..."
    echo ""
    
    # Preparar red antes del test
    for iface in $IFACES; do
        sudo ip route add 239.255.255.250/32 dev "$iface" 2>/dev/null || \
        sudo ip route change 239.255.255.250/32 dev "$iface" 2>/dev/null || true
    done
    sudo sysctl -w net.ipv4.conf.all.rp_filter=2 >/dev/null 2>&1 || true
    
    OUTPUT=$(timeout 15 "$BINARIO" discover:sadp --csv 2>&1) || true
    EXIT_CODE=$?
    
    if [[ -n "$OUTPUT" ]]; then
        DEVICE_COUNT=$(echo "$OUTPUT" | grep -v "^$" | grep -v "IPv4Address" | wc -l)
        echo "Código de salida: $EXIT_CODE"
        echo "Dispositivos encontrados: $DEVICE_COUNT"
        echo ""
        echo "--- SALIDA COMPLETA ---"
        echo "$OUTPUT"
        echo "--- FIN SALIDA ---"
    else
        echo "⚠️  El binario no devolvió ninguna salida"
        echo "   Código de salida: $EXIT_CODE"
    fi
    
    echo ""
    echo "Probando sin --csv (formato tabla):"
    OUTPUT2=$(timeout 15 "$BINARIO" discover:sadp 2>&1) || true
    echo "Código de salida: $?"
    if [[ -n "$OUTPUT2" ]]; then
        echo "--- SALIDA ---"
        echo "$OUTPUT2"
        echo "--- FIN ---"
    else
        echo "⚠️  Sin salida"
    fi
else
    echo "⏩ Saltando prueba (binario no encontrado o no ejecutable)"
fi
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. DETECTAR TRÁFICO UDP 37020
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "8. DETECTAR TRÁFICO UDP 37020 (tcpdump)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v tcpdump &> /dev/null; then
    echo "Escuchando paquetes UDP en puerto 37020 durante 8 segundos..."
    echo "(Las cámaras Hikvision envían anuncios SADP periódicamente)"
    echo ""
    TCPDUMP_OUT=$(sudo timeout 8 tcpdump -i any -c 10 udp port 37020 -nn 2>&1) || true
    if echo "$TCPDUMP_OUT" | grep -q "37020"; then
        echo "✅ SE DETECTA tráfico SADP:"
        echo "$TCPDUMP_OUT"
    else
        echo "⚠️  NO se detectó tráfico SADP en 8 segundos"
        echo "   Posibles causas:"
        echo "   - Los equipos Hikvision no están en la misma VLAN/segmento L2"
        echo "   - Un switch managed bloquea multicast/broadcast"
        echo "   - Los dispositivos están apagados o sin red"
        echo "   Salida tcpdump:"
        echo "$TCPDUMP_OUT"
    fi
else
    echo "⚠️  tcpdump no instalado. Para instalar: sudo apt install tcpdump"
fi
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 9. LANZADOR sadp-gui
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "9. LANZADOR sadp-gui"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ -f "$HOME/.local/bin/sadp-gui" ]]; then
    echo "✅ El lanzador sadp-gui existe en ~/.local/bin/sadp-gui"
else
    echo "❌ El lanzador sadp-gui NO existe."
    echo "   ¿Se ejecutó setup-produccion.sh correctamente?"
    ERRORS=$((ERRORS + 1))
fi

echo ""
echo "⚠️  IMPORTANTE: Si ejecutaste directamente 'python3 gui_sadp.py'"
echo "   en lugar de 'sadp-gui', las rutas multicast y la configuración"
echo "   del kernel NO se aplican correctamente antes del escaneo."
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RESUMEN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    RESUMEN DE DIAGNÓSTICO                 ║"
echo "╚════════════════════════════════════════════════════════════╝"

if [[ $ERRORS -eq 0 ]]; then
    echo "✅ No se detectaron errores de configuración evidentes."
    echo ""
    echo "Si aún no se encuentran dispositivos, el problema podría ser:"
    echo "  1. Los equipos Hikvision están en una VLAN distinta (switch gestionado)"
    echo "  2. El PC está en WiFi pero las cámaras en Ethernet (red diferente)"
    echo "  3. Un router/switch bloquea tráfico multicast entre segmentos"
    echo "  4. Los dispositivos están apagados o sin conexión de red"
else
    echo "❌ Se encontraron $ERRORS problema(s) de configuración."
    echo ""
    echo "Soluciones rápidas:"
    echo "  1. Reinstalar: bash setup-produccion.sh"
    echo "  2. O aplicar manualmente:"
    echo "     sudo setcap cap_net_raw=ep ~/.local/bin/sadp/sadp-linux-amd64"
    echo "     sudo ufw allow 37020/udp"
    echo "     sudo sysctl -w net.ipv4.conf.all.rp_filter=2"
fi
echo ""
echo "📋 Copia y pega toda esta salida para compartir el diagnóstico."
