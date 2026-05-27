# SinIceStir server-side artifacts

Files that live on the `ubuntu-4gb-hil-1` VM (Tailscale `100.81.48.21`, public
`5.78.184.174`) hosting `sin-ice-stir.club` behind Caddy.

## Files

### `server.py`
Anonymous suggestion-box backend. Tiny stdlib-only HTTP server listening on
`127.0.0.1:8090`. Accepts `POST /api/suggestion` with JSON or form-encoded
body. Captures **no identifying info** — appends one JSON line per submission
to `/home/work/suggestion-box/data/suggestions.jsonl`.

**Deployed to:** `/home/work/suggestion-box/server.py`
**Owned by:** `work:work`, mode `0755`
**Data dir:** `/home/work/suggestion-box/data/` (mode `0750`)

### `sin-suggestion-box.service`
Systemd unit that runs `server.py` as the `work` user with hardening
(NoNewPrivileges, ProtectSystem=strict, ReadWritePaths limited to the data
dir, etc.).

**Deployed to:** `/etc/systemd/system/sin-suggestion-box.service`
**Enable + start:** `sudo systemctl enable --now sin-suggestion-box.service`

### `sin-ice-stir.caddy`
Caddy site block for `sin-ice-stir.club`. Adds:

- `handle /api/suggestion*` → `reverse_proxy 127.0.0.1:8090`
- `try_files {path} {path}.html {path}/` for clean URLs (so `/foodsafety` →
  `foodsafety.html`)

**Deployed to:** `/etc/caddy/conf.d/sin-ice-stir.caddy`
**Reload:** `sudo systemctl reload caddy`

## Reading suggestions

Each submission is one JSON line. To pretty-print all submissions:

```
ssh work@100.81.48.21 'jq . /home/work/suggestion-box/data/suggestions.jsonl'
```

Or just the messages:

```
ssh work@100.81.48.21 'jq -r ".ts + \"  [\" + .category + \"]  \" + .message" /home/work/suggestion-box/data/suggestions.jsonl'
```

## Quick smoke test

```
# health
curl https://sin-ice-stir.club/api/suggestion/health

# submission
curl -X POST https://sin-ice-stir.club/api/suggestion \
     -H 'Content-Type: application/json' \
     -d '{"message":"test","category":"other"}'
```
