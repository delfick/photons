#!/bin/bash

set -e

export TESTS_CHDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd $TESTS_CHDIR
../tools/venv tests -q $@
