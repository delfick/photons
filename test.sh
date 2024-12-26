#!/bin/bash

set -e

cd "$(git rev-parse --show-toplevel)"

exec ./dev tests "$@"
