#!/usr/bin/env bash
# Usage: sudo bash wireguard/add-clients.sh <name> [name2 name3 ...]
# Generates keys and a ready-to-use .conf for each client, then reloads WireGuard.
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <client-name> [client-name2 ...]"
  exit 1
fi

WG_DIR=/etc/wireguard
SERVER_PUB=$(cat "$WG_DIR/server.pub")
ENDPOINT="vpn.romagudev.com:51820"

mkdir -p "$WG_DIR/clients"
chmod 700 "$WG_DIR/clients"

next_ip() {
  # Find the highest 10.0.0.X already in wg0.conf and return X+1 (min 2)
  local max
  max=$(grep -oP '10\.0\.0\.\K\d+(?=/32)' "$WG_DIR/wg0.conf" 2>/dev/null | sort -n | tail -1)
  echo $(( ${max:-1} + 1 ))
}

for NAME in "$@"; do
  IP="10.0.0.$(next_ip)"
  KEY="$WG_DIR/clients/$NAME.key"
  PUB="$WG_DIR/clients/$NAME.pub"
  CONF="$WG_DIR/clients/$NAME.conf"

  if [[ ! -f "$KEY" ]]; then
    wg genkey | tee "$KEY" | wg pubkey > "$PUB"
    chmod 600 "$KEY"
    echo "[$NAME] keys generated"
  else
    echo "[$NAME] keys already exist, skipping key generation"
  fi

  cat > "$CONF" <<EOF
[Interface]
Address = $IP/32
PrivateKey = $(cat "$KEY")
DNS = 10.0.0.1

[Peer]
PublicKey = $SERVER_PUB
Endpoint = $ENDPOINT
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25
EOF
  chmod 600 "$CONF"
  echo "[$NAME] config written → $CONF (VPN IP: $IP)"

  if ! grep -q "$(cat "$PUB")" "$WG_DIR/wg0.conf"; then
    cat >> "$WG_DIR/wg0.conf" <<EOF

# $NAME ($IP)
[Peer]
PublicKey = $(cat "$PUB")
AllowedIPs = $IP/32
EOF
    echo "[$NAME] peer added to wg0.conf"
  else
    echo "[$NAME] peer already in wg0.conf, skipping"
  fi
done

systemctl reload wg-quick@wg0
echo ""
echo "Done. Active peers:"
wg show
