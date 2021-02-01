#!/bin/bash

set -e

LOGLEVEL=${CELERY_LOGLEVEL:-INFO}

echo "Starting celery worker"
celery worker \
    --app archiefvernietigingscomponent \
    -l $LOGLEVEL \
    --workdir src \
    -O fair \
