#!/usr/bin/env python3
"""
Cloudflare DDNS updater.

Reads CF_API_TOKEN, CF_ZONE_ID, and CF_RECORD_NAME from the environment.
Fetches the current public IP, compares it to the DNS record, and PATCHes
only when it has changed.  Designed to run as a systemd service on a loop
(see ddns.service) rather than a one-shot cron job so it logs cleanly via
journald.
"""

import logging
import os
import sys
import time
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Config (all from environment — no secrets in this file)
# ---------------------------------------------------------------------------

API_TOKEN = os.environ["CF_API_TOKEN"]
ZONE_ID = os.environ["CF_ZONE_ID"]
RECORD_NAME = os.environ.get("CF_RECORD_NAME", "romagudev.com")
TTL = int(os.environ.get("CF_TTL", "60"))
CHECK_INTERVAL = int(os.environ.get("DDNS_INTERVAL", "300"))  # seconds

CF_API = "https://api.cloudflare.com/client/v4"
IP_PROVIDERS = [
    "https://api4.my-ip.io/ip",
    "https://ipv4.icanhazip.com",
    "https://api.ipify.org",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("ddns")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_public_ip() -> str:
    """Try each IP provider in order; raise if all fail."""
    for url in IP_PROVIDERS:
        try:
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            ip = r.text.strip()
            if ip:
                return ip
        except requests.RequestException:
            continue
    raise RuntimeError("All IP providers failed")


def cf_headers() -> dict:
    """Cloudflare API headers with auth."""
    return {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}


def get_record() -> tuple[str, str]:
    """Return (record_id, current_ip) for RECORD_NAME."""
    url = f"{CF_API}/zones/{ZONE_ID}/dns_records"
    params = {"type": "A", "name": RECORD_NAME}
    r = requests.get(url, headers=cf_headers(), params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if not data["result"]:
        raise RuntimeError(f"No A record found for {RECORD_NAME} in zone {ZONE_ID}")
    record = data["result"][0]
    return record["id"], record["content"]


def update_record(record_id: str, new_ip: str) -> None:
    """PATCH the A record with the new IP."""
    url = f"{CF_API}/zones/{ZONE_ID}/dns_records/{record_id}"
    payload = {"type": "A", "name": RECORD_NAME, "content": new_ip, "ttl": TTL, "proxied": False}
    r = requests.patch(url, headers=cf_headers(), json=payload, timeout=10)
    r.raise_for_status()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run_once() -> None:
    """Check IP and update DNS if needed."""
    public_ip = get_public_ip()
    record_id, dns_ip = get_record()

    if public_ip == dns_ip:
        log.info("IP unchanged (%s), nothing to do", public_ip)
        return

    log.info("IP changed: %s → %s, updating DNS", dns_ip, public_ip)
    update_record(record_id, public_ip)
    log.info("DNS record updated to %s", public_ip)


def main() -> None:
    """Run the DDNS updater in an infinite loop with error handling and logging."""
    log.info("DDNS service started (record=%s, interval=%ds)", RECORD_NAME, CHECK_INTERVAL)
    while True:
        try:
            run_once()
        except Exception as exc:
            log.error("Update failed: %s", exc)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
