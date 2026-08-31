#!/usr/bin/env python3
"""
sadp_discover.py - Descubrimiento nativo de dispositivos Hikvision via protocolo SADP (Python puro).

Reemplaza la dependencia del binario Go (sadp-linux-amd64) para el descubrimiento.
El binario Go sigue siendo necesario para las funciones 'send' (modificar red / unbind).

Protocolo SADP:
  - UDP Multicast a 239.255.255.250:37020
  - Sonda XML tipo <Probe><Types>inquiry</Types></Probe>
  - Respuesta XML tipo <ProbeMatch> con datos del dispositivo

Uso independiente:
    python3 sadp_discover.py [--timeout 10] [--debug] [--csv] [--raw]
"""

import socket
import struct
import uuid
import xml.etree.ElementTree as ET
import time
import subprocess
import sys
import select

SADP_MULTICAST = "239.255.255.250"
SADP_PORT = 37020


def build_probe():
    """Construye el paquete XML de sondeo SADP (inquiry)."""
    probe_uuid = str(uuid.uuid4())
    return (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<Probe><Uuid>{probe_uuid}</Uuid><Types>inquiry</Types></Probe>'
    ).encode('utf-8')


def get_interface_ips():
    """Obtiene todas las IPs IPv4 de interfaces activas (no loopback)."""
    ips = []
    try:
        if sys.platform.startswith('linux'):
            res = subprocess.run(
                ['ip', '-4', '-o', 'addr', 'show', 'scope', 'global'],
                capture_output=True, text=True, timeout=5
            )
            for line in res.stdout.splitlines():
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == 'inet' and i + 1 < len(parts):
                        ip = parts[i + 1].split('/')[0]
                        if ip != '127.0.0.1':
                            ips.append(ip)
        else:
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = info[4][0]
                if ip != '127.0.0.1' and ip not in ips:
                    ips.append(ip)
    except Exception:
        pass
    return ips or ['0.0.0.0']


def get_broadcast_addrs():
    """Obtiene las direcciones de broadcast de cada interfaz activa."""
    addrs = ['255.255.255.255']
    try:
        if sys.platform.startswith('linux'):
            res = subprocess.run(
                ['ip', '-4', '-o', 'addr', 'show', 'scope', 'global'],
                capture_output=True, text=True, timeout=5
            )
            for line in res.stdout.splitlines():
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == 'brd' and i + 1 < len(parts):
                        b = parts[i + 1]
                        if b not in addrs:
                            addrs.append(b)
    except Exception:
        pass
    return addrs


def parse_response(data, addr, debug=False):
    """
    Parsea una respuesta SADP a un diccionario de dispositivo.
    
    Las respuestas pueden ser XML puro o tener una cabecera binaria antes del XML.
    """
    if debug:
        print(f"  [PARSE] {len(data)} bytes de {addr[0]}:{addr[1]}")

    # Buscar inicio de XML en los datos (puede haber cabecera binaria)
    xml_data = None
    for marker in [b'<?xml', b'<ProbeMatch', b'<Probe']:
        idx = data.find(marker)
        if idx != -1:
            raw = data[idx:]
            raw = raw.rstrip(b'\x00')
            end = raw.rfind(b'>')
            if end != -1:
                xml_data = raw[:end + 1]
            else:
                xml_data = raw
            if debug and idx > 0:
                print(f"  [PARSE] Cabecera binaria de {idx} bytes detectada")
            break

    if xml_data is None:
        if debug:
            print(f"  [PARSE] No se encontró XML. Hex: {data[:64].hex()}")
        return None

    try:
        try:
            xml_str = xml_data.decode('utf-8')
        except UnicodeDecodeError:
            xml_str = xml_data.decode('latin-1')

        root = ET.fromstring(xml_str)

        def get(tag, default=''):
            """Busca un tag XML (case-insensitive)."""
            el = root.find(tag)
            if el is not None and el.text:
                return el.text.strip()
            tag_lower = tag.lower()
            for child in root:
                if child.tag.lower() == tag_lower:
                    return (child.text or '').strip()
            return default

        mac = get('MAC')
        if not mac:
            if debug:
                print(f"  [PARSE] Respuesta sin MAC, descartando")
            return None

        ip = get('IPv4Address') or addr[0]

        activated = get('Activated', 'true').lower()
        if activated in ('true', 'active', 'activado', '1'):
            estado = 'Active'
        elif activated in ('false', 'inactive', '0'):
            estado = 'Inactive'
        else:
            estado = activated

        device = {
            'ip': ip,
            'mac': mac,
            'tipo': get('DeviceType'),
            'estado': estado,
            'puerto': get('CommandPort') or get('Port', '8000'),
            'http_port': get('HttpPort', '80'),
            'serial': get('DeviceSN') or get('SerialNumber', ''),
            'version': get('SoftwareVersion', ''),
            'subnet': get('IPv4SubnetMask', '255.255.255.0'),
            'gateway': get('IPv4Gateway', ''),
            'dhcp': get('DHCP', 'false'),
        }

        if debug:
            print(f"  [PARSE] ✅ {ip} ({mac}) - {device['serial']}")

        return device

    except ET.ParseError as e:
        if debug:
            print(f"  [PARSE] Error XML: {e}")
            print(f"  [PARSE] Datos: {xml_data[:200]}")
        return None
    except Exception as e:
        if debug:
            print(f"  [PARSE] Error inesperado: {e}")
        return None


