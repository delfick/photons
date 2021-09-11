#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
run_photons_core_tests -q $@ -o "default_alt_async_timeout=10"
