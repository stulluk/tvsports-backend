#!/bin/sh
# Re-apply dc6 HTTP/HTTPS accept rules after reboot (no extra packages).
iptables -C INPUT -p tcp -m state --state NEW --dport 80 -j ACCEPT 2>/dev/null || \
  iptables -I INPUT 8 -p tcp -m state --state NEW --dport 80 -j ACCEPT
iptables -C INPUT -p tcp -m state --state NEW --dport 443 -j ACCEPT 2>/dev/null || \
  iptables -I INPUT 8 -p tcp -m state --state NEW --dport 443 -j ACCEPT
