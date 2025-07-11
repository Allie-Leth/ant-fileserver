# Harbor Self-Hosted Registry Migration Roadmap

## Overview

Strategic roadmap for migrating from GitHub Container Registry (GHCR) to self-hosted Harbor registry for complete infrastructure autonomy and cost optimization.

## Current State vs Target State

### Current: GitHub Container Registry
- **Cost**: Free tier (500 MB storage, 1 GB bandwidth/month)
- **Location**: External (github.com)
- **Control**: Limited (GitHub platform dependency)
- **Features**: Basic registry with security scanning

### Target: Self-Hosted Harbor
- **Cost**: Infrastructure only (~$5-10/month for small VPS)
- **Location**: Self-hosted on k3s cluster or dedicated instance
- **Control**: Full control over features, policies, retention
- **Features**: Advanced registry with vulnerability scanning, content trust, replication

## Migration Timeline

### Phase 1: Research & Planning (Month 1)
**Duration**: 2-3 weeks  
**Priority**: Low (background research)

#### Week 1-2: Harbor Evaluation
- [ ] **Research Harbor deployment options**
  - Kubernetes Helm chart deployment
  - Docker Compose standalone
  - Harbor Operator for k3s
- [ ] **Evaluate hardware requirements**
  - Storage needs (estimate: 10-50 GB for multiple projects)
  - CPU/Memory requirements
  - Network bandwidth considerations
- [ ] **Cost-benefit analysis**
  - Infrastructure costs vs GHCR overage fees
  - Operational overhead vs control benefits

#### Week 3: Architecture Design
- [ ] **Design Harbor deployment architecture**
  - Integration with existing k3s cluster vs separate instance
  - Storage backend (Longhorn integration)
  - SSL/TLS with cert-manager integration
  - Backup and disaster recovery strategy
- [ ] **Security planning**
  - Access control and RBAC design
  - Integration with existing authentication (if applicable)
  - Network security and ingress configuration

### Phase 2: Infrastructure Preparation (Month 2)
**Duration**: 1-2 weeks  
**Priority**: Medium (when approaching GHCR limits)

#### Week 1: Environment Setup
- [ ] **Prepare Harbor deployment environment**
  - Allocate dedicated namespace or infrastructure
  - Configure persistent storage (minimum 20 GB)
  - Set up DNS and ingress configuration
- [ ] **Install Harbor**
  - Deploy via Helm chart or Harbor Operator
  - Configure with cert-manager for TLS
  - Set up basic authentication and access controls

#### Week 2: Integration & Testing
- [ ] **Configure Harbor features**
  - Enable vulnerability scanning (Trivy integration)
  - Set up retention policies
  - Configure webhooks and notifications
- [ ] **Test Harbor functionality**
  - Push/pull test images
  - Validate security scanning
  - Test access controls and permissions

### Phase 3: Migration Implementation (Month 2-3)
**Duration**: 1 week  
**Priority**: High (when ready to migrate)

#### Migration Execution
- [ ] **Prepare migration scripts**
  - Create image migration utilities
  - Update CI/CD pipelines for dual-push (GHCR + Harbor)
  - Prepare Kubernetes manifest updates
- [ ] **Execute parallel operation**
  - Configure CI/CD to push to both registries
  - Validate all images available in Harbor
  - Test deployments using Harbor images
- [ ] **Cutover execution**
  - Update Kubernetes manifests to use Harbor
  - Update CI/CD to push only to Harbor
  - Validate production deployments

### Phase 4: Optimization & Cleanup (Month 3)
**Duration**: 1 week  
**Priority**: Low (maintenance)

#### Post-Migration Tasks
- [ ] **Optimize Harbor configuration**
  - Fine-tune retention policies
  - Configure automated cleanup
  - Set up monitoring and alerting
- [ ] **Documentation and training**
  - Document Harbor operations procedures
  - Create troubleshooting guides
  - Train team on Harbor management
- [ ] **GHCR cleanup**
  - Archive/delete old images from GHCR
  - Update documentation references
  - Remove GHCR authentication from CI/CD

## Implementation Details

### Harbor Deployment Configuration

#### Recommended Helm Values
```yaml
# harbor-values.yaml
expose:
  type: ingress
  tls:
    enabled: true
    certSource: secret
  ingress:
    hosts:
      core: registry.scopecreep.productions
    className: nginx
    annotations:
      cert-manager.io/cluster-issuer: "letsencrypt-prod"

persistence:
  enabled: true
  resourcePolicy: "keep"
  persistentVolumeClaim:
    registry:
      size: 50Gi
      storageClass: longhorn
    chartmuseum:
      size: 5Gi
      storageClass: longhorn

trivy:
  enabled: true
  
notary:
  enabled: false  # Enable later for content trust

database:
  type: internal
  
redis:
  type: internal
```

