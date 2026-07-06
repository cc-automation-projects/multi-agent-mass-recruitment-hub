#!/bin/bash
# Production deployment script for Yandex Cloud

set -e

NAMESPACE="mass-recruit-hub"
HELM_RELEASE="mass-recruit-hub"
HELM_CHART="./infra/helm/mass-recruit-hub"
VALUES_PROD="./infra/helm/mass-recruit-hub/values-prod.yaml"

echo "Authenticating to Yandex Cloud..."
yc container registry configure-docker

TAG=$(git rev-parse --short HEAD)
docker build -t cr.yandex/crpXXXXX/mass-recruit-hub:$TAG -f Dockerfile .
docker push cr.yandex/crpXXXXX/mass-recruit-hub:$TAG

sed -i "s/tag: latest/tag: $TAG/g" $VALUES_PROD

kubectl run db-migrate --image=cr.yandex/crpXXXXX/mass-recruit-hub:$TAG --restart=Never --command -- alembic upgrade head
kubectl wait --for=condition=complete job/db-migrate --timeout=300s
kubectl delete job db-migrate

helm upgrade --install $HELM_RELEASE $HELM_CHART \
  --namespace $NAMESPACE --create-namespace \
  --values $VALUES_PROD \
  --set image.tag=$TAG

kubectl rollout status deployment -n $NAMESPACE -w

echo "Deployment completed. Check pods: kubectl get pods -n $NAMESPACE"
