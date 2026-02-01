# Infrastructure - AWS CDK

ECS Fargate deployment for the Median Code Backend.

## Prerequisites

- AWS CLI configured with credentials
- Python 3.13+
- CDK CLI (`npm install -g aws-cdk`)

## Setup

```bash
# Install CDK dependencies
make cdk-install

# Or manually
cd infra && pip install -r requirements.txt
```

## Commands

```bash
# Preview changes
make cdk-diff

# Deploy to AWS
make cdk-deploy

# Destroy all resources (clean removal)
make cdk-destroy

# Generate CloudFormation template
make cdk-synth
```

## Resources Created

- ECS Cluster (Fargate)
- Application Load Balancer (public)
- Fargate Service (256 CPU / 512 MB)
- CloudWatch Log Group

## Configuration

All resources are configured with `RemovalPolicy.DESTROY` - stack deletion removes everything completely.

Modify `stacks/backend_stack.py` to adjust:
- CPU/Memory allocation
- Desired container count
- Auto-scaling thresholds
- Environment variables

## First Deploy

```bash
# Bootstrap CDK (one-time per account/region)
cd infra && cdk bootstrap

# Deploy
make cdk-deploy
```

The ALB URL will be shown in the outputs after deployment.
