#!/usr/bin/env bash
set -Eeuo pipefail

# Compose file secrets are bind mounts: POSIX mode 0600 belongs to the host UID.
# Root copies them into tmpfs before the official entrypoint drops to postgres.
# Host permissions stay private; neither the image nor logs contain passwords.
if [ "$(id -u)" = '0' ]; then
  install -d -m 0700 -o postgres -g postgres /run/indexpilot-secrets
  for role in admin meta demo analyzer bench; do
    install -m 0400 -o postgres -g postgres \
      "/run/secrets/${role}_password" "/run/indexpilot-secrets/${role}_password"
  done
fi

exec /usr/local/bin/docker-entrypoint.sh "$@"
