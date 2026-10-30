# Free Messenger server for DeckMessages

DeckMessages connects to Messenger through a small server that runs the
[mautrix-meta](https://github.com/mautrix/meta) bridge. This guide puts it on a free cloud VM. You don't need
your own hardware or a domain name, and it takes about 15 minutes.

```
 phone / PC ──HTTPS──▶  your free VM: Caddy ▶ Synapse (Matrix) ◀▶ Messenger bridge  ──▶ Messenger
```

> **Heads up:** the bridge logs in as you, like an unofficial app would. That isn't sanctioned by Meta's terms,
> and Meta sometimes asks accounts that use unofficial clients to re-verify. Use at your own risk.

## 1. Create a free VM (Oracle Cloud)

1. Sign up at [cloud.oracle.com](https://cloud.oracle.com) for an **Always Free** account. It asks for a card to
   verify you; Always Free resources aren't charged.
2. Go to **Compute → Instances → Create instance**:
   - **Image:** Canonical Ubuntu 24.04
   - **Shape:** `VM.Standard.A1.Flex` (Ampere) with 1 OCPU and 6 GB memory. If it says *out of capacity*, try
     another availability domain or use `VM.Standard.E2.1.Micro`. The installer adds swap on small machines.
   - **Networking:** keep *Assign a public IPv4 address* on.
   - **SSH keys:** choose *Generate a key pair* and **download the private key**.
3. Open the web ports: **Networking → Virtual cloud networks →** your VCN **→ Security → Default security list →
   Add ingress rules**. Add one rule with source `0.0.0.0/0`, protocol TCP, destination port `80`, and another
   for port `443`.

Any other Ubuntu or Debian VM with a public IP works too (Hetzner, DigitalOcean, a Raspberry Pi with port
forwarding). Skip to step 2.

## 2. Run the installer

Connect to the VM from a terminal (PowerShell on Windows), using the key you downloaded and the instance's
public IP:

```bash
ssh -i path/to/ssh-key.key ubuntu@YOUR.PUBLIC.IP
```

Then run:

```bash
curl -fsSL https://raw.githubusercontent.com/Eidhaart/DeckMessages/HEAD/server/install.sh | sudo bash
```

It installs Docker, sets up the homeserver, the bridge, a database, and HTTPS, and creates your account.
At the end it prints your login details:

```
  homeserver:  https://203-0-113-7.sslip.io
  user:        deck
  passphrase:  ****************
```

[sslip.io](https://sslip.io) is a free service that turns your IP into a hostname so HTTPS works without
buying a domain. If you own one, use `... | sudo bash -s -- --domain chat.example.com` and point the domain's
DNS at the VM.

## 3. Connect Messenger

1. Open DeckMessages and enter the homeserver, user, and passphrase. Leave **bridge bot** as `facebookbot`.
2. Type `/bridge`. This opens a chat with the bridge bot.
3. Send `login` to see the login methods:
   - `login messenger-lite`: your Messenger email/phone and password. This is the easiest.
   - `login facebook` / `login messenger`: paste cookies from a logged-in browser (dev tools → Network →
     copy a request *as cURL*). Use this if the password login gets blocked.
4. Approve the login if Facebook asks on your phone. Your chats then appear in the channel list.

Useful bot commands: `help`, `list-logins`, `logout <id>`.

## Looking after it

```bash
cd /opt/deckmessages
sudo docker compose ps                                  # status
sudo docker compose logs -f mautrix-meta                # bridge logs
sudo docker compose pull && sudo docker compose up -d   # update everything
sudo cat credentials.txt                                # show login details again
```

Re-running the installer is safe: it updates the config and keeps your account and chats. Everything lives in
`/opt/deckmessages`; copy that folder to back it up.

**Things to know:**

- **Address changes:** the sslip.io address is based on the VM's IP. Keep the instance running, or give it a
  *reserved* public IP in Oracle, so the address never changes.
- **Idle reclaim:** Oracle may reclaim Always Free VMs it considers idle. Upgrading the account to *Pay As You
  Go* is reported to stop that, and you're still only billed beyond the free limits.
