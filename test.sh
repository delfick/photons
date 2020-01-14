#!/bin/bash
unset HARDCODED_DISCOVERY
unset SERIAL_FILTER
run_photons_core_tests -q $@
