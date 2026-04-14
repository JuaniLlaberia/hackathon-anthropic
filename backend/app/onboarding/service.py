import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.shared.models.user import User
from app.shared.claude_client import ClaudeClient, PENDING_QUESTIONS
from app.shared.ml_client import MercadoLibreClient
from .models import OnboardingSession

logger = logging.getLogger(__name__)

settings = get_settings()

ML_REGISTER_URL = "https://www.mercadolibre.com.ar/registration"

RESET_COMMANDS = {"reiniciar", "reset", "/reiniciar", "/reset"}
SESSION_TTL_MINUTES = 30
MAX_HISTORY = 4

MESSAGES = {
    "welcome": (
        "👋 ¡Hola! Soy tu asistente para publicar en MercadoLibre.\n\n"
        "Para empezar necesito conectar tu cuenta de MercadoLibre.\n"
        "¿Ya tenés una cuenta? Respondé *sí* o *no*.\n\n"
        "Si tenés alguna duda, preguntame lo que quieras. 💬"
    ),
    "oauth_link": (
        "¡Perfecto! Hacé click en este link para autorizar el acceso a tu cuenta:\n\n"
        "{oauth_url}\n\n"
        "Cuando termines, te confirmo por acá. 🔗\n"
        "Si tenés algún problema, contame."
    ),
    "registration_guide": (
        "¡No hay problema! Primero creá tu cuenta en MercadoLibre:\n\n"
        f"{ML_REGISTER_URL}\n\n"
        "Cuando la tengas lista, escribime de nuevo y te ayudo a conectarla. 👍\n"
        "Si necesitás ayuda con algo, preguntame."
    ),
    "registration_followup": (
        "¡Hola de nuevo! ¿Ya creaste tu cuenta en MercadoLibre?\n"
        "Si es así te mando el link para conectarla.\n"
        "Si tenés alguna duda, preguntame."
    ),
    "oauth_waiting": (
        "Todavía estoy esperando que autorices tu cuenta.\n"
        "Usá el link que te mandé. Si lo perdiste, acá va de nuevo:\n\n"
        "{oauth_url}\n\n"
        "Si tenés algún problema, contame."
    ),
    "already_connected": (
        "¡Ya tenés tu cuenta de MercadoLibre conectada! 🎉\n"
        "Mandame una foto de lo que querés vender o contame qué producto querés publicar."
    ),
    "oauth_success": (
        "✅ ¡Tu cuenta de MercadoLibre fue conectada con éxito!\n"
        "Ya podés empezar a publicar. Mandame una foto del producto o contame qué querés vender. 📸"
    ),
    "unclear": (
        "No estoy seguro de haber entendido. 🤔\n"
        "{pending_question}\n\n"
        "También podés preguntarme si tenés alguna duda."
    ),
    "reset": (
        "🔄 Listo, reinicié el proceso.\n\n"
        "👋 Soy tu asistente para publicar en MercadoLibre.\n"
        "Para empezar necesito conectar tu cuenta.\n"
        "¿Ya tenés una cuenta? Respondé *sí* o *no*."
    ),
}


