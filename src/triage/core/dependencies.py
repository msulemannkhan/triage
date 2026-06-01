"""Shared FastAPI dependencies — here, static API-key authentication."""

import secrets
from typing import Annotated

from fastapi import Depends, Header

from triage.core.config import Settings, get_settings
from triage.core.errors import AuthError


async def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    # Constant-time compare so a wrong key can't be recovered via response timing.
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise AuthError()
