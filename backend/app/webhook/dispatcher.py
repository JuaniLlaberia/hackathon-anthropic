from sqlalchemy.orm import Session

from app.shared.models.user import User


async def dispatch_message(phone: str, message: str, db: Session) -> dict:
    """
    Decide si el mensaje va a onboarding, a conectar ML, o a publication.
    REGLA:
      - No existe o no completo onboarding -> onboarding
      - Onboarded pero sin cuenta ML conectada -> needs_ml
      - Onboarded + ML conectada -> publication
    """
    user = db.query(User).filter(User.phone == phone).first()

    if not user or not user.is_onboarded:
        return {"module": "onboarding", "user": user, "message": message}
    elif not user.ml_connected:
        return {"module": "needs_ml", "user": user, "message": message}
    else:
        return {"module": "publication", "user": user, "message": message}
