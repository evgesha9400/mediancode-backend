from aws_cdk import (
    Stack,
    Tags,
    aws_ec2 as ec2,
    aws_ssm as ssm,
)
from constructs import Construct


class NetworkStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        az_count: int,
        nat_gateways: int,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        Tags.of(self).add("env", env_name)
        Tags.of(self).add("managed-by", "median-code")

        vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name=f"{env_name}-vpc",
            max_azs=az_count,
            nat_gateways=nat_gateways,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="App",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Db",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        ssm_prefix = f"/{env_name}/platform"

        ssm.StringParameter(
            self,
            "VpcIdParam",
            parameter_name=f"{ssm_prefix}/vpc-id",
            string_value=vpc.vpc_id,
        )

        ssm.StringParameter(
            self,
            "PublicSubnetIdsParam",
            parameter_name=f"{ssm_prefix}/public-subnet-ids",
            string_value=",".join(
                [s.subnet_id for s in vpc.public_subnets]
            ),
        )

        ssm.StringParameter(
            self,
            "AppSubnetIdsParam",
            parameter_name=f"{ssm_prefix}/app-subnet-ids",
            string_value=",".join(
                [s.subnet_id for s in vpc.private_subnets]
            ),
        )

        ssm.StringParameter(
            self,
            "DbSubnetIdsParam",
            parameter_name=f"{ssm_prefix}/db-subnet-ids",
            string_value=",".join(
                [s.subnet_id for s in vpc.isolated_subnets]
            ),
        )
