import aws_cdk as core
import aws_cdk.assertions as assertions

from cognito_middleware.cognito_middleware_stack import CognitoMiddlewareStack

# example tests. To run these tests, uncomment this file along with the example
# resource in cognito_middleware/cognito_middleware_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = CognitoMiddlewareStack(app, "cognito-middleware")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