class OnboardingService:
    def __init__(self, db: Session):
        self.db = db

    # ── User & session management ──

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
            .filter(
                OnboardingSession.user_id == user_id,
                OnboardingSession.completed == False,
            )
            .first()
        )

        # Auto-expire stale sessions
        if session and session.created_at:
            age = datetime.utcnow() - session.created_at
            if age > timedelta(minutes=SESSION_TTL_MINUTES):
                logger.info(f"Session expired for user {user_id} (age: {age})")
                session.completed = True
                self.db.commit()
                session = None

        if not session:
            session = OnboardingSession(user_id=user_id, state="welcome", data={"history": []})
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
        return session

    def _reset_session(self, user_id) -> OnboardingSession:
        """Close any active session and create a fresh one."""
        active = (
            self.db.query(OnboardingSession)
            .filter(
                OnboardingSession.user_id == user_id,
                OnboardingSession.completed == False,
            )
            .all()
        )
        for s in active:
            s.completed = True

        new_session = OnboardingSession(user_id=user_id, state="account_check", data={"history": []})
        self.db.add(new_session)
        self.db.commit()
        self.db.refresh(new_session)
        return new_session

    # ── Conversation history helpers ──

    def _get_history(self, session: OnboardingSession) -> list[dict]:
        data = session.data or {}
        return data.get("history", [])

    def _append_history(self, session: OnboardingSession, user_msg: str, bot_msg: str):
        data = dict(session.data) if session.data else {}
        history = list(data.get("history", []))
        history.append({"user": user_msg, "assistant": bot_msg})
        # Keep only last N exchanges
        data["history"] = history[-MAX_HISTORY:]
        session.data = data
        self.db.commit()

    # ── Clients ──

    def _get_ml_client(self) -> MercadoLibreClient:
        redirect_uri = settings.ML_REDIRECT_URI or f"{settings.BACKEND_BASE_URL}/api/v1/auth/ml/callback"
        return MercadoLibreClient(
            app_id=settings.ML_APP_ID,
            app_secret=settings.ML_APP_SECRET,
            redirect_uri=redirect_uri,
        )

    def _get_claude_client(self) -> ClaudeClient:
        return ClaudeClient(api_key=settings.ANTHROPIC_API_KEY)

    # ── Main entry point ──

    async def process_step(self, phone: str, message: str) -> dict:
        """Main entry point — routes to the right handler based on session state."""
        user = self._get_or_create_user(phone)

        # Handle reset command — works even if already connected
        if message.strip().lower() in RESET_COMMANDS:
            user.ml_connected = False
            user.is_onboarded = False
            self.db.commit()
            self._reset_session(user.id)
            return {"response": MESSAGES["reset"], "completed": False}

        # Already fully connected — skip onboarding
        if user.ml_connected and user.is_onboarded:
            return {"response": MESSAGES["already_connected"], "completed": True}

        session = self._get_or_create_session(user.id)

        handler = {
            "welcome": self._handle_welcome,
            "account_check": self._handle_account_check,
            "oauth_pending": self._handle_oauth_pending,
            "registration_pending": self._handle_registration_pending,
        }.get(session.state)

        if not handler:
            return {"response": MESSAGES["already_connected"], "completed": True}

        return await handler(user, session, message)

    # ── State handlers ──

    async def _handle_welcome(self, user: User, session: OnboardingSession, message: str) -> dict:
        """First contact — greet and ask if they have an ML account."""
        session.state = "account_check"
        # Initialize history
        data = dict(session.data) if session.data else {}
        data["history"] = []
        session.data = data
        self.db.commit()

        response_text = MESSAGES["welcome"]
        self._append_history(session, message or "(primer mensaje)", response_text)
        return {"response": response_text, "completed": False}

    async def _handle_account_check(self, user: User, session: OnboardingSession, message: str) -> dict:
        """User should answer yes/no about having an ML account."""
        claude = self._get_claude_client()
        history = self._get_history(session)
        result = await claude.classify_and_respond(message, "account_check", history=history)

        if result["intent"] == "yes":
            # Has account — send OAuth link
            ml = self._get_ml_client()
            oauth_url = ml.build_oauth_url(user.phone)
            session.state = "oauth_pending"
            data = dict(session.data) if session.data else {}
            data["oauth_url"] = oauth_url
            session.data = data
            self.db.commit()
            response_text = MESSAGES["oauth_link"].format(oauth_url=oauth_url)
            self._append_history(session, message, response_text)
            return {"response": response_text, "completed": False}

        if result["intent"] == "no":
            # No account — guide to register
            session.state = "registration_pending"
            self.db.commit()
            response_text = MESSAGES["registration_guide"]
            self._append_history(session, message, response_text)
            return {"response": response_text, "completed": False}

        if result["intent"] in ("question", "problem"):
            # Answer the question/problem, then nudge back to the pending question
            nudge = PENDING_QUESTIONS.get("account_check", "")
            response_text = f"{result['response']}\n\n{nudge}"
            self._append_history(session, message, response_text)
            return {"response": response_text, "completed": False}

        # "other" — unclear
        pending = PENDING_QUESTIONS.get("account_check", "")
        response_text = MESSAGES["unclear"].format(pending_question=pending)
        self._append_history(session, message, response_text)
        return {"response": response_text, "completed": False}

    async def _handle_oauth_pending(self, user: User, session: OnboardingSession, message: str) -> dict:
        """Waiting for OAuth callback. Now handles questions and problems."""
        # Check if OAuth completed between messages
        self.db.refresh(user)
        if user.ml_connected:
            session.state = "completed"
            session.completed = True
            self.db.commit()
            return {"response": MESSAGES["oauth_success"], "completed": True}

        data = session.data or {}
        oauth_url = data.get("oauth_url", "")
        if not oauth_url:
            ml = self._get_ml_client()
            oauth_url = ml.build_oauth_url(user.phone)

        claude = self._get_claude_client()
        history = self._get_history(session)
        result = await claude.classify_and_respond(message, "oauth_pending", history=history)

        if result["intent"] in ("question", "problem"):
            response_text = f"{result['response']}\n\nAcá tenés el link de nuevo:\n{oauth_url}"
            self._append_history(session, message, response_text)
            return {"response": response_text, "completed": False}

        # For yes/no/other — remind them about the link
        response_text = MESSAGES["oauth_waiting"].format(oauth_url=oauth_url)
        self._append_history(session, message, response_text)
        return {"response": response_text, "completed": False}

    async def _handle_registration_pending(self, user: User, session: OnboardingSession, message: str) -> dict:
        """User was told to create ML account. Now handles questions and problems."""
        claude = self._get_claude_client()
        history = self._get_history(session)
        result = await claude.classify_and_respond(message, "registration_pending", history=history)

        if result["intent"] == "yes":
            # They created the account — send OAuth link
            ml = self._get_ml_client()
            oauth_url = ml.build_oauth_url(user.phone)
            session.state = "oauth_pending"
            data = dict(session.data) if session.data else {}
            data["oauth_url"] = oauth_url
            session.data = data
            self.db.commit()
            response_text = MESSAGES["oauth_link"].format(oauth_url=oauth_url)
            self._append_history(session, message, response_text)
            return {"response": response_text, "completed": False}

        if result["intent"] in ("question", "problem"):
            nudge = PENDING_QUESTIONS.get("registration_pending", "")
            response_text = f"{result['response']}\n\n{nudge}"
            self._append_history(session, message, response_text)
            return {"response": response_text, "completed": False}

        if result["intent"] == "no":
            response_text = (
                f"No te preocupes, tomate tu tiempo. Creá tu cuenta acá:\n\n"
                f"{ML_REGISTER_URL}\n\n"
                f"Cuando la tengas, escribime y te ayudo a conectarla."
            )
            self._append_history(session, message, response_text)
            return {"response": response_text, "completed": False}

        # "other"
        response_text = MESSAGES["registration_followup"]
        self._append_history(session, message, response_text)
        return {"response": response_text, "completed": False}

    # ── OAuth completion (called from callback endpoint) ──

    def complete_oauth(
        self,
        user: User,
        access_token: str,
        refresh_token: str,
        expires_at,
        ml_user_id: str,
    ):
        """Called from the OAuth callback endpoint — not from WhatsApp flow."""
        user.ml_access_token = access_token
        user.ml_refresh_token = refresh_token
        user.ml_token_expires_at = expires_at
        user.ml_user_id = ml_user_id
        user.ml_connected = True
        user.is_onboarded = True

        # Close any active onboarding session
        active_session = (
            self.db.query(OnboardingSession)
            .filter(
                OnboardingSession.user_id == user.id,
                OnboardingSession.completed == False,
            )
            .first()
        )
        if active_session:
            active_session.state = "completed"
            active_session.completed = True

        self.db.commit()

    def get_status(self, phone: str) -> dict:
        user = self.db.query(User).filter(User.phone == phone).first()
        if not user:
            return {
                "phone": phone,
                "state": "not_started",
                "completed": False,
                "ml_connected": False,
                "data": {},
            }

        session = (
            self.db.query(OnboardingSession)
            .filter(OnboardingSession.user_id == user.id)
            .order_by(OnboardingSession.created_at.desc())
            .first()
        )

        return {
            "phone": phone,
            "state": session.state if session else "not_started",
            "completed": session.completed if session else False,
            "ml_connected": user.ml_connected,
            "data": session.data if session else {},
        }
