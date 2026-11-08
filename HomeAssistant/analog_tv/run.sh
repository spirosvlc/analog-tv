#!/usr/bin/with-contenv bashio
set -eu

export ANALOG_LAN_ADMIN=true
export ANALOG_ALLOW_ADMIN_SETUP=false
if bashio::config.true 'allow_admin_setup'; then
  export ANALOG_ALLOW_ADMIN_SETUP=true
fi
export FORWARDED_ALLOW_IPS=""
export ANALOG_DATABASE_URL="sqlite:////config/analog_tv.db"
export ANALOG_HOST="0.0.0.0"
export ANALOG_PORT="8080"
export ANALOG_LOG_LEVEL="$(bashio::config 'log_level')"

echo "[Analog TV] Starting Home Assistant app"
echo "[Analog TV] SQLite: /config/analog_tv.db"
echo "[Analog TV] Host mapping: /addon_configs/local_analog_tv/analog_tv.db"
echo "[Analog TV] /media and /share mapped; host port 8155 / internal port 8080"

if [ ! -d /config ] || [ ! -w /config ]; then
  echo "[Analog TV] ERROR: writable addon_config mapping is required."
  exit 1
fi

if [ -e /config/analog_tv.db ]; then
  echo "[Analog TV] Existing database found"
  if [ ! -w /config/analog_tv.db ]; then
    echo "[Analog TV] ERROR: database exists but is not writable."
    ls -l /config/analog_tv.db
    exit 1
  fi
else
  echo "[Analog TV] No database found; a new one will be created. Restore your backup before starting if migrating."
fi

cd /opt/analog_tv
exec python3 -m analog_tv.main
