import botocore.exceptions

from pycommon.dal.errors import Conflict, PermissionDenied, TransientError
from pycommon.dal.providers.aws.helpers import map_aws_error


def make_client_error(code):
    error_response = {"Error": {"Code": code}}
    return botocore.exceptions.ClientError(error_response, "operation")


def test_map_aws_error_transient():
    e = make_client_error("ProvisionedThroughputExceededException")
    mapped = map_aws_error(e)
    assert isinstance(mapped, TransientError)
    assert str(e) in str(mapped)

    e = make_client_error("ThrottlingException")
    mapped = map_aws_error(e)
    assert isinstance(mapped, TransientError)


def test_map_aws_error_permission_denied():
    e = make_client_error("AccessDeniedException")
    mapped = map_aws_error(e)
    assert isinstance(mapped, PermissionDenied)


def test_map_aws_error_conflict():
    e = make_client_error("ConditionalCheckFailedException")
    mapped = map_aws_error(e)
    assert isinstance(mapped, Conflict)


def test_map_aws_error_other_client_error():
    e = make_client_error("SomeOtherException")
    mapped = map_aws_error(e)
    assert mapped is e  # unchanged


def test_map_aws_error_non_client_error():
    e = ValueError("not a client error")
    mapped = map_aws_error(e)
    assert mapped is e
