from exceptions import (
    ClaimException,
    EnvVarError,
    HTTPBadRequest,
    HTTPException,
    HTTPNotFound,
    HTTPUnauthorized,
    UnknownApiUserException,
)


def test_http_exception():
    exc = HTTPException(500, "Internal Server Error")
    assert exc.status_code == 500
    assert str(exc) == "Internal Server Error"


def test_bad_request_exception():
    exc = HTTPBadRequest()
    assert exc.status_code == 400
    assert str(exc) == "Bad Request"

    custom_message = "Invalid input"
    exc = HTTPBadRequest(custom_message)
    assert exc.status_code == 400
    assert str(exc) == custom_message


def test_unauthorized_exception():
    exc = HTTPUnauthorized()
    assert exc.status_code == 401
    assert str(exc) == "Unauthorized"

    custom_message = "Access denied"
    exc = HTTPUnauthorized(custom_message)
    assert exc.status_code == 401
    assert str(exc) == custom_message


def test_not_found_exception():
    exc = HTTPNotFound()
    assert exc.status_code == 404
    assert str(exc) == "Not Found"

    custom_message = "Resource not found"
    exc = HTTPNotFound(custom_message)
    assert exc.status_code == 404
    assert str(exc) == custom_message


def test_environment_error_default_message():
    exc = EnvVarError()
    assert str(exc) == "Environment variable error occurred"


def test_environment_error_custom_message():
    custom_message = "Missing required environment variable"
    exc = EnvVarError(custom_message)
    assert str(exc) == custom_message


def test_claim_exception_default_message():
    exc = ClaimException()
    assert str(exc) == "Claim error occurred"


def test_claim_exception_custom_message():
    custom_message = "Invalid claim data"
    exc = ClaimException(custom_message)
    assert str(exc) == custom_message


def test_unknown_api_user_exception_default_message():
    exc = UnknownApiUserException()
    assert str(exc) == "Unknown API user"


def test_unknown_api_user_exception_custom_message():
    custom_message = "API user not recognized"
    exc = UnknownApiUserException(custom_message)
    assert str(exc) == custom_message
