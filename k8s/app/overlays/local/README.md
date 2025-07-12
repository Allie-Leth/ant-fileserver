# Local k3s Deployment

This overlay is designed for local development and testing on k3s.

## Prerequisites

1. k3s cluster running
2. MinIO deployed in `minio` namespace
3. Docker image built locally: `ant-fileserver:test`

## Setup

1. **Create namespace**:
   ```bash
   kubectl create namespace ant-local
   ```

2. **Configure secrets**:
   ```bash
   cp secrets.env.template secrets.env
   # Edit secrets.env with your MinIO credentials
   ```

3. **Build local image**:
   ```bash
   docker build -f Dockerfile.test -t ant-fileserver:test .
   ```

4. **Deploy**:
   ```bash
   kubectl apply -k .
   ```

## Features

- NetworkPolicy disabled for easier debugging
- Debug logging enabled
- Connects to cluster MinIO instance
- No ingress (use port-forward for testing)

## Testing

```bash
# Check deployment
kubectl -n ant-local get pods

# View logs
kubectl -n ant-local logs -l app=ant-fileserver

# Port forward
kubectl -n ant-local port-forward svc/ant-fileserver 8080:80

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

## Cleanup

```bash
kubectl delete namespace ant-local
```