from uuid import UUID

from sqlalchemy.orm import Session

from .models import Publication, PublicationStatus, Category, Media

PUBLICATION_STEPS = [
    {"step": 0, "field": "category", "prompt": "Que queres publicar?\n1. Venta\n2. Servicio\n3. Evento\n4. Otro"},
    {"step": 1, "field": "title", "prompt": "Dale un titulo a tu publicacion:"},
    {"step": 2, "field": "body", "prompt": "Escribi la descripcion:"},
    {"step": 3, "field": "media", "prompt": "Envia una foto (o escribi 'omitir'):"},
    {"step": 4, "field": "confirm", "prompt": "Tu publicacion:\n\n*{title}*\n{body}\n\nConfirmar? (si/no)"},
]


class PublicationService:
    def __init__(self, db: Session):
        self.db = db

    async def process_message(self, user_id: UUID, message: str, image_url: str | None = None) -> dict:
        if message.lower() in ["publicar", "nueva", "crear"]:
            return {"response": PUBLICATION_STEPS[0]["prompt"]}

        # TODO: implementar flujo paso a paso con session (similar a onboarding)
        return {"response": "Escribi 'publicar' para crear una nueva publicacion."}

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
