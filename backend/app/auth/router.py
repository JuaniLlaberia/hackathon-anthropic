"""
OAuth callback para MercadoLibre.
ML redirige aca despues de que el usuario autoriza.
"""

import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.shared.deps import get_db
from app.shared.kapso import KapsoClient, KapsoError
from app.shared.ml_client import MercadoLibreClient, MercadoLibreError
from app.shared.models.user import User
from app.onboarding.service import OnboardingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

settings = get_settings()

SUCCESS_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cuenta conectada</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            display: flex; align-items: center; justify-content: center;
            min-height: 100vh; margin: 0;
            background: #f5f5f5; color: #333;
        }
        .card {
            background: white; border-radius: 16px; padding: 3rem;
            text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,.08);
            max-width: 400px;
        }
        .check { font-size: 4rem; margin-bottom: 1rem; }
        h1 { margin: 0 0 .5rem; font-size: 1.4rem; }
        p { color: #666; margin: 0; }
    </style>
</head>
<body>
    <div class="card">
        <div class="check">✅</div>
        <h1>¡Cuenta conectada!</h1>
        <p>Ya podés cerrar esta ventana y volver a WhatsApp.</p>
    </div>
</body>
</html>
"""

ERROR_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            display: flex; align-items: center; justify-content: center;
            min-height: 100vh; margin: 0;
            background: #f5f5f5; color: #333;
        }
        .card {
            background: white; border-radius: 16px; padding: 3rem;
            text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,.08);
            max-width: 400px;
        }
        .icon { font-size: 4rem; margin-bottom: 1rem; }
        h1 { margin: 0 0 .5rem; font-size: 1.4rem; }
        p { color: #666; margin: 0; }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">❌</div>
        <h1>Algo salió mal</h1>
        <p>No pudimos conectar tu cuenta. Volvé a WhatsApp e intentá de nuevo.</p>
    </div>
</body>
</html>
"""


def _get_kapso_client() -> KapsoClient:
    return KapsoClient(
        api_key=settings.KAPSO_API_KEY,
        phone_number_id=settings.KAPSO_PHONE_NUMBER_ID,
    )


@router.get("/ml/callback", response_class=HTMLResponse)
async def ml_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """MercadoLibre redirects here after user authorizes."""
    # Decode phone from state
    try:
        phone = MercadoLibreClient.decode_state(state)
    except Exception:
        logger.error(f"Could not decode state: {state}")
        return HTMLResponse(content=ERROR_HTML, status_code=400)

    # Find the user
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        logger.error(f"OAuth callback for unknown phone: {phone}")
        return HTMLResponse(content=ERROR_HTML, status_code=404)

    # Exchange code for tokens
    redirect_uri = settings.ML_REDIRECT_URI or f"{settings.BACKEND_BASE_URL}/api/v1/auth/ml/callback"
    ml_client = MercadoLibreClient(
        app_id=settings.ML_APP_ID,
        app_secret=settings.ML_APP_SECRET,
        redirect_uri=redirect_uri,
    )

    try:
        tokens = ml_client.exchange_code_for_tokens(code)
    except MercadoLibreError as e:
        logger.error(f"ML token exchange failed for {phone}: {e}")
        return HTMLResponse(content=ERROR_HTML, status_code=502)

    # Store tokens and complete onboarding
    onboarding = OnboardingService(db)
    onboarding.complete_oauth(
        user=user,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_at=tokens["expires_at"],
        ml_user_id=tokens["user_id"],
    )

    # Notify user on WhatsApp
    if settings.KAPSO_API_KEY and settings.KAPSO_PHONE_NUMBER_ID:
        try:
            kapso = _get_kapso_client()
            kapso.send_text(
                to=phone,
                body=(
                    "✅ ¡Tu cuenta de MercadoLibre fue conectada con éxito!\n"
                    "Ya podés empezar a publicar. Mandame una foto del producto o contame qué querés vender. 📸"
                ),
            )
        except KapsoError as e:
            logger.error(f"Failed to send OAuth success message to {phone}: {e}")

    logger.info(f"OAuth complete for {phone} (ML user {tokens['user_id']})")
    return HTMLResponse(content=SUCCESS_HTML)
