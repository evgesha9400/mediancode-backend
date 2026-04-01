#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.compute import ComputeStack

app = cdk.App()

env_name = app.node.try_get_context("env") or "dev"
project_name = app.node.try_get_context("project") or "shop-api"

prefix = f"{env_name}-{project_name}"

# Dev/prod config
is_prod = env_name == "prod"
fargate_cpu = 512 if is_prod else 256
fargate_memory_mib = 1024 if is_prod else 512

ComputeStack(
    app,
    prefix,
    project_name=project_name,
    env_name=env_name,
    fargate_cpu=fargate_cpu,
    fargate_memory_mib=fargate_memory_mib,
    env=cdk.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    ),
)

app.synth()
