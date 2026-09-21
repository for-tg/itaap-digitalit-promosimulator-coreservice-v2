"""
JWT token authentication and role-based authorization handlers.

Provides:
- TokenValidator for validating JWT tokens in request headers
- RoleChecker for enforcing role-based access control
- User claim extraction for authenticated requests
"""

import base64
import json
from typing import Any

from fastapi import Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itaap_python_utils.auth.exceptions import (
    InvalidAudienceError,
    InvalidRoleError,
    InvalidSignatureError,
    InvalidTenantError,
    InvalidTokenFormatError,
    TokenExpiredError,
)
from itaap_python_utils.auth.jwt_token_checker import JWTTokenChecker

from app.config.settings import settings
from app.exceptions.error_factory import service_error_factory
from app.exceptions.service_errors import ServiceErrors


auth_error = ServiceErrors.AUTHENTICATION.value
error_factory = service_error_factory


bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="Enter the access token received from the frontend login.",
)


token_checker = JWTTokenChecker(
    algorithm="RS256",
    jwks_url=settings.JWKS_URL,
    audience=settings.JWT_AUDIENCE,
)


def get_auth_header(request: Request) -> str:
    """Extract the Bearer token from the Authorization header."""

    auth_header = request.headers.get("Authorization")

    if not auth_header:
        error_factory.raise_exception(
            auth_error,
            reason="Authorization header missing",
        )

    try:
        auth_type, token = auth_header.split(" ", 1)

    except ValueError:
        error_factory.raise_exception(
            auth_error,
            reason="Invalid authorization format",
        )

    if auth_type.lower() != "bearer":
        error_factory.raise_exception(
            auth_error,
            reason="Invalid auth type",
        )

    if not token.strip():
        error_factory.raise_exception(
            auth_error,
            reason="Bearer token missing",
        )

    return token.strip()


def _decode_token_claims(
    token: str,
) -> dict[str, Any]:
    """
    Decode JWT payload claims.

    This function is called only after token validation has succeeded.
    Signature, audience, expiry, and tenant validation are handled by
    JWTTokenChecker before these claims are trusted.
    """

    try:
        token_parts = token.split(".")

        if len(token_parts) != 3:
            raise ValueError(
                "Invalid JWT structure."
            )

        payload = token_parts[1]

        # JWT uses URL-safe Base64 without guaranteed padding.
        padding = "=" * (
            (4 - len(payload) % 4) % 4
        )

        decoded_payload = base64.urlsafe_b64decode(
            payload + padding
        )

        claims = json.loads(
            decoded_payload.decode("utf-8")
        )

        if not isinstance(claims, dict):
            raise ValueError(
                "Invalid JWT payload."
            )

        return claims

    except (
        ValueError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as exc:
        error_factory.raise_exception(
            auth_error,
            reason=f"Unable to read token claims: {exc}",
        )


def _set_request_user_state(
    request: Request,
    token: str,
    client_id: str | None = None,
) -> None:
    """Store authenticated user information in request.state."""

    claims = _decode_token_claims(token)

    user_id = (
        claims.get("oid")
        or claims.get("sub")
    )

    user_name = (
        claims.get("name")
        or claims.get("preferred_username")
    )

    user_email = (
        claims.get("preferred_username")
        or claims.get("email")
        or claims.get("upn")
    )

    roles = claims.get(
        "roles",
        [],
    )

    if isinstance(roles, str):
        roles = [roles]

    if not user_id:
        error_factory.raise_exception(
            auth_error,
            reason=(
                "Authenticated token does not contain "
                "a supported user identifier."
            ),
        )

    request.state.user_id = str(user_id)
    request.state.user_name = (
        str(user_name)
        if user_name
        else None
    )
    request.state.user_email = (
        str(user_email)
        if user_email
        else None
    )
    request.state.roles = roles
    request.state.client_id = client_id


class TokenValidator:
    """Validate the Bearer token from the Authorization header."""

    def __call__(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Security(
            bearer_scheme
        ),
    ) -> bool:
        """Validate authentication and populate authenticated user state."""

        if not settings.ENABLE_AUTH:
            request.state.user_id = "local-user"
            request.state.user_name = "Local User"
            request.state.user_email = None
            request.state.roles = []
            request.state.client_id = "authentication-disabled"

            return True

        if credentials is None:
            error_factory.raise_exception(
                auth_error,
                reason="Authorization header missing",
            )

        token = credentials.credentials

        try:
            token_appid = token_checker.validate_token(
                token
            )

            _set_request_user_state(
                request=request,
                token=token,
                client_id=token_appid,
            )

        except (
            InvalidTokenFormatError,
            InvalidSignatureError,
            TokenExpiredError,
            InvalidAudienceError,
            InvalidTenantError,
        ) as exc:
            error_factory.raise_exception(
                auth_error,
                reason=str(exc),
            )

        return True


class RoleChecker:
    """Validate that the request token contains the required role."""

    def __init__(
        self,
        required_role: str | None = None,
    ):
        self.required_role = required_role

    def __call__(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Security(
            bearer_scheme
        ),
    ) -> bool:
        """Validate the required Azure App Role."""

        if not settings.ENABLE_AUTH:
            return True

        if credentials is None:
            error_factory.raise_exception(
                auth_error,
                reason="Authorization header missing",
            )

        token = credentials.credentials

        try:
            token_checker.verify_roles(
                token,
                self.required_role,
            )

        except (
            InvalidTokenFormatError,
            InvalidRoleError,
            InvalidSignatureError,
            TokenExpiredError,
            InvalidAudienceError,
            InvalidTenantError,
        ) as exc:
            error_factory.raise_exception(
                auth_error,
                reason=str(exc),
            )

        return True