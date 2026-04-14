from sqlalchemy.orm import Session

from app.shared.models.user import User
from .models import Profile, OnboardingSession

ONBOARDING_STEPS = [
    {"step": 0, "field": "name", "prompt": "Hola! Bienvenido. Como te llamas?"},
    {"step": 1, "field": "email", "prompt": "Genial, {name}. Cual es tu email?"},
    {"step": 2, "field": "city", "prompt": "De que ciudad sos?"},
    {"step": 3, "field": "bio", "prompt": "Contanos un poco sobre vos (breve bio):"},
]


class OnboardingService:
    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_user(self, phone: str) -> User:
        user = self.db.query(User).filter(User.phone == phone).first()
        if not user:
            user = User(phone=phone)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        return user

    def _get_or_create_session(self, user_id) -> OnboardingSession:
        session = (
            self.db.query(OnboardingSession)
            .filter(OnboardingSession.user_id == user_id, OnboardingSession.completed == False)
            .first()
        )
        if not session:
            session = OnboardingSession(user_id=user_id, data={})
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
        return session

    async def process_step(self, phone: str, message: str) -> dict:
        user = self._get_or_create_user(phone)
        session = self._get_or_create_session(user.id)

        if session.current_step >= len(ONBOARDING_STEPS):
            return {"response": "Ya completaste el registro.", "completed": True}

        # Guardar respuesta del paso actual
        step_config = ONBOARDING_STEPS[session.current_step]
        data = dict(session.data) if session.data else {}
        data[step_config["field"]] = message
        session.data = data

        # Avanzar al siguiente paso
        session.current_step += 1
        self.db.commit()

        if session.current_step >= len(ONBOARDING_STEPS):
            self._finalize_onboarding(user, session)
            return {
                "response": "Registro completo! Ya podes publicar. Escribi 'publicar' para empezar.",
                "completed": True,
            }

        # Enviar siguiente pregunta
        next_step = ONBOARDING_STEPS[session.current_step]
        prompt = next_step["prompt"].format(**data)
        return {"response": prompt, "completed": False}

    def _finalize_onboarding(self, user: User, session: OnboardingSession):
        data = session.data or {}
        user.name = data.get("name")
        user.email = data.get("email")
        user.is_onboarded = True

        profile = Profile(
            user_id=user.id,
            city=data.get("city"),
            bio=data.get("bio"),
        )
        self.db.add(profile)

        session.completed = True
        self.db.commit()

    def get_status(self, phone: str) -> dict:
        user = self.db.query(User).filter(User.phone == phone).first()
        if not user:
            return {
                "phone": phone,
                "current_step": 0,
                "total_steps": len(ONBOARDING_STEPS),
                "completed": False,
                "data": {},
            }

        session = (
            self.db.query(OnboardingSession)
            .filter(OnboardingSession.user_id == user.id)
            .order_by(OnboardingSession.created_at.desc())
            .first()
        )

        if not session:
            return {
                "phone": phone,
                "current_step": 0,
                "total_steps": len(ONBOARDING_STEPS),
                "completed": False,
                "data": {},
            }

        return {
            "phone": phone,
            "current_step": session.current_step,
            "total_steps": len(ONBOARDING_STEPS),
            "completed": session.completed,
            "data": session.data or {},
        }
