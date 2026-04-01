from aws_cdk import (
    BundlingOptions,
    BundlingOutput,
    Duration,
    Stack,
    Tags,
    aws_apigatewayv2 as apigwv2,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_ssm as ssm,
)
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from constructs import Construct


class ComputeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        project_name: str,
        env_name: str,
        lambda_memory_mib: int,
        environment: dict,
        security_group: ec2.ISecurityGroup,
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

        bundling = BundlingOptions(
            image=lambda_.Runtime.PYTHON_3_13.bundling_image,
            command=[
                "bash", "-c",
                "pip install poetry poetry-plugin-export && "
                "poetry export -f requirements.txt --without-hashes -o /tmp/requirements.txt && "
                "pip install -r /tmp/requirements.txt -t /asset-output && "
                "cp -r src/* /asset-output/",
            ],
            output_type=BundlingOutput.NOT_ARCHIVED,
            user="root",
        )

        env_vars = {}
        env_vars.update(environment)

        if env_name == "dev":
            retention = logs.RetentionDays.ONE_WEEK
        elif env_name == "stg":
            retention = logs.RetentionDays.TWO_WEEKS
        else:
            retention = logs.RetentionDays.ONE_MONTH

        logs.LogGroup(self, "ApiLogGroup", log_group_name=f"/{prefix}/lambda-logs", retention=retention)
        api_role = iam.Role(
            self, "ApiRole",
            role_name=f"{prefix}-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole"),
            ],
        )

        api_function = lambda_.Function(
            self,
            "ApiFunction",
            function_name=f"{prefix}-lambda",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.handler",
            code=lambda_.Code.from_asset(
                project_root,
                exclude=["infra", ".venv", "__pycache__", "*.pyc", "tests", "cdk.out"],
                bundling=bundling,
            ),
            memory_size=lambda_memory_mib,
            timeout=Duration.seconds(30),
            environment=env_vars,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=app_subnets),
            security_groups=[security_group],
            role=api_role,
        )

        api = apigwv2.HttpApi(
            self,
            "HttpApi",
            api_name=f"{prefix}-api",
            default_integration=HttpLambdaIntegration(
                "LambdaIntegration",
                handler=api_function,
            ),
        )

        ssm.StringParameter(
            self,
            "ApiUrlParam",
            parameter_name=f"/{env_name}/{project_name}/api-url",
            string_value=api.api_endpoint,
        )
