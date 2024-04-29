#!/bin/bash

set -ex

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Install the CaaS operator from the chart we are about to ship
# Make sure to use the images that we just built
helm upgrade azimuth-schedule-operator ./charts/operator \
  --dependency-update \
  --namespace azimuth-schedule-operator \
  --create-namespace \
  --install \
  --wait \
  --timeout 10m \
  --set-string image.tag=${GITHUB_SHA::7} \
  --set-json 'managedResources=[{"apiGroup": "", "resources": ["configmaps"]}]'

until [ `kubectl get crds | grep schedules.scheduling.azimuth.stackhpc.com | wc -l` -eq 1 ]; do echo "wait for crds"; sleep 5; done
kubectl get crds


export AFTER=$(date --date="-1 hour" +"%Y-%m-%dT%H:%M:%SZ")
envsubst < $SCRIPT_DIR/test_schedule.yaml | kubectl apply -f -

kubectl wait --for=jsonpath='{.status.refExists}'=true schedule caas-mycluster
# ensure updatedAt is written out
kubectl get schedule caas-mycluster -o yaml | grep "updatedAt"
kubectl wait --for=jsonpath='{.status.refDeleteTriggered}'=true schedule caas-mycluster
kubectl get schedule caas-mycluster -o yaml

# for debugging get the logs from the operator
kubectl logs -n azimuth-schedule-operator deployment/azimuth-schedule-operator
