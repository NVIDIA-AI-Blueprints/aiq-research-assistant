#!/bin/sh

if [ -z "$AIRA_HOSTED_NIMS" -o "$AIRA_HOSTED_NIMS" = "false" ]; then
    exec uv run aiq serve --config_file /app/configs/config.yml --host 0.0.0.0 --port 3838
else
    exec uv run aiq serve --config_file /app/configs/hosted-config.yml --host 0.0.0.0 --port 3838
fi