def discover(timeout=10, debug=False):
    """
    Descubre dispositivos Hikvision en la red local usando el protocolo SADP nativo.

    Envía sondas UDP multicast (239.255.255.250:37020) y broadcast,
    luego escucha las respuestas XML de los dispositivos.

    IMPORTANTE: Se enlaza al puerto 37020 (el mismo que permite el firewall UFW)
    para que las respuestas unicast de los dispositivos no sean bloqueadas.

    Args:
        timeout: Tiempo máximo de espera en segundos (default: 10).
        debug: Si True, imprime información de depuración.

    Returns:
        Lista de diccionarios, uno por cada dispositivo descubierto.
    """
    devices = {}  # Clave: MAC normalizada, para deduplicar

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # SO_REUSEPORT permite coexistir con otros procesos en el mismo puerto
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except (AttributeError, OSError):
        pass
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # Buffer grande para manejar respuestas reensambladas (post IP-fragmentation)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    except Exception:
        pass

    # TTL para multicast (4 saltos es suficiente para redes locales/VLANs)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)

    # Permitir recibir nuestro propio multicast
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

    # ── BIND AL PUERTO 37020 ──
    # Los dispositivos responden al puerto fuente de la sonda. Si usamos un
    # puerto aleatorio, el firewall (UFW) bloquea la respuesta porque solo
    # tiene abierto el 37020/udp. Al enlazar directamente al 37020,
    # tanto el envío como la recepción pasan por el puerto permitido.
    bound_port = SADP_PORT
    try:
        sock.bind(('', SADP_PORT))
    except OSError as e:
        # Si el puerto 37020 está ocupado, usar uno aleatorio e informar
        if debug:
            print(f"[SADP] No se pudo enlazar al puerto {SADP_PORT}: {e}")
            print(f"[SADP] ⚠️  Usando puerto aleatorio. Si el firewall bloquea respuestas,")
            print(f"[SADP]    ejecuta: sudo ufw allow from any port 37020 to any")
        sock.bind(('', 0))
        bound_port = sock.getsockname()[1]

    if debug:
        print(f"[SADP] Socket enlazado al puerto {bound_port}")

    # Unirse al grupo multicast en cada interfaz activa
    iface_ips = get_interface_ips()
    for ip in iface_ips:
        try:
            mreq = struct.pack("4s4s",
                               socket.inet_aton(SADP_MULTICAST),
                               socket.inet_aton(ip))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            if debug:
                print(f"[SADP] Multicast join en {ip}")
        except Exception as e:
            if debug:
                print(f"[SADP] No se pudo unir multicast en {ip}: {e}")

    # Construir y enviar sonda
    probe = build_probe()

    # Enviar sonda multicast desde CADA interfaz (no solo la default)
    for ip in iface_ips:
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                            socket.inet_aton(ip))
            sock.sendto(probe, (SADP_MULTICAST, SADP_PORT))
            if debug:
                print(f"[SADP] Sonda multicast enviada via {ip}")
        except Exception as e:
            if debug:
                print(f"[SADP] Fallo envío multicast via {ip}: {e}")

    # Enviar a direcciones broadcast (redundancia)
    for brd in get_broadcast_addrs():
        try:
            sock.sendto(probe, (brd, SADP_PORT))
            if debug:
                print(f"[SADP] Sonda broadcast enviada a {brd}:{SADP_PORT}")
        except Exception as e:
            if debug:
                print(f"[SADP] Fallo broadcast {brd}: {e}")

    # Escuchar respuestas
    end_time = time.time() + timeout
    resend_time = time.time() + 2.0
    resent = False

    while True:
        remaining = end_time - time.time()
        if remaining <= 0:
            break

        # Reenviar sonda a los ~2 segundos para mejorar detección
        if not resent and time.time() >= resend_time:
            try:
                probe2 = build_probe()
                sock.sendto(probe2, (SADP_MULTICAST, SADP_PORT))
                for brd in get_broadcast_addrs():
                    sock.sendto(probe2, (brd, SADP_PORT))
                resent = True
                if debug:
                    print("[SADP] Sonda reenviada")
            except Exception:
                pass

        ready, _, _ = select.select([sock], [], [], min(remaining, 0.5))
        if not ready:
            continue

        try:
            data, addr = sock.recvfrom(65535)
            device = parse_response(data, addr, debug=debug)
            if device and device.get('mac'):
                mac_key = device['mac'].lower().replace(':', '').replace('-', '')
                if mac_key not in devices:
                    devices[mac_key] = device
        except Exception as e:
            if debug:
                print(f"[SADP] Error recibiendo: {e}")

    sock.close()

    result = list(devices.values())
    if debug:
        print(f"\n[SADP] Descubrimiento completo: {len(result)} dispositivo(s)")
    return result


