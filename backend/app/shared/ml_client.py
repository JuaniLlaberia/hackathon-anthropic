"""
Cliente OAuth para MercadoLibre.
Docs: https://developers.mercadolibre.com.ar/es_ar/autenticacion-y-autorizacion
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

ML_AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
ML_USER_URL = "https://api.mercadolibre.com/users/me"


class MercadoLibreError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"[{status_code}] {message}")


class MercadoLibreClient:
    def __init__(self, app_id: str, app_secret: str, redirect_uri: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.redirect_uri = redirect_uri

    def build_oauth_url(self, phone: str) -> str:
        """Build the ML OAuth authorization URL with phone encoded in state."""
        state = base64.urlsafe_b64encode(phone.encode()).decode()
        return (
            f"{ML_AUTH_URL}"
            f"?response_type=code"
            f"&client_id={self.app_id}"
            f"&redirect_uri={quote(self.redirect_uri, safe='')}"
            f"&state={state}"
        )

    @staticmethod
    def decode_state(state: str) -> str:
        """Decode state parameter back to phone number."""
        return base64.urlsafe_b64decode(state.encode()).decode()

    def exchange_code_for_tokens(self, code: str) -> dict:
        """Exchange authorization code for access + refresh tokens.

        Returns dict with: access_token, refresh_token, expires_in, user_id
        """
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        with httpx.Client() as client:
            response = client.post(ML_TOKEN_URL, json=payload)

        if response.is_error:
            logger.error(f"ML token exchange failed: {response.text}")
            raise MercadoLibreError(response.status_code, response.text)

        data = response.json()
        logger.info(f"ML token exchange response keys: {list(data.keys())}")
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_in": data.get("expires_in", 21600),
            "user_id": str(data["user_id"]),
            "expires_at": datetime.utcnow() + timedelta(seconds=data.get("expires_in", 21600)),
        }

    def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token."""
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "refresh_token": refresh_token,
        }
        with httpx.Client() as client:
            response = client.post(ML_TOKEN_URL, json=payload)

        if response.is_error:
            logger.error(f"ML token refresh failed: {response.text}")
            raise MercadoLibreError(response.status_code, response.text)

        data = response.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_in": data["expires_in"],
            "user_id": str(data["user_id"]),
            "expires_at": datetime.utcnow() + timedelta(seconds=data["expires_in"]),
        }

    @staticmethod
    def get_user_info(access_token: str) -> dict:
        """Get the authenticated ML user's profile."""
        with httpx.Client() as client:
            response = client.get(
                ML_USER_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if response.is_error:
            raise MercadoLibreError(response.status_code, response.text)

        return response.json()
