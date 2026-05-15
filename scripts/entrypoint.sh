#!/bin/bash
set -e
INTERVAL=${CRON_INTERVAL:-5}
echo "*/$INTERVAL * * * * cd /app && uv run python -m src.main 2>&1" > /etc/cron.d/dashidai
chmod 0644 /etc/cron.d/dashidai
crontab /etc/cron.d/dashidai
echo "Cron job set up with interval: */$INTERVAL minutes"
exec crond -f -l 2
