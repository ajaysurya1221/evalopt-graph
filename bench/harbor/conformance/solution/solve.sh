#!/bin/bash
set -euo pipefail
mkdir -p /logs/artifacts
printf '%s\n' 'kernel adapter ready' > /logs/artifacts/done.txt
