#!/usr/bin/env bash
# Deploy the backend tree to dc6 (primary) and dc4 (backup).
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="/home/ubuntu/tvsports-backend"

rsync_host() {
  host="$1"
  rsync -az --delete \
    --exclude '.venv' \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude '*.egg-info' \
    "${ROOT}/" "${host}:${REMOTE_DIR}/"
}

echo "sync dc6"
rsync_host dc6
echo "sync dc4"
rsync_host dc4

echo "start dc6 stack"
ssh -o BatchMode=yes dc6 "sudo systemctl start docker
sudo iptables -C INPUT -p tcp -m state --state NEW --dport 80 -j ACCEPT 2>/dev/null || \
  sudo iptables -I INPUT 8 -p tcp -m state --state NEW --dport 80 -j ACCEPT
sudo iptables -C INPUT -p tcp -m state --state NEW --dport 443 -j ACCEPT 2>/dev/null || \
  sudo iptables -I INPUT 8 -p tcp -m state --state NEW --dport 443 -j ACCEPT
chmod +x /home/ubuntu/tvsports-backend/deploy/ensure_dc6_http_ports.sh
tmpcron=\$(mktemp)
crontab -l 2>/dev/null | grep -v tvsports-iptables >\"\$tmpcron\" || true
echo '@reboot /home/ubuntu/tvsports-backend/deploy/ensure_dc6_http_ports.sh # tvsports-iptables' >>\"\$tmpcron\"
crontab \"\$tmpcron\"
rm -f \"\$tmpcron\"
cd /home/ubuntu/tvsports-backend
printf 'TVSPORTS_HOSTNAME=tvsports.kernelmax.com\\n' > .env
export TVSPORTS_HOSTNAME=tvsports.kernelmax.com
docker-compose --env-file .env up -d --build"

echo "start dc4 stack and ntfy vhost"
ssh -o BatchMode=yes dc4 "cd /home/ubuntu/tvsports-backend
docker-compose -f docker-compose.dc4-full.yml down
docker-compose -f docker-compose.dc4-full.yml up -d --build --force-recreate
python3 /home/ubuntu/tvsports-backend/deploy/ensure_dc4_ntfy_vhost.py
docker exec ntfy-caddy caddy reload --config /etc/caddy/Caddyfile"

echo "deploy finished"
