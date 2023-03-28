## kube-workload-restarter

[![Publish](https://github.com/andreacioni/kube-workload-restarter/actions/workflows/main.yml/badge.svg)](https://github.com/andreacioni/kube-workload-restarter/actions/workflows/main.yml) [![Artifact Hub](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/kube-workload-restarter)](https://artifacthub.io/packages/search?repo=kube-workload-restarter)

`kube-workload-restarter` is a small utility to be deployed in your Kubernetes namespace that is able to restart your workloads based on some conditions.

### Workloads

When we talk about [workloads](https://kubernetes.io/docs/concepts/workloads/)we are referring to the following resources:

- Deployment
- StatefulSet
- DaemonSet
- Job & CronJob

> Even if the idea behind `kube-workload-restarter` could be applied to all of this resource, **currently only Deployment workloads are supported**.

## Install

To install `kube-workload-restarter` in your namespace you can use Helm:

```bash
helm repo add kube-workload-restarter https://andreacioni.github.io/kube-workload-restarter/

helm install kube-workload-restarter kube-workload-restarter/kube-workload-restarter --version <latest_version_here>
```

## How to use it

`kube-workload-restarter` works by checking restart conditions by checking annotations on Deployments.

Currently supported annotations are:

- `restarter/after`: specify _after_ how much time your workload will be restarted
- `restarter/when`: in addition to `restarter/after` you can specify when a restart should happen. **This annotation alone has no effect**.

You can set this annotaions on your own Deployment as shown below:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  annotations:
    "restarter/after": "10d"
    "restarter/when": "* 2-3 * * 3"
spec:
  selector:
    matchLabels:
      app: nginx
  replicas: 1
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
        - name: nginx
          image: nginx:1.14.2
          ports:
            - containerPort: 80
```

## Build

```bash
docker build -t andreacioni/kube-workload-restarter:latest .
```
