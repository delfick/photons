#!/bin/bash

if [[ -z $1 ]]; then
  echo "Please specify command as first argument"
  exit 1
fi

ARGS=$(printf '{"command": "%s"}' "$1")
if [[ ! -z $2 ]]; then
  ARGS=$(printf '{"command": "%s", "args": %s}' "$1" "$2")
fi

curl -XPUT http://${INTERACTOR_HOST-localhost}:${INTERACTOR_PORT-6100}/v1/lifx/command \
  -HContent-Type:application/json \
  -d "$ARGS"
