#!/bin/sh
# Nightly database dump on the Oracle server, keeping the last 7. These stay on the same disk,
# so they protect against mistakes, not against losing the server; copy one off the server now
# and then (scp ubuntu@<server>:backups/<file> .).
set -eu
mkdir -p "$HOME/backups"
file="$HOME/backups/stockwatch-$(date -u +%Y%m%d-%H%M).dump"
docker exec supabase-db pg_dump -U postgres -d postgres -Fc --schema=public --schema=private --schema=auth \
  --schema=supabase_migrations > "$file.part"
mv "$file.part" "$file"
ls -1t "$HOME"/backups/stockwatch-*.dump | tail -n +8 | xargs -r rm --
echo "backup: $file ($(du -h "$file" | cut -f1))"
