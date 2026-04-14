import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from .models import Publication, PublicationStatus, Category, Media, AgentSession
from .agent_service import AgentService

logger = logging.getLogger(__name__)

settings = get_settings()


class PublicationService:
    def __init__(self, db: Session):
        self.db = db

    async def process_message(self, user_id: UUID, message: str, image_url: str | None = None) -> dict:
        # If no Anthropic key configured, fallback to simple response
        if not settings.ANTHROPIC_API_KEY:
            return {"response": "El agente de publicacion no esta configurado. Falta ANTHROPIC_API_KEY."}

        # Find active agent session for this user
        agent_session = (
            self.db.query(AgentSession)
            .filter(AgentSession.user_id == user_id, AgentSession.completed == False)
            .order_by(AgentSession.created_at.desc())
            .first()
        )

        agent = AgentService(self.db)
        result = await agent.process_message(
            user_id=user_id,
            session_id=agent_session.session_id if agent_session else None,
            message=message,
            image_url=image_url,
        )

        # Persist session if new
        if not agent_session:
            agent_session = AgentSession(
                user_id=user_id,
                session_id=result["session_id"],
            )
            self.db.add(agent_session)

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