#### Storage Requirements
- **Registry Storage**: 50 GB (expandable with Longhorn)
- **Database**: 5 GB for metadata
- **Chart Museum**: 5 GB for Helm charts (optional)
- **Total**: ~60 GB initial allocation

### Migration Scripts

#### Dual-Push CI/CD Configuration
```yaml
# GitHub Actions example
- name: Build and push to registries
  run: |
    # Build image
    docker build -t ant-fileserver:${{ github.sha }} .
    
    # Push to GHCR (current)
    docker tag ant-fileserver:${{ github.sha }} ghcr.io/allie-leth/ant-fileserver:${{ github.sha }}
    docker push ghcr.io/allie-leth/ant-fileserver:${{ github.sha }}
    
    # Push to Harbor (new)
    docker tag ant-fileserver:${{ github.sha }} registry.scopecreep.productions/ant-fileserver:${{ github.sha }}
    docker push registry.scopecreep.productions/ant-fileserver:${{ github.sha }}
```

#### Image Migration Script
```bash
#!/bin/bash
# migrate-images.sh
SOURCE_REGISTRY="ghcr.io/allie-leth"
TARGET_REGISTRY="registry.scopecreep.productions"

for repo in ant-fileserver; do
  for tag in latest dev $(git tag); do
    echo "Migrating ${repo}:${tag}"
    docker pull ${SOURCE_REGISTRY}/${repo}:${tag}
    docker tag ${SOURCE_REGISTRY}/${repo}:${tag} ${TARGET_REGISTRY}/${repo}:${tag}
    docker push ${TARGET_REGISTRY}/${repo}:${tag}
  done
done
```

### Security Considerations

#### Harbor Security Features
- **Vulnerability Scanning**: Integrated Trivy scanner
- **Content Trust**: Docker Notary integration (optional)
- **Access Control**: RBAC with project-based permissions
- **Image Signing**: Support for cosign integration
- **Webhook Integration**: Automated security notifications

#### Network Security
- **TLS Termination**: cert-manager integration
- **Network Policies**: Restrict access to Harbor services
- **Ingress Security**: WAF and rate limiting via ingress-nginx
- **Backup Encryption**: Encrypted backups of Harbor data

## Cost Analysis

### Current GHCR Costs
- **Free Tier**: 500 MB storage, 1 GB bandwidth/month
- **Projected Growth**: $2-5/month after 6 months

### Harbor Infrastructure Costs
- **Storage**: Included in existing Longhorn cluster
- **Compute**: Minimal overhead on existing k3s nodes
- **Bandwidth**: No external charges (self-hosted)
- **Total**: $0 additional infrastructure cost

### Operational Benefits
- **Independence**: No vendor lock-in or external dependencies
- **Control**: Full control over retention, policies, features
- **Integration**: Deep integration with existing infrastructure
- **Compliance**: Data sovereignty and control

## Risk Assessment & Mitigation

### Risks
- **Operational Overhead**: Managing Harbor instance
- **Backup Complexity**: Additional backup requirements
- **Upgrade Management**: Regular Harbor updates needed

### Mitigation Strategies
- **Automation**: Automated backup and monitoring
- **Documentation**: Comprehensive operational procedures
- **Staged Migration**: Parallel operation during transition
- **Rollback Plan**: Ability to revert to GHCR if needed

## Success Metrics

### Technical Metrics
- **Image Pull Performance**: < 30s for typical container images
- **Uptime**: > 99.5% availability
- **Storage Utilization**: Efficient use of allocated storage
- **Security Coverage**: 100% vulnerability scanning coverage

### Operational Metrics
- **Cost Reduction**: Eliminate GHCR overage fees
- **Team Productivity**: Faster development cycles with local registry
- **Compliance**: Meet data sovereignty requirements

## Decision Points

### Trigger for Migration
- **GHCR costs exceed $10/month** consistently
- **Need for advanced registry features** (replication, advanced RBAC)
- **Compliance requirements** for data sovereignty
- **Integration benefits** outweigh operational overhead

### Go/No-Go Criteria
- **Infrastructure Capacity**: Sufficient storage and compute available
- **Team Bandwidth**: Resources available for migration and ongoing management
- **Business Value**: Clear ROI from migration benefits

---

**Roadmap Status**: 📋 Planning Phase  
**Target Start**: When GHCR costs approach $5/month or advanced features needed  
**Estimated Effort**: 2-3 weeks total implementation  
**Risk Level**: Medium (manageable with proper planning)

## Next Steps

1. **Monitor GHCR usage** and costs monthly
2. **Research Harbor deployment** options for k3s
3. **Prepare infrastructure** capacity planning
4. **Execute when triggered** by cost or feature requirements

This roadmap provides a structured approach to eventual Harbor migration while maximizing the value of GHCR during early project phases.