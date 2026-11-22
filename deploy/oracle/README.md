# Oracle server (self-hosted Supabase)

Since 2026-11-22 the app's database runs on an Oracle Cloud Always Free server (Ampere A1, 2 OCPU,
12 GB RAM, Ubuntu 24.04, 4 GB swap) at `https://stockwatchpk.duckdns.org`. Scraping still runs on
GitHub Actions; the server only holds the database and loads the snapshots from `monitor-state`.

| On the server | What it is |
| --- | --- |
| `~/supabase/` | Supabase self-hosted (`setup.sh`, release `self-hosted/v0.8.4`), started with `sh run.sh start`. `.env` holds every secret (chmod 600, never in git). |
| `~/supabase/docker-compose.local.yml` | Copy of `docker-compose.local.yml` here: database pooler and Studio bound to 127.0.0.1 only. |
| `~/supabase/volumes/proxy/caddy/Caddyfile` | Copy of `Caddyfile` here: Caddy (HTTPS, Let's Encrypt over port 443) exposes only `/auth/v1` and `/rest/v1`. |
| `~/stockwatch/` | Clone of this repo with `.venv`; `.db.env` holds `DATABASE_URL` for the local pooler (not in git). |
| `stockwatch-ingest.timer` | Every 15 minutes: `git pull`, then `ingest.sh`, which loads only once per finished scrape run. |
| `stockwatch-backup.timer` | 22:30 UTC: `backup.sh`, a `pg_dump` into `~/backups`, last 7 kept (same disk). |

Firewall: Oracle security list allows TCP 22 and 443; the server's iptables also allows 80 and 443.
Ports 5432/6543 (database) and 3000 (Studio) are not reachable from outside.

```bash
ssh -i <key> ubuntu@130.210.105.162
systemctl list-timers 'stockwatch*'
journalctl -u stockwatch-ingest -n 100 --no-pager      # last ingest log
sh ~/stockwatch/deploy/oracle/ingest.sh --now          # load right away
cd ~/supabase && docker compose ps                      # services
ssh -i <key> -L 3000:127.0.0.1:3000 ubuntu@130.210.105.162   # then http://localhost:3000 (Studio;
                                                              # DASHBOARD_USERNAME/PASSWORD in ~/supabase/.env)
```

Install the units (done 2026-11-22):

```bash
sudo cp ~/stockwatch/deploy/oracle/stockwatch-*.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stockwatch-ingest.timer stockwatch-backup.timer
```

Free-tier caveats: Oracle may reclaim an Always Free instance that stays idle (upgrading the account to
Pay As You Go, still free within the limits, avoids that). Backups live on the same disk.
