import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.shared.models.user import User
from .models import Publication, PublicationStatus, Category, Media, AgentSession
from .agent_service import AgentService

logger = logging.getLogger(__name__)

settings = get_settings()

SESSION_TTL_MINUTES = 60


class PublicationService:
    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_session(self, user_id: UUID) -> AgentSession:
        """Find an active agent session or create a new one."""
        session = (
            self.db.query(AgentSession)
            .filter(AgentSession.user_id == user_id, AgentSession.completed == False)
            .order_by(AgentSession.created_at.desc())
            .first()
        )

        # Auto-expire stale sessions
        if session and session.created_at:
            age = datetime.utcnow() - session.created_at
            if age > timedelta(minutes=SESSION_TTL_MINUTES):
                print(f"[PUB] Session expired for user {user_id} (age: {age})", flush=True)
                session.completed = True
                self.db.commit()
                session = None

        if not session:
            session = AgentSession(
                user_id=user_id,
                session_id="local",  # legacy column
                data={"messages": []},
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

        return session

    async def process_message(self, user_id: UUID, message: str, image_url: str | None = None) -> dict:
        if not settings.ANTHROPIC_API_KEY:
            return {"response": "El agente de publicacion no esta configurado. Falta ANTHROPIC_API_KEY."}

        # Get user's ML access token for authenticated ML API calls
        user = self.db.query(User).filter(User.id == user_id).first()
        access_token = user.ml_access_token if user else None

        # Find or create agent session with conversation history
        agent_session = self._get_or_create_session(user_id)
        data = agent_session.data or {}
        history = data.get("messages", [])

        # Store image_url from first photo — reuse across messages
        if image_url:
            data["image_url"] = image_url
        stored_image_url = data.get("image_url")

        agent = AgentService()
        result = await agent.process_message(
            message=message,
            image_url=stored_image_url,
            access_token=access_token,
            history=history,
        )

        # Persist updated conversation history + image_url
        agent_session.data = {"messages": result["messages"], "image_url": stored_image_url}
        if result.get("completed"):
            agent_session.completed = True
        self.db.commit()

        return {"response": result["response"]}

    async def create_publication(self, user_id: UUID, data: dict) -> Publication:
        pub = Publication(
            user_id=user_id,
            title=data["title"],
            body=data["body"],
            category_id=data.get("category_id"),
            status=PublicationStatus.PENDING,
        )
        self.db.add(pub)
        self.db.commit()
        self.db.refresh(pub)
        return pub

    def list_publications(
        self,
        status: str | None = None,
        category: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> list[Publication]:
        query = self.db.query(Publication)

        if status:
            query = query.filter(Publication.status == status)
        if category:
            query = query.join(Category).filter(Category.slug == category)

        query = query.order_by(Publication.created_at.desc())
        return query.offset((page - 1) * limit).limit(limit).all()

    def get_by_id(self, pub_id: str) -> Publication | None:
        return self.db.query(Publication).filter(Publication.id == pub_id).first()

    async def moderate(self, pub_id: str, action: str, reason: str | None = None) -> Publication:
        pub = self.db.query(Publication).filter(Publication.id == pub_id).first()
        if action == "approve":
            pub.status = PublicationStatus.APPROVED
        elif action == "reject":
            pub.status = PublicationStatus.REJECTED
            pub.rejection_reason = reason
        self.db.commit()
        self.db.refresh(pub)
        return pub
