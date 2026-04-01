from aws_cdk import (
    Duration,
    Stack,
    Tags,
    aws_ec2 as ec2,
    aws_ecr_assets as ecr_assets,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_logs as logs,
    aws_ssm as ssm,
)
from constructs import Construct


class ComputeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        project_name: str,
        env_name: str,
        fargate_cpu: int,
        fargate_memory_mib: int,
        environment: dict | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        Tags.of(self).add("project", project_name)
        Tags.of(self).add("env", env_name)
        Tags.of(self).add("managed-by", "median-code")
        Tags.of(self).add("naming-version", "v1")

        prefix = f"{env_name}-{project_name}"
        ssm_prefix = f"/{env_name}/platform"

        vpc_id = ssm.StringParameter.value_from_lookup(self, f"{ssm_prefix}/vpc-id")
        vpc = ec2.Vpc.from_lookup(self, "Vpc", vpc_id=vpc_id)
        app_subnet_ids = ssm.StringParameter.value_from_lookup(
            self, f"{ssm_prefix}/app-subnet-ids"
        ).split(",")
        app_subnets = [
            ec2.Subnet.from_subnet_id(self, f"AppSubnet{i}", sid)
            for i, sid in enumerate(app_subnet_ids)
        ]
        project_root = self.node.try_get_context("project-root") or "../.."

        if env_name == "dev":
            retention = logs.RetentionDays.ONE_WEEK
        elif env_name == "stg":
            retention = logs.RetentionDays.TWO_WEEKS
        else:
            retention = logs.RetentionDays.ONE_MONTH

        api_log_group = logs.LogGroup(
            self, "ApiLogGroup",
            log_group_name=f"/{prefix}/ecs-logs",
            retention=retention,
        )

        cluster = ecs.Cluster(
            self,
            "Cluster",
            cluster_name=f"{prefix}-cluster",
            vpc=vpc,
        )

        self.fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "FargateService",
            cluster=cluster,
            service_name=f"{prefix}-ecs",
            cpu=fargate_cpu,
            memory_limit_mib=fargate_memory_mib,
            desired_count=1,
            task_subnets=ec2.SubnetSelection(subnets=app_subnets),
            public_load_balancer=True,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset(
                    project_root,
                    platform=ecr_assets.Platform.LINUX_AMD64,
                ),
                container_port=80,
                environment=environment or {},
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="api",
                    log_group=api_log_group,
                ),
            ),
            health_check_grace_period=Duration.seconds(60),
        )

        self.fargate_service.target_group.configure_health_check(
            path="/health",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(5),
        )

        self.security_group = (
            self.fargate_service.service.connections.security_groups[0]
        )

        ssm.StringParameter(
            self,
            "ApiUrlParam",
            parameter_name=f"/{env_name}/{project_name}/api-url",
            string_value=f"http://{self.fargate_service.load_balancer.load_balancer_dns_name}",
        )
