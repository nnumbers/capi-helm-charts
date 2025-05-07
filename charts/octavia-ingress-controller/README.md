# Octavia Ingress Controller

![Version: 0.0.1](https://img.shields.io/badge/Version-0.0.1-informational?style=flat-square) ![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square) ![AppVersion: v1.32.0](https://img.shields.io/badge/AppVersion-v1.32.0-informational?style=flat-square)


This Helm chart deploys the [Octavia Ingress Controller](https://github.com/kubernetes/cloud-provider-openstack/blob/master/docs/octavia-ingress-controller/using-octavia-ingress-controller.md) as a Cluster API add-on for Kubernetes clusters on OpenStack.

## Prerequisites

- Cluster API management cluster with Cluster API Provider for OpenStack (CAPO) installed.
- Cluster API Addon Provider installed (`helm install cluster-api-addon-provider capi-addons/cluster-api-addon-provider`).
- An `OpenStackCluster` resource with `spec.identityRef` pointing to a `Secret` containing `clouds.yaml`.
- OpenStack Octavia and Barbican services enabled for load balancer and TLS support.

## Installation

```bash
helm repo add capi https://<nnumbers-helm-repo>/capi-helm-charts
helm install octavia-ingress capi/octavia-ingress-controller --namespace default --set clusterName=example
```

## Configuration
| Key | Type | Description | Default |
|-----|------|-------------|---------|
| `image.repository` | string | Image repository |  `registry.k8s.io/provider-os/octavia-ingress-controller` |
| `image.tag` | string | Image tag | `v1.32.0` |
| `secretName` | string | Name of the configuration Secret | `octavia-ingress-controller-config` |
| `namespace` | Namespace for deployment | `openstack-system` |
| `octavia.manageSecurityGroups` | bool | Enable security group management | `true` |
| `octavia.flavorId` | string | Octavia flavor ID | `""` |
| `octavia.provider` | string | Octavia provider | `""` |
| `clusterName` | string | Target Cluster API cluster name | `""` |

| `affinity` | object | affinity for scheduler pod assignment | `{}` |
| `debug` | bool | show debug logs | `false` |
| `fullnameOverride` | string | full name of the chart. | `""` |
| `image.pullPolicy` | string | image pull policy | `"IfNotPresent"` |
| `imagePullSecrets` | list | image pull secret for private images | `[]` |
| `nameOverride` | string | override name of the chart | `""` |
| `nodeSelector` | object | node for scheduler pod assignment | `{}` |
| `podSecurityContext` | object | specifies security settings for a pod | `{}` |
| `resources` | object | custom resource configuration | `{}` |
| `securityContext` | object | specifies security settings for a container | `{}` |
| `rbac.annotations` | object | annotations to add to the RBACs | `{}` |
| `rbac.create` | bool | specifies whether the RBACs should be created | `true` |
| `rbac.serviceAccount.name` | string | the name of the service account to use; if not set and create is true, a name is generated using the fullname template | `nil` |
| `tolerations` | list | tolerations for scheduler pod assignment | `[]` |


## Dynamic Values

The chart uses the Cluster API Addon Provider to source:
- OpenStack credentials from `cloud_identity.data.clouds_yaml`.
- Subnet ID from `openstack_cluster.status.network.subnet.id`.
- Network ID from `openstack_cluster.status.network.id`.
- Floating IP ID from `openstack_cluster.status.apiServerFloatingIP.id`.

## Usage

Create an Ingress resource with the `openstack` ingress class:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: test-ingress
  namespace: default
  annotations:
    kubernetes.io/ingress.class: "openstack"
spec:
  rules:
  - host: api.sample.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-service
            port:
              number: 8080
```