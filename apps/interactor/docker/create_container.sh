#!/bin/bash

set -e

if [[ $CI != "true" ]]; then
    echo "Not on CI"
    exit 0
fi

_folder=$(git rev-parse --show-toplevel)/apps/interactor
cd $_folder

_found=0
for tag in $(git tag --points-at HEAD); do
    if [[ $tag =~ "interactor-" ]]; then
        _found=1
    fi
done
if (($_found == 0)); then
    echo "This commit is not an interactor tag, exiting"
    exit 0
fi

echo "This is an interactor tag, will build the container"

staging=$(mktemp -d)
cleanup() { rm -rf $staging; }
trap cleanup EXIT

cd $staging
pip3 install venvstarter

$_folder/docker/harpoon get_docker_context lifx-photons-interactor

curl -fsSL https://get.docker.com | sh
echo '{"experimental":"enabled"}' | sudo tee /etc/docker/daemon.json
mkdir -p $HOME/.docker
echo '{"experimental":"enabled"}' | sudo tee $HOME/.docker/config.json
sudo service docker start

docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
docker buildx create --name xbuilder --use

echo "$DOCKER_TOKEN" | docker login -u "$DOCKER_USERNAME" --password-stdin
tar xf context_lifx-photons-interactor.tar
export TAG=$(python -c 'print(__import__("runpy").run_path("apps/interactor/interactor/__init__.py")["VERSION"])')

docker buildx build --progress plain --platform $DOCKER_PLATFORM --push -t ${TARGET_IMAGE}:${TAG} -t ${TARGET_IMAGE}:latest .
