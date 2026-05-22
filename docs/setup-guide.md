# Setup guide

Full installation guide for the homelab from scratch. Follow in order — each section depends on the previous one.

## Prerequisites

- Raspberry Pi with Ubuntu Server
- Domain managed by Cloudflare
- SSH access to the RPi

---

## 1. DDNS (Cloudflare)

Keeps the DNS record pointing to the current public IP even when the ISP changes it.

### Required credentials

**Zone ID:** Cloudflare dashboard → your domain → Overview → right sidebar.

**API Token:** Cloudflare dashboard → user icon → My Profile → API Tokens → Create Token → "Edit zone DNS" template → scope it to your specific zone only.

### Installation on the RPi

```bash
# 1. Create a dedicated unprivileged user
sudo useradd -r -s /sbin/nologin ddns

# 2. Copy the script
sudo cp ddns/ddns-update.py /usr/local/bin/ddns-update.py
sudo chmod +x /usr/local/bin/ddns-update.py

# 3. Create the secrets file
sudo mkdir /etc/ddns
sudo cp ddns/.env.example /etc/ddns/ddns.env
sudo nano /etc/ddns/ddns.env        # fill in CF_API_TOKEN, CF_ZONE_ID, CF_RECORD_NAME
sudo chmod 640 /etc/ddns/ddns.env
sudo chown root:ddns /etc/ddns/ddns.env

# 4. Install and start the service
sudo cp ddns/ddns.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ddns

# 5. Check logs
sudo journalctl -u ddns -f
```

### Verify it works

```bash
dig home.romagudev.com +short   # should return your public IP
curl -s https://api4.my-ip.io/ip   # your current public IP
```

Both should match.

---

## 2. WireGuard

VPN server on the RPi. Internal network `10.0.0.x`:

| IP | Client |
|---|---|
| `10.0.0.1` | RPi (server) |
| `10.0.0.2` | hrodgerr (primary) |
| `10.0.0.3` | tebrase |
| `10.0.0.4` | nakko |
| `10.0.0.5` | hrodgerr-afk |

### Installation

```bash
sudo apt install wireguard
```

### Enable IP forwarding (permanent)

```bash
echo "net.ipv4.ip_forward=1" | sudo tee /etc/sysctl.d/99-wireguard.conf
sudo sysctl -p /etc/sysctl.d/99-wireguard.conf
```

### Generate server keys

```bash
wg genkey | sudo tee /etc/wireguard/server.key | wg pubkey | sudo tee /etc/wireguard/server.pub
sudo chmod 600 /etc/wireguard/server.key
```

### Generate client keys

One key pair per client. The private key goes in the client's `.conf`, the public key goes in the server's `wg0.conf`.

```bash
sudo mkdir /etc/wireguard/clients
sudo chmod 700 /etc/wireguard/clients

# Repeat for each client
wg genkey | sudo tee /etc/wireguard/clients/<name>.key | wg pubkey | sudo tee /etc/wireguard/clients/<name>.pub
sudo chmod 600 /etc/wireguard/clients/<name>.key
```

For the current clients:

```bash
for name in hrodgerr tebrase nakko hrodgerr-afk; do
  wg genkey | sudo tee /etc/wireguard/clients/$name.key | wg pubkey | sudo tee /etc/wireguard/clients/$name.pub
  sudo chmod 600 /etc/wireguard/clients/$name.key
done
```

### Create the server config

```bash
sudo nano /etc/wireguard/wg0.conf
```

Use `wireguard/server/wg0.conf.template` as reference. Replace:
- `REPLACE_WITH_SERVER_PRIVATE_KEY` → `sudo cat /etc/wireguard/server.key`
- Each `REPLACE_WITH_<NAME>_PUBLIC_KEY` → `sudo cat /etc/wireguard/clients/<name>.pub`
- `eth0` → actual RPi network interface (`ip route show default` to find it)

```bash
sudo chmod 600 /etc/wireguard/wg0.conf
```

### Start the server

```bash
sudo systemctl enable --now wg-quick@wg0

# Verify peers are listed
sudo wg show
```

### Router port forwarding

Open on the home router:
- `51820/UDP` → RPi local IP

---

## 3. Initialising all clients at once

Run this once on the RPi after the server is up. It generates key pairs, writes each client's `.conf`, and adds all peers to `wg0.conf` in one shot:

```bash
sudo bash wireguard/add-clients.sh
```

The script is idempotent — re-running it skips clients whose keys already exist and peers already present in `wg0.conf`.

---

## 4. Adding a new client manually

### On the RPi — create the client config

Build the `.conf` file for the client. These files are not tracked by git (see `.gitignore`) and are managed directly on the RPi.

```bash
# Print the values you need
sudo cat /etc/wireguard/server.pub          # → PublicKey in [Peer]
sudo cat /etc/wireguard/clients/<name>.key  # → PrivateKey in [Interface]
```

Create the file at `/etc/wireguard/clients/<name>.conf` using `wireguard/clients/client.conf.template` as reference. Replace:
- `10.0.0.X` → IP assigned to this client (see table above)
- `REPLACE_WITH_CLIENT_PRIVATE_KEY` → contents of `<name>.key`
- `REPLACE_WITH_SERVER_PUBLIC_KEY` → contents of `server.pub`

### On the RPi — add the peer to the server

Add a `[Peer]` block to `/etc/wireguard/wg0.conf`:

```ini
[Peer]
PublicKey = <contents of clients/<name>.pub>
AllowedIPs = 10.0.0.X/32
```

Reload without dropping active connections:

```bash
sudo systemctl reload wg-quick@wg0
```

### Send the config to the client

Share the `.conf` file via a secure channel (Signal, AirDrop). Never send it over unencrypted email.

Alternatively, generate a QR code the client can scan directly with the WireGuard mobile app:

```bash
sudo apt install qrencode
sudo qrencode -t ansiutf8 < /etc/wireguard/clients/<name>.conf
```

---

## 5. Connecting as a client

### Linux / macOS

```bash
# Install WireGuard
sudo apt install wireguard          # Debian/Ubuntu
brew install wireguard-tools        # macOS (Homebrew)

# Place the config (use the file received from the server admin)
sudo cp <name>.conf /etc/wireguard/wg0.conf
sudo chmod 600 /etc/wireguard/wg0.conf

# Connect
sudo wg-quick up wg0

# Verify — should show the server as a peer with a handshake
sudo wg show

# Disconnect
sudo wg-quick down wg0
```

On macOS you can also use the WireGuard app from the App Store and import the `.conf` file via File → Import Tunnel(s).

### iOS / Android

1. Install the **WireGuard** app (App Store / Play Store)
2. Tap **+** → **Create from file or archive** and import the `.conf` file, or scan the QR code generated by the server admin
3. Toggle the tunnel on

### Verify the connection

Once connected, you should be able to reach the RPi at `10.0.0.1`:

```bash
ping 10.0.0.1
ssh user@10.0.0.1
```

---

## 6. Nginx — subdomains

*(Pending)*
