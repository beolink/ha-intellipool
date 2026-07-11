"""Active network discovery for Intellipool INTP-1010B."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from dataclasses import dataclass

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Ports to probe on each host
PROBE_PORTS = [80, 8080, 443, 8443]

# HTTP paths that might return data on the device
PROBE_HTTP_PATHS = [
    "/",
    "/api/v1/status",
    "/api/status",
    "/status",
    "/data.json",
    "/state.json",
    "/pool",
    "/cgi-bin/status",
]

# Strings that identify an Intellipool / Pentair device in HTTP responses
FINGERPRINT_STRINGS = [
    "intellipool",
    "intp",
    "pentair",
    "Pentair",
    "IntelliPool",
    "INTP",
    "pool controller",
    "pool automation",
]

# Hostnames to try via mDNS / DHCP resolution
CANDIDATE_HOSTNAMES = [
    "intellipool.local",
    "intellipool",
    "pentair.local",
    "pentair",
    "intp1010b.local",
    "poolcontroller.local",
]

# Scan concurrency caps
PORT_SCAN_CONCURRENCY = 50
HTTP_PROBE_CONCURRENCY = 20
PORT_SCAN_TIMEOUT = 0.5   # seconds
HTTP_PROBE_TIMEOUT = 3.0  # seconds


@dataclass
class DiscoveredDevice:
    host: str
    port: int
    hostname: str | None
    api_path: str | None
    fingerprint_match: str | None
    confidence: str  # "high" | "medium" | "low"


def _get_local_subnet() -> list[str]:
    """Return all IPv4 addresses in the same /24 as the host machine."""
    candidates: list[str] = []
    try:
        # Connect a UDP socket to discover the default outbound interface
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
        candidates = [str(h) for h in network.hosts()]
        _LOGGER.debug("Scanning subnet %s (%d hosts)", network, len(candidates))
    except OSError:
        _LOGGER.warning("Could not determine local subnet for discovery")
    return candidates


async def _tcp_port_open(ip: str, port: int, semaphore: asyncio.Semaphore) -> bool:
    """Return True if a TCP connection to ip:port succeeds within the timeout."""
    async with semaphore:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=PORT_SCAN_TIMEOUT,
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return True
        except (OSError, asyncio.TimeoutError):
            return False


async def _http_fingerprint(
    ip: str,
    port: int,
    semaphore: asyncio.Semaphore,
    session: aiohttp.ClientSession,
) -> tuple[str | None, str | None]:
    """
    Probe HTTP paths on ip:port and return (matched_path, matched_fingerprint).
    Returns (None, None) if nothing matches.
    """
    scheme = "https" if port in (443, 8443) else "http"
    async with semaphore:
        for path in PROBE_HTTP_PATHS:
            url = f"{scheme}://{ip}:{port}{path}"
            try:
                async with session.get(
                    url,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=HTTP_PROBE_TIMEOUT),
                    allow_redirects=True,
                ) as resp:
                    body = await resp.text(errors="replace")
                    combined = (
                        body
                        + " ".join(
                            f"{k}: {v}" for k, v in resp.headers.items()
                        )
                    ).lower()
                    for fp in FINGERPRINT_STRINGS:
                        if fp.lower() in combined:
                            _LOGGER.info(
                                "Fingerprint match '%s' at %s%s", fp, ip, path
                            )
                            return path, fp
            except Exception:
                continue
    return None, None


async def _resolve_hostname(hostname: str) -> str | None:
    """Resolve a hostname to an IPv4 address, return None on failure."""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: socket.getaddrinfo(hostname, None, socket.AF_INET),
        )
        if result:
            return result[0][4][0]
    except OSError:
        pass
    return None


async def _probe_known_hostnames(
    session: aiohttp.ClientSession,
    http_semaphore: asyncio.Semaphore,
) -> list[DiscoveredDevice]:
    """Try a list of well-known hostnames and fingerprint any that resolve."""
    found: list[DiscoveredDevice] = []
    for hostname in CANDIDATE_HOSTNAMES:
        ip = await _resolve_hostname(hostname)
        if ip is None:
            continue
        _LOGGER.debug("Resolved %s → %s", hostname, ip)
        for port in PROBE_PORTS:
            path, fp = await _http_fingerprint(ip, port, http_semaphore, session)
            if fp:
                found.append(
                    DiscoveredDevice(
                        host=ip,
                        port=port,
                        hostname=hostname,
                        api_path=path,
                        fingerprint_match=fp,
                        confidence="high",
                    )
                )
                break
            # Even without fingerprint, a responding device at a known hostname
            # is worth surfacing to the user
            ok = await _tcp_port_open(ip, port, asyncio.Semaphore(1))
            if ok:
                found.append(
                    DiscoveredDevice(
                        host=ip,
                        port=port,
                        hostname=hostname,
                        api_path=None,
                        fingerprint_match=None,
                        confidence="medium",
                    )
                )
                break
    return found


async def discover_devices(timeout: float = 30.0) -> list[DiscoveredDevice]:
    """
    Scan the local /24 subnet and known hostnames for Intellipool devices.

    Returns a list of DiscoveredDevice, sorted highest-confidence first.
    """
    found: list[DiscoveredDevice] = []
    seen_ips: set[str] = set()

    port_semaphore = asyncio.Semaphore(PORT_SCAN_CONCURRENCY)
    http_semaphore = asyncio.Semaphore(HTTP_PROBE_CONCURRENCY)

    connector = aiohttp.TCPConnector(ssl=False, limit=HTTP_PROBE_CONCURRENCY)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Phase 1: known hostnames (fast, high-confidence)
        _LOGGER.debug("Discovery phase 1: known hostnames")
        hostname_results = await _probe_known_hostnames(session, http_semaphore)
        for dev in hostname_results:
            if dev.host not in seen_ips:
                seen_ips.add(dev.host)
                found.append(dev)

        # Phase 2: subnet port scan
        _LOGGER.debug("Discovery phase 2: subnet scan")
        subnet_hosts = _get_local_subnet()
        if not subnet_hosts:
            return sorted(found, key=lambda d: {"high": 0, "medium": 1, "low": 2}[d.confidence])

        # Remove hosts already confirmed via hostname probe
        subnet_hosts = [h for h in subnet_hosts if h not in seen_ips]

        # TCP port scan all hosts concurrently
        port_tasks = [
            _tcp_port_open(ip, port, port_semaphore)
            for ip in subnet_hosts
            for port in PROBE_PORTS
        ]
        try:
            port_results = await asyncio.wait_for(
                asyncio.gather(*port_tasks, return_exceptions=True),
                timeout=timeout * 0.5,
            )
        except asyncio.TimeoutError:
            port_results = [False] * len(port_tasks)

        # Build list of (ip, port) pairs that had open ports
        open_endpoints: list[tuple[str, int]] = []
        idx = 0
        for ip in subnet_hosts:
            for port in PROBE_PORTS:
                if port_results[idx] is True:
                    open_endpoints.append((ip, port))
                idx += 1

        _LOGGER.debug(
            "Found %d open HTTP endpoints, fingerprinting...", len(open_endpoints)
        )

        # Phase 3: HTTP fingerprint open endpoints
        fp_tasks = [
            _http_fingerprint(ip, port, http_semaphore, session)
            for ip, port in open_endpoints
            if ip not in seen_ips
        ]
        try:
            fp_results = await asyncio.wait_for(
                asyncio.gather(*fp_tasks, return_exceptions=True),
                timeout=timeout * 0.5,
            )
        except asyncio.TimeoutError:
            fp_results = [(None, None)] * len(fp_tasks)

        for (ip, port), result in zip(
            [(ip, p) for ip, p in open_endpoints if ip not in seen_ips],
            fp_results,
        ):
            if isinstance(result, Exception):
                continue
            path, fp = result
            if fp and ip not in seen_ips:
                seen_ips.add(ip)
                found.append(
                    DiscoveredDevice(
                        host=ip,
                        port=port,
                        hostname=None,
                        api_path=path,
                        fingerprint_match=fp,
                        confidence="high",
                    )
                )

    # Sort: high → medium → low
    order = {"high": 0, "medium": 1, "low": 2}
    found.sort(key=lambda d: order[d.confidence])

    _LOGGER.info(
        "Intellipool discovery complete: %d candidate(s) found", len(found)
    )
    return found
