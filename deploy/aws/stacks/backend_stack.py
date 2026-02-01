"""ECS Fargate stack for deploying the backend API."""

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_logs as logs,
)
from constructs import Construct


class BackendStack(Stack):
    """Deploy backend API to ECS Fargate with minimal resources.

    Uses the default VPC and creates a single Fargate container with an ALB.
    All resources are configured for complete removal on stack destroy.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Use the default VPC
        vpc = ec2.Vpc.from_lookup(self, "DefaultVpc", is_default=True)

        # Create ECS cluster
        cluster = ecs.Cluster(
            self,
            "BackendCluster",
            vpc=vpc,
            cluster_name="median-code-backend",
            container_insights_v2=ecs.ContainerInsights.DISABLED,
        )

        # Create log group with removal policy
        log_group = logs.LogGroup(
            self,
            "BackendLogGroup",
            log_group_name="/ecs/median-code-backend",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create Fargate service with ALB
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "BackendService",
            cluster=cluster,
            # Minimal Fargate resources (smallest allowed)
            cpu=256,  # 0.25 vCPU
            memory_limit_mib=512,  # 512 MB
            desired_count=1,
            # Build from Dockerfile in project root
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset(".."),
                container_port=80,
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="backend",
                    log_group=log_group,
                ),
                environment={
                    "ENVIRONMENT": "production",
                },
            ),
            # Public ALB
            public_load_balancer=True,
            # Health check
            health_check_grace_period=Duration.seconds(60),
        )

        # Configure health check
        fargate_service.target_group.configure_health_check(
            path="/health",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(5),
        )

        # Enable removal of all resources on stack destroy
        # ALB and related resources
        fargate_service.load_balancer.apply_removal_policy(RemovalPolicy.DESTROY)

        # Service auto-scaling (optional, minimal config)
        scaling = fargate_service.service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=2,
        )
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )
