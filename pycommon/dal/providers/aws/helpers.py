import datetime

import botocore.exceptions

from ...errors import Conflict, PermissionDenied, TransientError


def map_aws_error(e: Exception) -> Exception:
    if isinstance(e, botocore.exceptions.ClientError):
        code = e.response.get("Error", {}).get("Code", "")
        if code in {"ProvisionedThroughputExceededException", "ThrottlingException"}:
            return TransientError(str(e))
        if code in {"AccessDeniedException"}:
            return PermissionDenied(str(e))
        if code in {"ConditionalCheckFailedException"}:
            return Conflict(str(e))
    return e


# get a timestamp string for right now w/ `nowstr()`
def nowstr() -> str:
    """
    Returns the current timestamp as an ISO-like string (YYYY-MM-DDTHH:MM:SS).
    """
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
