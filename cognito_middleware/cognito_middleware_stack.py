from aws_cdk import (
    App,
    CfnCondition,
    CfnMapping,
    CfnOutput,
    CfnParameter,
    Fn,
    RemovalPolicy,
    Stack,
    aws_apigateway as apigateway,
    aws_logs as logs,
    aws_stepfunctions as stepfunctions,
)
from constructs import Construct


def read_file(filename: str):
    with open(filename, "rt") as file:
        return file.read()


class CognitoMiddlewareStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        log_group = logs.LogGroup(
            self,
            "OIDC Proxy Log Group",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        api = apigateway.RestApi(
            self,
            "OIDC Proxy Middleware",
            description="Proxy middleware",
            endpoint_configuration=apigateway.EndpointConfiguration(
                types=[apigateway.EndpointType.REGIONAL]
            ),
            deploy_options=apigateway.StageOptions(
                access_log_destination=apigateway.LogGroupLogDestination(log_group),
                access_log_format=apigateway.AccessLogFormat.custom(
                    '$context.identity.sourceIp $context.identity.caller $context.identity.user [$context.requestTime] "$context.httpMethod $context.resourcePath $context.protocol" $context.status $context.responseLength $context.requestId'
                ),
            ),
        )

        empty_json_resource = api.root.add_resource("empty.json")
        empty_json_resource.add_method(
            "GET",
            apigateway.MockIntegration(
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": "{}",
                        },
                    )
                ],
                passthrough_behavior=apigateway.PassthroughBehavior.WHEN_NO_TEMPLATES,
                request_templates={
                    "application/json": '{"statusCode": 200}',
                },
            ),
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                )
            ],
        )

        github_resource = api.root.add_resource("github")

        github_well_known_resource = github_resource.add_resource(".well-known")

        github_discovery_resource = github_well_known_resource.add_resource(
            "openid-configuration"
        )
        github_discovery_resource.add_method(
            "GET",
            integration=apigateway.MockIntegration(
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": read_file(
                                "./mapping-templates/github_discovery/integration-response.vtl"
                            ),
                        },
                    )
                ],
                passthrough_behavior=apigateway.PassthroughBehavior.WHEN_NO_TEMPLATES,
                request_templates={
                    "application/json": '{"statusCode": 200}',
                },
            ),
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                )
            ],
        )

        github_access_token_resource = github_resource.add_resource("access_token")
        github_access_token_resource.add_method(
            "POST",
            apigateway.HttpIntegration(
                "https://github.com/login/oauth/access_token",
                http_method="POST",
                options=apigateway.IntegrationOptions(
                    passthrough_behavior=apigateway.PassthroughBehavior.WHEN_NO_TEMPLATES,
                    request_parameters={
                        "integration.request.header.Accept": "'application/json'"
                    },
                    integration_responses=[
                        apigateway.IntegrationResponse(
                            status_code="200",
                        )
                    ],
                ),
                proxy=False,
            ),
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                )
            ],
        )

        github_user_resource = github_resource.add_resource("user")
        github_user_resource.add_method(
            "GET",
            integration=apigateway.HttpIntegration(
                "https://api.github.com/user",
                http_method="GET",
                options=apigateway.IntegrationOptions(
                    passthrough_behavior=apigateway.PassthroughBehavior.WHEN_NO_TEMPLATES,
                    request_parameters={
                        "integration.request.header.Authorization": "method.request.header.Authorization",
                    },
                    integration_responses=[
                        apigateway.IntegrationResponse(
                            status_code="200",
                            response_templates={
                                "application/json": read_file(
                                    "./mapping-templates/github_access_token/integration-response.vtl"
                                ),
                            },
                        ),
                        apigateway.IntegrationResponse(
                            status_code="401",
                            selection_pattern="401",
                            response_templates={
                                "application/json": "$input.json('$')",
                            },
                        ),
                    ],
                    request_templates={
                        "application/json": read_file(
                            "./mapping-templates/github_access_token/integration-request.vtl"
                        ),
                    },
                ),
                proxy=False,
            ),
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                )
            ],
            request_parameters={
                "method.request.header.Authorization": True,
            },
            request_validator_options=apigateway.RequestValidatorOptions(
                request_validator_name="Validate query string parameters and headers",
                validate_request_body=False,
                validate_request_parameters=True,
            ),
        )

        CfnOutput(
            self,
            "GithubIssuerURL",
            description="Github Issuer URL",
            value=Fn.join(
                "",
                [
                    api.url,
                    "github",
                ],
            ),
            export_name=Fn.sub("${AWS::StackName}-Provider-Github"),
        )
