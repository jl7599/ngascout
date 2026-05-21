#!/bin/bash

set -e
INTERVAL=${CRON_INTERVAL:-5}
echo "*/$INTERVAL * * * * cd /app && /usr/local/bin/uv run python -m src.main >> /proc/1/fd/1 2>> /proc/1/fd/2" > /etc/cron.d/nga
chmod 0644 /etc/cron.d/nga
crontab /etc/cron.d/nga

echo "Cron job set up:"
crontab -l

exec cron -f -L 2
