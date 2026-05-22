# romagudev-homelab

Personal homelab infrastructure running on a Raspberry Pi. Covers everything from initial setup to production services.

## What's in here

| Directory | Purpose |
|-----------|---------|
| `docs/` | Architecture decisions, setup guide, and runbooks |
| `ddns/` | Cloudflare DDNS update script and systemd service |
| `wireguard/` | VPN config templates (no real keys — ever) |
| `nginx/` | Reverse proxy config and virtual hosts |
| `services/` | One directory per hosted service or project |
| `scripts/` | Bootstrap and maintenance utilities |

## Quick start

See [`docs/setup-guide.md`](docs/setup-guide.md) for a full walkthrough.

## Security note

Config files containing secrets (private keys, tokens, passwords) are never committed. Use the `.template` files as a reference and keep your real configs out of version control.
