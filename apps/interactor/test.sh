#!/bin/bash

set -e

cd "$(git rev-parse --show-toplevel)"

./dev interactor-tests -q "$@" -o "default_alt_async_timeout=10"
