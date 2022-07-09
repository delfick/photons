#!/bin/bash

set -e

export TESTS_CHDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd $TESTS_CHDIR
echo "DISABLED"
# exec ../../tools/venv tests -q $@ -o "default_alt_async_timeout=10"
