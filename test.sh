#!/bin/bash
unset HARDCODED_DISCOVERY
unset SERIAL_FILTER
nosetests --with-noy $@
