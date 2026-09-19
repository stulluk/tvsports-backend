#!/usr/bin/env python3
"""Add the tvsports2 reverse-proxy site to the dc4 ntfy Caddyfile."""

from pathlib import Path

CADDYFILE = Path("/home/ubuntu/ntfy/Caddyfile")
BLOCK = """
tvsports2.kernelmax.com {
	encode gzip
	reverse_proxy tvsports-caddy:80
}
"""


def main() -> None:
    """Append the vhost once, then print what was done."""
    text = CADDYFILE.read_text(encoding="utf-8")
    if "tvsports2.kernelmax.com" in text:
        print("tvsports2 vhost already present")
        return
    CADDYFILE.write_text(text.rstrip() + "\n" + BLOCK, encoding="utf-8")
    print("appended tvsports2 vhost")


if __name__ == "__main__":
    main()
