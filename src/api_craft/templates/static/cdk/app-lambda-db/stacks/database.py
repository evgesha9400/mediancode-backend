from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager,
    aws_ssm as ssm,
)
from constructs import Construct


class DatabaseStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        project_name: str,
        env_name: str,
        db_instance_class: str,
        db_multi_az: bool,
        db_removal_policy: RemovalPolicy,
        backup_retention_days: int,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        Tags.of(self).add("project", project_name)
        Tags.of(self).add("env", env_name)
        Tags.of(self).add("managed-by", "median-code")
        Tags.of(self).add("naming-version", "v1")

        prefix = f"{env_name}-{project_name}"
        self.db_name = project_name.replace("-", "_")
        ssm_prefix = f"/{env_name}/platform"

        vpc_id = ssm.StringParameter.value_from_lookup(self, f"{ssm_prefix}/vpc-id")
        vpc = ec2.Vpc.from_lookup(self, "Vpc", vpc_id=vpc_id)
        db_subnet_ids = ssm.StringParameter.value_from_lookup(
            self, f"{ssm_prefix}/db-subnet-ids"
        ).split(",")
        db_subnets = [
            ec2.Subnet.from_subnet_id(self, f"DbSubnet{i}", sid)
            for i, sid in enumerate(db_subnet_ids)
        ]

        self.security_group = ec2.SecurityGroup(
            self,
            "DbSg",
            vpc=vpc,
            security_group_name=f"{prefix}-db-sg",
            description="Security group for RDS PostgreSQL",
        )

        # Lambda SG lives here to avoid cross-stack circular dependency
        self.lambda_security_group = ec2.SecurityGroup(
            self,
            "LambdaSg",
            vpc=vpc,
            security_group_name=f"{prefix}-lambda-sg",
            description="Security group for Lambda functions",
        )

        self.security_group.add_ingress_rule(
            peer=self.lambda_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow Lambda to connect to RDS",
        )

        self.secret = secretsmanager.Secret(
            self,
            "DbSecret",
            secret_name=f"{prefix}/db-credentials",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "postgres"}',
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=30,
            ),
        )

        _, family, size = db_instance_class.split(".")
        instance_type = ec2.InstanceType.of(
            getattr(ec2.InstanceClass, family.upper()),
            getattr(ec2.InstanceSize, size.upper()),
        )

        self.instance = rds.DatabaseInstance(
            self,
            "Database",
            instance_identifier=f"{prefix}-db",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16,
            ),
            instance_type=instance_type,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=db_subnets),
            security_groups=[self.security_group],
            database_name=self.db_name,
            credentials=rds.Credentials.from_secret(self.secret),
            multi_az=db_multi_az,
            allocated_storage=20,
            max_allocated_storage=100,
            storage_encrypted=True,
            backup_retention=Duration.days(backup_retention_days),
            removal_policy=db_removal_policy,
            deletion_protection=env_name == "prod",
        )

        ssm.StringParameter(
            self,
            "SecretArnParam",
            parameter_name=f"/{env_name}/{project_name}/db-secret-arn",
            string_value=self.secret.secret_arn,
        )

        ssm.StringParameter(
            self,
            "EndpointParam",
            parameter_name=f"/{env_name}/{project_name}/db-endpoint",
            string_value=self.instance.db_instance_endpoint_address,
        )

    def get_database_url_env(self) -> dict:
        host = self.instance.db_instance_endpoint_address
        port = self.instance.db_instance_endpoint_port
        return {
            "DATABASE_URL": f"postgresql+asyncpg://postgres:{{{{resolve:secretsmanager:{self.secret.secret_arn}:SecretString:password}}}}@{host}:{port}/{self.db_name}"
        }

