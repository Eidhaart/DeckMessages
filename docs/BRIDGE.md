# Connecting DeckMessages to Facebook Messenger

Meta doesn't offer a public API for personal Messenger chats. The official Messenger Platform only covers
business Pages. DeckMessages gets around this the way Beeper and similar apps do:

```
 DeckMessages  ──Matrix API──▶  your homeserver (Synapse)  ◀──appservice──▶  mautrix-meta  ──▶  Messenger
 (desktop / Android)                                                          (acts as a logged-in browser)
```

Each Messenger conversation becomes a Matrix room. DeckMessages is a regular Matrix client, so you could also
open the same chats in Element or any other Matrix app.

> **Heads up:** bridging uses your own Messenger session cookies. This isn't sanctioned by Meta's terms, and
> Meta occasionally flags or checkpoints accounts that use unofficial clients. Use at your own risk.

## What you need

- A small Linux box or VPS with Docker and Docker Compose (1 GB RAM is fine).
- A domain name pointing at it, e.g. `matrix.example.com`.
- HTTPS in front of port 8008. Use a reverse proxy such as Caddy:
  `matrix.example.com { reverse_proxy localhost:8008 }`. Android won't connect to plain `http://` servers.

## 1. Start Synapse

```bash
cd bridge
cp .env.example .env          # set SERVER_NAME
docker compose run --rm synapse generate
```

In `synapse/homeserver.yaml`:

- Swap the `database:` block for Postgres:

  ```yaml
  database:
    name: psycopg2
    args:
      user: deck
      password: change-me
      database: synapse
      host: postgres
      cp_min: 5
      cp_max: 10
  ```

- Leave public registration **off**. You'll create your account by hand.

```bash
docker compose up -d postgres synapse
docker compose exec synapse register_new_matrix_user -c /data/homeserver.yaml http://localhost:8008
```

## 2. Configure the Messenger bridge

```bash
docker compose run --rm mautrix-meta      # first run writes data/meta/config.yaml, then exits
```

Edit `data/meta/config.yaml`:

```yaml
network:
  mode: messenger                 # facebook.com Messenger. Use "instagram" for IG DMs.

homeserver:
  address: http://synapse:8008
  domain: matrix.example.com      # same as SERVER_NAME

appservice:
  address: http://mautrix-meta:29319
  hostname: 0.0.0.0
  port: 29319

database:
  type: postgres
  uri: postgres://deck:change-me@postgres/mautrix_meta?sslmode=disable

bridge:
  permissions:
    "matrix.example.com": user
    "@you:matrix.example.com": admin

encryption:
  allow: true                     # DeckMessages supports E2EE rooms; set false for a simpler setup
  default: true
```

Run it once more to generate `data/meta/registration.yaml`, then register it with Synapse:

```bash
docker compose run --rm mautrix-meta      # writes registration.yaml
cp data/meta/registration.yaml synapse/meta-registration.yaml
```

Add this to `synapse/homeserver.yaml`:

```yaml
app_service_config_files:
  - /data/meta-registration.yaml
```

```bash
docker compose up -d
```

The option names above match current mautrix-meta releases. If a key looks different in your generated config,
the [official mautrix-meta docs](https://docs.mau.fi/bridges/go/meta/index.html) are the source of truth.

## 3. Log in from DeckMessages

1. Launch DeckMessages and enter your homeserver URL, Matrix user, and password.
   Keep **bridge bot** set to `metabot` unless you renamed the bot in the config.
2. If no `⚙ metabot` channel appears yet, open a DM with `@metabot:matrix.example.com` from any Matrix client.
   Then type `/bridge` in the deck to jump to it.
3. Send `login` to the bot and follow its instructions. For Messenger, it asks for cookies from a logged-in
   messenger.com tab: in your browser's dev tools, copy the request as cURL and paste it.
4. The bridge creates a room for each recent Messenger chat. With **auto-accept invites** on, they appear in the
   channel list right away.

Useful bot commands: `help`, `list-logins`, `logout <id>`, `sync`.

## Optional extras

- **Double puppeting** makes messages you send from your phone's Messenger app show up as you instead of as a
  ghost user. See the mautrix double puppeting docs.
- **Instagram DMs:** run a second mautrix-meta container with `mode: instagram`.
- **Other networks:** mautrix bridges also exist for WhatsApp, Signal, Telegram, Discord and Google Messages.
  They show up in DeckMessages the same way.
