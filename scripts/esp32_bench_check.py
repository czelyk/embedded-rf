def parse_telemetry(message: bytes) -> Optional[tuple[str, int]]:
    """Parse device telemetry; intentionally ignores synthetic RF metrics."""
    try:
        fields = dict(
            chunk.split("=", 1)
            for chunk in message.decode("ascii").strip().split(";")
            if "=" in chunk
        )
        if fields.get("device") != "esp32-c3":
            return None
        mode = fields["mode"]
        seq = int(fields["sequence"])
        uptime = int(fields["uptime_ms"])
        if mode not in ("NORMAL", "TEST") or seq < 0 or uptime < 0:
            return None
        return mode, seq
    except (UnicodeError, KeyError, TypeError, ValueError):
        return None


def check_udp(seconds: float, port: int) -> UdpStats:
    stats = UdpStats()
    previous = None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError as exc:
            raise CheckError(f"UDP port {port} dinlenemedi: {exc}") from exc
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            sock.settimeout(min(0.5, max(0.01, deadline - time.monotonic())))
            try:
                payload, _ = sock.recvfrom(2048)
            except socket.timeout:
                continue
            decoded = parse_telemetry(payload)
            if decoded is None:
                continue
            mode, sequence = decoded
            stats.packets += 1
            stats.normal += mode == "NORMAL"
            stats.test += mode == "TEST"
            if previous is not None:
                if sequence == previous:
                    stats.duplicates += 1
                elif sequence < previous:
                    stats.resets += 1
                elif sequence > previous + 1:
                    stats.gaps += sequence - previous - 1
            previous = sequence
    if stats.packets == 0:
        raise CheckError(
            "Geçerli UDP telemetrisi alınamadı. Cihazın bu bilgisayara "
            "UDP gönderdiğini ve güvenlik duvarını kontrol edin."
        )
    return stats


def list_ports() -> int:
    try:
        from serial.tools import list_ports as tools
    except ImportError:
        print("Port listelemek için: python -m pip install pyserial")
        return 1
    ports = list(tools.comports())
    if not ports:
        print("Seri port bulunamadı; USB bağlantısını/sürücüyü kontrol edin.")
    else:
        for entry in ports:
            print(f"{entry.device}  -  {entry.description}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--serial", metavar="PORT", help="Örn: COM5 / /dev/ttyUSB0")
    parser.add_argument("--tcp", metavar="ESP32_IP", help="Cihaz IP adresi")
    parser.add_argument("--tcp-port", type=int, default=TCP_PORT)
    parser.add_argument("--udp-seconds", type=float, default=0, metavar="SECONDS")
    parser.add_argument("--udp-port", type=int, default=UDP_PORT)
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()

    if args.timeout <= 0 or args.udp_seconds < 0:
        parser.error("--timeout pozitif, --udp-seconds sıfır veya pozitif olmalı")
    if not (1 <= args.tcp_port <= 65535 and 1 <= args.udp_port <= 65535):
        parser.error("Port numaraları 1-65535 arasında olmalı")
    if args.list_ports:
        return list_ports()
    if not (args.serial or args.tcp or args.udp_seconds):
        parser.print_help()
        return 2

    failures = 0
    for name, open_link in (
        ("USB SERIAL", lambda: SerialLink(args.serial)) if args.serial else (None, None),
        ("TCP CONTROL", lambda: TcpLink(args.tcp, args.tcp_port, args.timeout)) if args.tcp else (None, None),
    ):
        if name is None:
            continue
        print(f"\n[{name}] Simülasyon modu protokol testi")
        link = None
        try:
            link = open_link()
            test_control(link, args.timeout)
            print(f"[{name}] PASS")
        except (CheckError, OSError) as exc:
            failures += 1
            print(f"[{name}] FAIL: {exc}")
        finally:
            if link is not None:
                link.close()

    if args.udp_seconds:
        print(f"\n[UDP] {args.udp_seconds:g} saniye cihaz telemetrisi dinleniyor...")
        try:
            stats = check_udp(args.udp_seconds, args.udp_port)
            print(
                f"[UDP] PASS: {stats.packets} paket, NORMAL={stats.normal}, "
                f"TEST={stats.test}, kayıp sırası={stats.gaps}, "
                f"tekrar={stats.duplicates}, sayaç sıfırlanması={stats.resets}"
            )
        except (CheckError, OSError) as exc:
            failures += 1
            print(f"[UDP] FAIL: {exc}")

