"""End-to-end JWT verification tests for ``get_claims`` using real RSA keys.

Unlike test_authz.py these do not mock ``jwt.decode``; they sign real tokens and
check that signature, issuer, audience, expiry and algorithm handling are right.
"""

import base64
import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from pycommon.authz import _get_jwks_for_url, get_claims
from pycommon.exceptions import ClaimException

ISSUER = "http://mock-issuer.com"
AUDIENCE = "mock-audience"
KID = "test-kid"

ENV = {
    "OAUTH_ISSUER_BASE_URL": ISSUER,
    "OAUTH_AUDIENCE": AUDIENCE,
    "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    "ADDITIONAL_CHARGES_TABLE": "mock-additional-charges-table",
    "COGNITO_USERS_DYNAMODB_TABLE": "mock-cognito-table",
    "IDP_PREFIX": "mockprefix",
}


def _b64(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def other_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def jwks(signing_key):
    nums = signing_key.public_key().public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": KID,
                "alg": "RS256",
                "use": "sig",
                "n": _b64(nums.n),
                "e": _b64(nums.e),
            }
        ]
    }


@pytest.fixture(autouse=True)
def clear_cache():
    _get_jwks_for_url.cache_clear()


@pytest.fixture
def run_get_claims(jwks):
    """Call get_claims with env, JWKS, DynamoDB and DAL mocked out."""

    def _run(token):
        table = MagicMock()
        table.get_item.return_value = {
            "Item": {"accounts": [{"id": "acct", "isDefault": True}]}
        }
        with (
            patch(
                "pycommon.authz.os.environ.get",
                side_effect=lambda k, d=None: ENV.get(k, d),
            ),
            patch(
                "pycommon.authz.requests.get",
                return_value=MagicMock(ok=True, json=MagicMock(return_value=jwks)),
            ),
            patch("pycommon.authz.boto3.resource") as resource,
            patch("pycommon.dal.DAL"),
        ):
            resource.return_value.Table.return_value = table
            return get_claims(token)

    return _run


def _token(key, *, alg="RS256", **claims):
    payload = {
        "username": "mockprefix_mockuser",
        "iss": ISSUER,
        "exp": int(time.time()) + 300,
        **claims,
    }
    return jwt.encode(payload, key, algorithm=alg, headers={"kid": KID})


def test_valid_access_token_without_aud_is_accepted(signing_key, run_get_claims):
    # Cognito access tokens carry no 'aud' claim
    token = _token(signing_key, token_use="access")
    assert run_get_claims(token)["username"] == "mockuser"


def test_valid_token_with_matching_aud_is_accepted(signing_key, run_get_claims):
    token = _token(signing_key, aud=AUDIENCE)
    assert run_get_claims(token)["username"] == "mockuser"


def test_valid_token_with_matching_aud_in_list_is_accepted(signing_key, run_get_claims):
    token = _token(signing_key, aud=["other", AUDIENCE])
    assert run_get_claims(token)["username"] == "mockuser"


def test_wrong_audience_rejected(signing_key, run_get_claims):
    token = _token(signing_key, aud="someone-else")
    with pytest.raises(ClaimException, match="Invalid JWT claims"):
        run_get_claims(token)


def test_wrong_issuer_rejected(signing_key, run_get_claims):
    token = _token(signing_key, iss="http://evil.example.com")
    with pytest.raises(ClaimException, match="Invalid JWT claims"):
        run_get_claims(token)


def test_missing_issuer_rejected(signing_key, run_get_claims):
    payload = {"username": "mockprefix_mockuser", "exp": int(time.time()) + 300}
    token = jwt.encode(payload, signing_key, algorithm="RS256", headers={"kid": KID})
    with pytest.raises(ClaimException, match="Invalid JWT claims"):
        run_get_claims(token)


def test_expired_token_rejected(signing_key, run_get_claims):
    token = _token(signing_key, exp=int(time.time()) - 60)
    with pytest.raises(ClaimException, match="JWT token has expired"):
        run_get_claims(token)


def test_token_signed_by_other_key_rejected(other_key, run_get_claims):
    token = _token(other_key)
    with pytest.raises(ClaimException, match="Invalid JWT token"):
        run_get_claims(token)


def test_hs256_token_signed_with_public_key_rejected(signing_key, run_get_claims):
    """Algorithm-confusion attack: forge an HS256 token using the public key bytes."""
    import hashlib
    import hmac
    import json

    pub_der = signing_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    def b64(data: bytes) -> bytes:
        return base64.urlsafe_b64encode(data).rstrip(b"=")

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": KID}).encode())
    body = b64(
        json.dumps(
            {
                "username": "mockprefix_attacker",
                "iss": ISSUER,
                "exp": int(time.time()) + 300,
            }
        ).encode()
    )
    sig = b64(hmac.new(pub_der, header + b"." + body, hashlib.sha256).digest())
    forged = (header + b"." + body + b"." + sig).decode()

    with pytest.raises(ClaimException, match="Invalid JWT token"):
        run_get_claims(forged)


def test_alg_none_token_rejected(run_get_claims):
    token = jwt.encode(
        {"username": "x", "iss": ISSUER},
        key=None,
        algorithm="none",
        headers={"kid": KID},
    )
    with pytest.raises(ClaimException, match="Invalid JWT token"):
        run_get_claims(token)


def test_id_token_rejected(signing_key, run_get_claims):
    token = _token(signing_key, token_use="id")
    with pytest.raises(ClaimException, match="token_use must be 'access'"):
        run_get_claims(token)


def test_malformed_token_rejected(run_get_claims):
    with pytest.raises(ClaimException, match="malformed header"):
        run_get_claims("not.a.jwt")
