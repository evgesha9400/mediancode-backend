#!/usr/bin/env python3
import os

import aws_cdk as cdk
from aws_cdk import RemovalPolicy
from stacks.compute import ComputeStack
from stacks.database import DatabaseStack

app = cdk.App()

env_name = app.node.try_get_context("env") or "dev"
project_name = app.node.try_get_context("project") or "shop-api"

prefix = f"{env_name}-{project_name}"

aws_env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"],
    region=os.environ["CDK_DEFAULT_REGION"],
)

# Dev/prod config
is_prod = env_name == "prod"
lambda_memory_mib = 512 if is_prod else 256
db_instance_class = "db.t4g.small" if is_prod else "db.t4g.micro"
db_multi_az = is_prod
db_removal_policy = RemovalPolicy.SNAPSHOT if is_prod else RemovalPolicy.DESTROY
if env_name == "prod":
    backup_retention_days = 35
elif env_name == "stg":
    backup_retention_days = 14
else:
    backup_retention_days = 7

# Database
db_stack = DatabaseStack(
    app,
    f"{prefix}-db",
    project_name=project_name,
    env_name=env_name,
    db_instance_class=db_instance_class,
    db_multi_az=db_multi_az,
    db_removal_policy=db_removal_policy,
    backup_retention_days=backup_retention_days,
    env=aws_env,
)

# Compute
compute_stack = ComputeStack(
    app,
    prefix,
    project_name=project_name,
    env_name=env_name,
    lambda_memory_mib=lambda_memory_mib,
    environment=db_stack.get_database_url_env(),
    security_group=db_stack.lambda_security_group,
    env=aws_env,
)

# Compute depends on database (needs DATABASE_URL + security group)
compute_stack.add_dependency(db_stack)

app.synth()