def raw_capture(timeout=10):
    """Captura y muestra paquetes SADP crudos para diagnóstico del protocolo."""
    print("Modo captura raw: escuchando tráfico SADP...\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except (AttributeError, OSError):
        pass
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    except Exception:
        pass

    # Bind al puerto 37020 para pasar por el firewall
    try:
        sock.bind(('', SADP_PORT))
        print(f"Enlazado al puerto {SADP_PORT}")
    except OSError:
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        print(f"⚠️  Puerto {SADP_PORT} ocupado, usando {port} (firewall podría bloquear)")

    # Join multicast en todas las interfaces
    iface_ips = get_interface_ips()
    for ip in iface_ips:
        try:
            mreq = struct.pack("4s4s",
                               socket.inet_aton(SADP_MULTICAST),
                               socket.inet_aton(ip))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception:
            pass

    # Enviar sonda desde cada interfaz
    probe = build_probe()
    for ip in iface_ips:
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                            socket.inet_aton(ip))
            sock.sendto(probe, (SADP_MULTICAST, SADP_PORT))
            print(f"Sonda multicast enviada via {ip}")
        except Exception:
            pass
    for brd in get_broadcast_addrs():
        try:
            sock.sendto(probe, (brd, SADP_PORT))
        except Exception:
            pass

    print(f"Sonda enviada. Esperando respuestas ({timeout}s)...\n")

    end = time.time() + timeout
    count = 0
    while time.time() < end:
        ready, _, _ = select.select([sock], [], [], 1.0)
        if not ready:
            continue
        try:
            data, addr = sock.recvfrom(65535)
            count += 1
            print(f"═══ Paquete #{count} de {addr[0]}:{addr[1]} ({len(data)} bytes) ═══")
            xml_idx = data.find(b'<?xml')
            if xml_idx >= 0:
                if xml_idx > 0:
                    print(f"Cabecera binaria ({xml_idx} bytes): {data[:xml_idx].hex()}")
                xml_text = data[xml_idx:].decode('utf-8', errors='replace')
                # Pretty print cortando a 600 chars
                print(f"XML:\n{xml_text[:600]}")
                if len(xml_text) > 600:
                    print(f"  ... ({len(xml_text) - 600} caracteres más)")
            else:
                print(f"Sin XML detectado")
                print(f"Hex (primeros 120 bytes): {data[:120].hex()}")
                print(f"Text: {data[:200].decode('utf-8', errors='replace')}")
            print()
        except Exception as e:
            print(f"Error: {e}")

    print(f"Total: {count} paquete(s) recibido(s)")
    sock.close()


# ────────────────────────────────────────────────────────────
# Modo CLI para pruebas directas
# ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Descubrimiento SADP nativo en Python para dispositivos Hikvision'
    )
    parser.add_argument('--timeout', type=int, default=10,
                        help='Tiempo de espera en segundos (default: 10)')
    parser.add_argument('--debug', action='store_true',
                        help='Mostrar información de depuración detallada')
    parser.add_argument('--csv', action='store_true',
                        help='Salida en formato CSV')
    parser.add_argument('--raw', action='store_true',
                        help='Capturar paquetes crudos para diagnóstico del protocolo')
    args = parser.parse_args()

    if args.raw:
        raw_capture(timeout=args.timeout)
        sys.exit(0)

    print("SADP Discovery - Descubrimiento Nativo Python")
    print(f"Buscando dispositivos Hikvision (timeout {args.timeout}s)...\n")

    devs = discover(timeout=args.timeout, debug=args.debug)

    if args.csv:
        print("IPv4Address,MAC,DeviceType,Activated,Port,HttpPort,"
              "SerialNumber,SoftwareVersion,IPv4SubnetMask,IPv4Gateway,DHCP")
        for d in devs:
            print(f"{d['ip']},{d['mac']},{d['tipo']},{d['estado']},"
                  f"{d['puerto']},{d['http_port']},{d['serial']},"
                  f"{d['version']},{d['subnet']},{d['gateway']},{d['dhcp']}")
    else:
        print(f"Descubiertos {len(devs)} dispositivo(s)\n")
        if devs:
            print(f"{'IP':18s} {'MAC':20s} {'Tipo':12s} {'Estado':10s} "
                  f"{'Puerto':8s} {'Serial'}")
            print("─" * 90)
            for d in devs:
                print(f"{d['ip']:18s} {d['mac']:20s} {d['tipo']:12s} "
                      f"{d['estado']:10s} {d['puerto']:8s} {d['serial']}")
        else:
            print("No se encontraron dispositivos.")
