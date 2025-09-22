"""
AWS Resource Permission Operations
Enums for defining specific AWS service operations needed by Lambda functions
"""

from enum import Enum


class DynamoDBOperation(Enum):
    """DynamoDB operations for IAM permissions"""

    GET_ITEM = "dynamodb:GetItem"
    PUT_ITEM = "dynamodb:PutItem"
    QUERY = "dynamodb:Query"
    SCAN = "dynamodb:Scan"
    UPDATE_ITEM = "dynamodb:UpdateItem"
    DELETE_ITEM = "dynamodb:DeleteItem"
    BATCH_GET_ITEM = "dynamodb:BatchGetItem"
    BATCH_WRITE_ITEM = "dynamodb:BatchWriteItem"
    DESCRIBE_TABLE = "dynamodb:DescribeTable"


class S3Operation(Enum):
    """S3 operations for IAM permissions"""

    GET_OBJECT = "s3:GetObject"
    PUT_OBJECT = "s3:PutObject"
    DELETE_OBJECT = "s3:DeleteObject"
    LIST_BUCKET = "s3:ListBucket"
    GET_BUCKET_LOCATION = "s3:GetBucketLocation"
    GET_BUCKET_VERSIONING = "s3:GetBucketVersioning"
    PUT_BUCKET_CORS = "s3:PutBucketCors"
    GET_BUCKET_CORS = "s3:GetBucketCors"


class SQSOperation(Enum):
    """SQS operations for IAM permissions"""

    SEND_MESSAGE = "sqs:SendMessage"
    RECEIVE_MESSAGE = "sqs:ReceiveMessage"
    DELETE_MESSAGE = "sqs:DeleteMessage"
    GET_QUEUE_ATTRIBUTES = "sqs:GetQueueAttributes"
    GET_QUEUE_URL = "sqs:GetQueueUrl"
    LIST_QUEUES = "sqs:ListQueues"


class SecretsManagerOperation(Enum):
    """Secrets Manager operations for IAM permissions"""

    GET_SECRET_VALUE = "secretsmanager:GetSecretValue"
    PUT_SECRET_VALUE = "secretsmanager:PutSecretValue"
    UPDATE_SECRET_VERSION_STAGE = "secretsmanager:UpdateSecretVersionStage"
    DESCRIBE_SECRET = "secretsmanager:DescribeSecret"


class SSMOperation(Enum):
    """Systems Manager Parameter Store operations"""

    GET_PARAMETER = "ssm:GetParameter"
    GET_PARAMETERS = "ssm:GetParameters"
    GET_PARAMETERS_BY_PATH = "ssm:GetParametersByPath"
    PUT_PARAMETER = "ssm:PutParameter"
    DELETE_PARAMETER = "ssm:DeleteParameter"
    DESCRIBE_PARAMETERS = "ssm:DescribeParameters"


class LambdaOperation(Enum):
    """Lambda operations for IAM permissions"""

    INVOKE_FUNCTION = "lambda:InvokeFunction"
    INVOKE_ASYNC = "lambda:InvokeAsync"
    GET_FUNCTION = "lambda:GetFunction"


class BedrockOperation(Enum):
    """Bedrock operations for IAM permissions"""

    INVOKE_MODEL = "bedrock:InvokeModel"
    INVOKE_MODEL_WITH_RESPONSE_STREAM = "bedrock:InvokeModelWithResponseStream"
    INVOKE_GUARDRAIL = "bedrock:InvokeGuardrail"
    APPLY_GUARDRAIL = "bedrock:ApplyGuardrail"


class CognitoOperation(Enum):
    """Cognito operations for IAM permissions"""

    ADMIN_GET_USER = "cognito-idp:AdminGetUser"
    ADMIN_CREATE_USER = "cognito-idp:AdminCreateUser"
    ADMIN_UPDATE_USER = "cognito-idp:AdminUpdateUser"
    ADMIN_DELETE_USER = "cognito-idp:AdminDeleteUser"
    LIST_USERS = "cognito-idp:ListUsers"
