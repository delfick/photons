#!/bin/bash

set -e

if [[ $CI != "true" ]]; then
  echo "Not on CI"
  exit 1
fi

if [[ -z $DOCKER_TOKEN ]]; then
  echo "You don't have a DOCKER_TOKEN in your environment"
  exit 1
fi

if [[ -z $DOCKER_USERNAME ]]; then
  echo "You don't have a DOCKER_USERNAME in your environment"
  exit 1
fi

_folder=$(git rev-parse --show-toplevel)/apps/interactor
cd $_folder

staging=$(mktemp -d)
cleanup() { rm -rf $staging; }
trap cleanup EXIT

cd $staging

$_folder/docker/harpoon get_docker_context lifx-photons-interactor

docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
docker buildx create --name xbuilder --use

echo "$DOCKER_TOKEN" | docker login -u "$DOCKER_USERNAME" --password-stdin
tar xf context_lifx-photons-interactor.tar
export TAG=$(python -c 'print(__import__("runpy").run_path("apps/interactor/interactor/__init__.py")["VERSION"])')

docker buildx build --progress plain --platform $DOCKER_PLATFORM --push -t ${TARGET_IMAGE}:${TAG} -t ${TARGET_IMAGE}:latest .
