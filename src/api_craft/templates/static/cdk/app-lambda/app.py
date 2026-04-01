#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.compute import ComputeStack

app = cdk.App()

env_name = app.node.try_get_context("env") or "dev"
project_name = app.node.try_get_context("project") or "shop-api"

lambda_memory_mib = 512 if env_name == "prod" else 256
prefix = f"{env_name}-{project_name}"

ComputeStack(
    app,
    prefix,
    project_name=project_name,
    env_name=env_name,
    lambda_memory_mib=lambda_memory_mib,
    env=cdk.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    ),
)

app.synth()
