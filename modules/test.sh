#!/bin/bash

set -e

cd "$(git rev-parse --show-toplevel)"

./dev module-tests -q "$@"
