# dal/providers/aws.py
from typing import Any, Dict

import boto3

from pycommon.dal.providers.aws import AwsAccount, AwsAdminConfig, AwsProvider, AwsUser

from ...contracts import BackendABC
from ...dal import Backend, register_backend


class AwsBackend(BackendABC):

    User = AwsUser
    Account = AwsAccount
    AdminConfig = AwsAdminConfig

    def __init__(self, **config: Any) -> None:
        boto3_kwargs: Dict[str, Any] = config.get("boto3_kwargs", {})

        dynamodb = boto3.resource("dynamodb", **boto3_kwargs)

        provider = AwsProvider(dynamodb=dynamodb)

        # Bind provider context to the AR classes
        self.User.provider = provider
        self.Account.provider = provider
        self.AdminConfig.provider = provider


# Register at import time
register_backend(Backend.AWS, AwsBackend)
