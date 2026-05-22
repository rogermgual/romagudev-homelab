# Runbook: WireGuard down

## Symptoms
- Cannot connect to the VPN from outside
- `ping 10.0.0.1` does not respond while connected

## Quick diagnosis

```bash
# Service status
sudo systemctl status wg-quick@wg0

# Connected peers and traffic counters
sudo wg show

# Check if the port is listening
sudo ss -ulnp | grep 51820
```

## Common fixes

### Service fails to start
```bash
sudo journalctl -u wg-quick@wg0 -n 50
# Look for config errors or malformed keys
```

### No traffic with a specific peer
- Verify the peer's `PublicKey` in `wg0.conf` is correct
- Verify the `Endpoint` in the client config points to `vpn.romagudev.com:51820`
- Check that port forwarding 51820/UDP is active on the router

### IP forwarding not working (peers connect but have no internet)
```bash
cat /proc/sys/net/ipv4/ip_forward   # should return 1
sudo sysctl -w net.ipv4.ip_forward=1  # enable at runtime
# To persist across reboots, check /etc/sysctl.d/99-wireguard.conf
```

### Clean restart
```bash
sudo wg-quick down wg0
sudo wg-quick up wg0
```
