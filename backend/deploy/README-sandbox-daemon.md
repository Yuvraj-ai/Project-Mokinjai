# Sandbox daemon — InstaBox runbook

The API on Render has no Docker daemon. This machine owns Docker and one session per
agent run, and the API reaches it over HTTPS with two auth layers. The decision record
is `docs/guides/deployment-architecture.md`; this file is only the operator's steps.

## 1. Put the repo on the machine

```bash
sudo mkdir -p /data/mokinjay
sudo chown "$USER":"$USER" /data/mokinjay
rsync -a --delete --exclude venv --exclude .git \
  ./backend/ /data/mokinjay/backend/
# docker/ must be at /data/mokinjay/docker/, because the build command uses it.
rsync -a ./docker/ /data/mokinjay/docker/
```

If the host has no `rsync` (the InstaBox Debian template does not), the same copy
works over a tar pipe:

```bash
tar czf - --exclude=venv --exclude=__pycache__ --exclude='*.pyc' --exclude=logs \
  -C backend . | ssh <host> 'tar xzf - -C /data/mokinjay/backend'
tar czf - -C docker . | ssh <host> 'tar xzf - -C /data/mokinjay/docker'
```

Create the venv and install only what the daemon imports:

```bash
cd /data/mokinjay/backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

The daemon needs no database, no LLM key and no JWT secret. `Settings` defaults are
enough. It does need our HMAC secret, because every session route verifies it. Copy
`backend/deploy/daemon.env.example` to `/data/mokinjay/.env`, replace `CHANGE_ME`, and
lock it down:

```bash
cd /data/mokinjay
printf "SANDBOX_DAEMON_SECRET=%s\n" "$(openssl rand -hex 32)" > .env
chmod 600 .env
```

`config.py` resolves `.env` from the repository root — `/data/mokinjay/.env` when the
repo is deployed there — so this is the file the service reads regardless of its
working directory. Do not copy the API's `.env`; the daemon needs nothing else.


## 2. Build the sandbox image here

No registry and no push — the image travels with the repo:

```bash
cd /data/mokinjay
sudo docker build -f docker/Dockerfile.sandbox -t mokinjay-sandbox:1 .
```

If this is skipped, every first run fails with `image_missing`.

The service user must reach the socket (`docker version` is the probe):

```bash
sudo usermod -aG docker "$USER"
newgrp docker   # or log out and back in
docker version
```

## 3. Install the service

```bash
sudo cp /data/mokinjay/backend/deploy/mokinjay-sandbox-daemon.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mokinjay-sandbox-daemon
systemctl status mokinjay-sandbox-daemon --no-pager
```

`enable` matters: a resume can fall back to a fresh boot with files intact, and
stop/restart ends processes. `Restart=always` and `StartLimitIntervalSec=0` keep
systemd from giving up after five restarts.

Verify locally:

```bash
curl -fsS http://127.0.0.1:8100/health
# {"status":"ok","docker":true,"sessions":0}
```

## 4. Publish the port — private, never public

Publish **8100** as a **private** port. InstaBox shows the `ibp_…` token once; store it
in Render immediately. Ports must be 1024–65535 and 16 is the maximum.

The daemon binds `0.0.0.0` because the proxy connects from outside the VM's loopback.
Confirm that once: edit the unit to `--host 127.0.0.1`, restart, publish, `curl` the
public URL. A `502` proves `0.0.0.0` is required; put it back.

Verify through the proxy:

```bash
curl -fsS https://<port>-<id>.<domain>/health \
  -H "Authorization: Bearer ibp_…"
# {"status":"ok","docker":true}
```

`/health` is deliberately unauthenticated: it is the liveness probe and must answer
before the shared secret is configured. Every session route needs both the InstaBox
bearer token and our own `X-Mokinjay-Signature: t=<unix>,v1=<hmac>` header.

## 5. Put the values in Render

| Render variable | Value |
|---|---|
| `SANDBOX_BACKEND` | `instabox` |
| `SANDBOX_DAEMON_URL` | the published HTTPS URL, no trailing slash |
| `SANDBOX_DAEMON_TOKEN` | the `ibp_…` token |
| `SANDBOX_DAEMON_SECRET` | any long random string; the API signs with it |

Generate the shared secret once and use the **same** value on both sides if you ever
run a client manually. Rotating the InstaBox token and rotating this secret are
separate operations; rotating one does not break the other.

## 6. Behaviour a reader will look for elsewhere

- The daemon admits **2** concurrent sessions and answers `503` beyond that. The API
  maps `503` to `backend_unavailable`; there is no queue.
- It prunes `/data/sessions` roots older than `max_run_seconds + 1 h`, at startup and
  on every create. `close()` never runs if Render dies or the run cap is hit, so the
  daemon cannot rely on the API cleaning up.
- A session id that does not match `^[A-Za-z0-9_-]{1,64}$` is a `400`. It becomes a
  directory and a container name, so it is checked before either exists.
- A `409` from the machine means the max-run cooldown (5–20 min). It is not retried;
  the agent sees "The execution engine is restarting."

## 7. Recovery

- After a stop, `systemctl start` is not enough: Docker containers are gone. Sessions
  are per-run, so the API simply opens a new one.
- A create for a name whose container survived (`docker rm -f <name>`) is safe: the
  daemon removes it and recreates the session rather than colliding.
- A daemon restart loses the in-memory job cache. A retried job may run twice; the
  container has `--network none`, so the blast radius is CPU.
- Prune unused images after rebuilds; the disk is 20 GiB.

## 8. Transport limits — measured

- **Requests are capped at 32 MiB by the proxy.** 31 MiB arrives; 32 MiB returns an
  instant `502` before the daemon sees it. The client stages anything larger in 16 MiB
  parts (`POST /sessions/{id}/files?offset=` + `/finalize`). A 95 MiB file was verified
  end to end (six parts, finalize 1.0 s, job read `99,614,720` bytes).
- **Responses:** a 60 MiB output tar came back through the proxy in 140 s. The 512 MiB
  top-tier case is deferred until a run actually needs it.

The client streams outputs to a temp file, so memory is bounded. If a future response
does truncate, chunk by member name; do not redesign before that happens.
