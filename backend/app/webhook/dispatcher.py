from sqlalchemy.orm import Session

from app.shared.models.user import User


async def dispatch_message(phone: str, message: str, db: Session) -> dict:
    """
    Decide si el mensaje va a onboarding o a publication.
    REGLA: si el usuario no existe o no completo onboarding -> onboarding
           si ya esta onboarded -> publication menu
    """
    user = db.query(User).filter(User.phone == phone).first()

    if not user or not user.is_onboarded:
        return {"module": "onboarding", "user": user, "message": message}
    else:
        return {"module": "publication", "user": user, "message": message}
