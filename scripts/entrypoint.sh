#!/bin/bash

set -e

# Read cron.template and substitute CRON_INTERVAL
CRON_INTERVAL=${CRON_INTERVAL:-5}
sed "s|{CRON_INTERVAL}|$CRON_INTERVAL|g" /app/cron.template > /etc/cron.d/nga
chmod 0644 /etc/cron.d/nga
crontab /etc/cron.d/nga

echo "Cron jobs configured:"
crontab -l

exec cron -f -L 2
