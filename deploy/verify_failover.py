#!/usr/bin/env python3
"""Prove the Android client can fall over from dc6 to dc4."""

from __future__ import annotations

import json
import ssl
import subprocess
import urllib.error
import urllib.request

PRIMARY = "https://tvsports.kernelmax.com/health.json"
BACKUP = "https://tvsports2.kernelmax.com/health.json"
PRIMARY_IP = "130.162.50.10"
BACKUP_IP = "130.162.41.32"


def fetch(url: str, ip: str, timeout: float = 8.0) -> dict:
    """GET JSON from url while pinning the host to ip (local DNS may lag)."""
    host = url.split("/")[2]
    request = urllib.request.Request(url, headers={"User-Agent": "tvsports-failover-check"})
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        urllib.request.ProxyHandler({}),
    )
    # Use curl --resolve so we do not depend on this machine's resolver.
    raw = subprocess.check_output(
        [
            "curl",
            "-sS",
            "--max-time",
            str(int(timeout)),
            "--resolve",
            f"{host}:443:{ip}",
            url,
        ],
        text=True,
    )
    return json.loads(raw)


def fetch_may_fail(url: str, ip: str) -> str:
    """Return ok / fail for one host."""
    try:
        data = fetch(url, ip)
        return f"ok events={data.get('event_count')}"
    except (subprocess.CalledProcessError, json.JSONDecodeError, urllib.error.URLError) as exc:
        return f"fail ({exc})"


def ssh(host: str, command: str) -> None:
    """Run a remote command with BatchMode."""
    subprocess.check_call(["ssh", "-o", "BatchMode=yes", host, command])


def main() -> None:
    """Stop primary Caddy, confirm backup answers, then start primary again."""
    print("before: primary", fetch_may_fail(PRIMARY, PRIMARY_IP))
    print("before: backup ", fetch_may_fail(BACKUP, BACKUP_IP))
    print("stopping dc6 caddy")
    ssh("dc6", "cd /home/ubuntu/tvsports-backend && docker-compose stop caddy")
    try:
        primary_down = fetch_may_fail(PRIMARY, PRIMARY_IP)
        backup_up = fetch_may_fail(BACKUP, BACKUP_IP)
        print("during: primary", primary_down)
        print("during: backup ", backup_up)
        if not backup_up.startswith("ok"):
            raise SystemExit("backup did not serve while primary was down")
        if primary_down.startswith("ok"):
            raise SystemExit("primary still served after caddy stop; failover test invalid")
        print("failover path verified")
    finally:
        print("starting dc6 caddy")
        ssh("dc6", "cd /home/ubuntu/tvsports-backend && docker-compose start caddy")
    print("after: primary", fetch_may_fail(PRIMARY, PRIMARY_IP))


if __name__ == "__main__":
    main()
