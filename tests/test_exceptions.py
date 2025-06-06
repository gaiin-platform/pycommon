from pycommon.exceptions import (
    HTTPBadRequest,
    HTTPException,
    HTTPNotFound,
    HTTPUnauthorized,
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
