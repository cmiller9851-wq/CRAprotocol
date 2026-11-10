# CRA Staging Kubernetes Deployment — Runbook

## Prerequisites

- `kubectl` configured against your staging cluster (`kubectl get nodes`)
- `docker` to build/push the image (or a CI pipeline doing it)
- Optional: `MAPBOX_ACCESS_TOKEN` for real routing data

## 1. Build and push the image

```bash
docker build -t ghcr.io/cmiller9851-wq/cra-supervisor:staging -f deploy/Dockerfile .
docker push ghcr.io/cmiller9851-wq/cra-supervisor:staging
```

If your registry is private, create an imagePullSecret first:
```bash
kubectl -n cra-staging create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io --docker-username=<USER> --docker-password=<PAT>
```

## 2. Optional: Mapbox token secret

```bash
kubectl create namespace cra-staging
kubectl -n cra-staging create secret generic cra-secrets \
  --from-literal=MAPBOX_ACCESS_TOKEN="pk.eyJ..."
```
(If omitted, the runtime falls back to haversine synthetic matrices automatically.)

## 3. Apply manifests

```bash
kubectl apply -f deploy/k8s/manifests.yaml
kubectl -n cra-staging rollout status deployment/cra-supervisor-runtime --timeout=120s
```

## 4. Verify

```bash
kubectl -n cra-staging get pods -o wide
curl -fs http://$(kubectl -n cra-staging get svc cra-supervisor-runtime -o jsonpath='{.spec.clusterIP}')/health
```

## 5. Run the load test

**From a machine outside the cluster (port-forward):**
```bash
kubectl -n cra-staging port-forward svc/cra-supervisor-runtime 8000:80 &
PF_PID=$!
python scripts/load_test_k8s.py --url http://127.0.0.1:8000 --concurrency 50 --duration 60
kill $PF_PID
```

**Watch the HPA scale under load (in another terminal):**
```bash
kubectl -n cra-staging get hpa -w
```

## 6. Interpreting results

- **Throughput target:** 300–800 req/s per pod (200ms p95) under mixed telemetry + matrix load
- **Scale behavior:** HPA adds pods when avg CPU utilization crosses 70% (2 → up to 10 pods)
- **Degradation signals:** HTTP 503 from `/health` → pods saturated, check `kubectl top pods`

## 7. Teardown

```bash
kubectl delete namespace cra-staging
```
