import os
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-Api-Key")

def verify_api_key(api_key: str = Depends(API_KEY_HEADER)):
    """
    Dependency to verify the API key from the X-Api-Key header.
    """
    expected_api_key = os.getenv("BRIDGE_API_KEY")

    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API Key is not configured on the server.",
        )

    if not api_key or api_key != expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key.",
        )
