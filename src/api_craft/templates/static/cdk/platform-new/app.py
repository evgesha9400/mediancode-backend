#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.network import NetworkStack

app = cdk.App()

env_name = app.node.try_get_context("env") or "dev"

# Always 2 AZs (RDS requires subnets in >= 2 AZs). Prod: 2 NATs, dev: 1 NAT.
az_count = 2
nat_gateways = 2 if env_name == "prod" else 1

NetworkStack(
    app,
    f"{env_name}-platform",
    env_name=env_name,
    az_count=az_count,
    nat_gateways=nat_gateways,
)

app.synth()
