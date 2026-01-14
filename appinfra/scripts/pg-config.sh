#!/usr/bin/env bash
# Outputs Make variable assignments for PG config
# Usage: pg-config.sh <config_file> <config_key> <etc_dir> <default_config_file>
# Output: Pipe-separated Make assignments for $(eval $(subst |,$(newline),...))
#
# If config_file is empty, uses default_config_file
# All filenames are resolved from etc_dir

CONFIG_FILE="$1"
CONFIG_KEY="$2"
ETC_DIR="$3"
DEFAULT_CONFIG_FILE="$4"

# Use default if config file not specified
if [ -z "$CONFIG_FILE" ]; then
    CONFIG_FILE="$DEFAULT_CONFIG_FILE"
fi

# Resolve full path
FULL_PATH="$ETC_DIR/$CONFIG_FILE"

# Check if file exists
if [ ! -f "$FULL_PATH" ]; then
    echo "PG_DOCKER_IMAGE:=|PG_VERSION:=|PG_PORT:=|PG_IMAGE:=|PG_REPLICA_ENABLED:=false|PG_PORT_R:=|PG_COMMAND:=postgres"
    exit 0
fi

python3 -c "
import yaml

# SafeLoader that ignores unknown tags (e.g., !include)
class SafeLoaderIgnoreUnknown(yaml.SafeLoader):
    pass
SafeLoaderIgnoreUnknown.add_constructor(None, lambda loader, node: None)

with open('$FULL_PATH') as f:
    cfg = yaml.load(f, Loader=SafeLoaderIgnoreUnknown).get('$CONFIG_KEY', {})

replica = cfg.get('replica', {})
replica_enabled = str(replica.get('enabled', False)).lower()
replica_port = replica.get('port', '')

# Build postgres command from config
postgres_conf = cfg.get('postgres_conf', {})
postgres_conf_file = cfg.get('postgres_conf_file', '')

cmd_parts = ['postgres']

# Add config file if specified
if postgres_conf_file:
    cmd_parts.extend(['-c', f'config_file={postgres_conf_file}'])

# Add individual config params (these override config file settings)
for key, value in postgres_conf.items():
    # Convert Python types to postgres format
    if isinstance(value, bool):
        value = 'on' if value else 'off'
    elif isinstance(value, list):
        value = ','.join(str(v) for v in value)
    cmd_parts.extend(['-c', f'{key}={value}'])

pg_command = ' '.join(cmd_parts)

# Output Make variable assignments (pipe-separated, converted to newlines by Makefile)
parts = [
    f'PG_DOCKER_IMAGE:={cfg.get(\"name\", \"\")}',
    f'PG_VERSION:={cfg.get(\"version\", \"\")}',
    f'PG_PORT:={cfg.get(\"port\", \"\")}',
    f'PG_IMAGE:={cfg.get(\"image\", \"\")}',
    f'PG_REPLICA_ENABLED:={replica_enabled}',
    f'PG_PORT_R:={replica_port}',
    f'PG_COMMAND:={pg_command}',
]
print('|'.join(parts))
"
