# Plan de hackathon — Bot WhatsApp (Onboarding + Publicación)

## Stack tecnológico

| Componente | Tecnología |
| --- | --- |
| Bot WhatsApp | Kapso (no-code, webhooks) |
| Backend / API | Python 3.11+ con FastAPI |
| Base de datos | PostgreSQL en Neon |
| ORM | SQLAlchemy + Alembic (migraciones) |
| Validación | Pydantic v2 |
| Frontend | React (Vite) o Next.js |
| Auth | JWT (python-jose) |
| Storage imágenes | Cloudinary o S3 (según disponibilidad) |

---

## Estructura del repositorio (monorepo)

`hackathon-bot/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app + CORS
│   │   ├── config.py                # Settings (env vars)
│   │   ├── database.py              # Engine + SessionLocal
│   │   │
│   │   ├── shared/                  # ⚠️ ZONA COMPARTIDA — ambos grupos
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── user.py          # Modelo User
│   │   │   │   └── base.py          # Base declarativa
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   └── user.py          # UserCreate, UserResponse
│   │   │   ├── deps.py              # get_db, get_current_user
│   │   │   └── auth.py              # JWT encode/decode
│   │   │
│   │   ├── onboarding/              # 🟢 GRUPO A — solo tocan esta carpeta
│   │   │   ├── __init__.py
│   │   │   ├── router.py            # /api/v1/onboarding/*
│   │   │   ├── service.py           # Lógica de negocio
│   │   │   ├── schemas.py           # Schemas propios
│   │   │   └── models.py            # Profile, OnboardingStep
│   │   │
│   │   ├── publication/             # 🟠 GRUPO B — solo tocan esta carpeta
│   │   │   ├── __init__.py
│   │   │   ├── router.py            # /api/v1/publications/*
│   │   │   ├── service.py           # Lógica de negocio
│   │   │   ├── schemas.py           # Schemas propios
│   │   │   └── models.py            # Publication, Media, Category
│   │   │
│   │   └── webhook/                 # ⚠️ COMPARTIDO — router del webhook de Kapso
│   │       ├── __init__.py
│   │       ├── router.py            # POST /api/v1/webhook
│   │       └── dispatcher.py        # Decide si va a onboarding o publication
│   │
│   ├── alembic/
│   │   ├── versions/                # Migraciones (cada grupo las suyas)
│   │   └── env.py
│   ├── alembic.ini
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── shared/                  # ⚠️ COMPARTIDO
│   │   │   ├── api/
│   │   │   │   └── client.ts        # Axios instance + interceptors
│   │   │   ├── components/
│   │   │   │   ├── Layout.tsx
│   │   │   │   ├── Navbar.tsx
│   │   │   │   └── ProtectedRoute.tsx
│   │   │   ├── hooks/
│   │   │   │   └── useAuth.ts
│   │   │   └── types/
│   │   │       └── user.ts          # Interface User
│   │   │
│   │   ├── onboarding/              # 🟢 GRUPO A
│   │   │   ├── pages/
│   │   │   │   ├── AdminDashboard.tsx
│   │   │   │   └── UserList.tsx
│   │   │   └── components/
│   │   │       ├── UserCard.tsx
│   │   │       └── OnboardingStats.tsx
│   │   │
│   │   ├── publication/             # 🟠 GRUPO B
│   │   │   ├── pages/
│   │   │   │   ├── Feed.tsx
│   │   │   │   ├── PublicationDetail.tsx
│   │   │   │   └── ModerationPanel.tsx
│   │   │   └── components/
│   │   │       ├── PublicationCard.tsx
│   │   │       ├── CategoryFilter.tsx
│   │   │       └── MediaGallery.tsx
│   │   │
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── .env.example
│
├── database/
│   └── init.sql                     # Schema base (se genera con Alembic)
│
├── docs/
│   ├── API_CONTRACT.md              # Contrato de API entre grupos
│   ├── DB_SCHEMA.md                 # Schema de la DB
│   └── KAPSO_FLOWS.md               # Documentación de flujos en Kapso
│
├── .gitignore
├── docker-compose.yml               # (opcional, para dev local)
└── README.md`

---

## Contrato compartido — Lo que se define PRIMERO (ambos grupos juntos)

Antes de que cada grupo empiece a trabajar, los dos equipos se sientan 30 minutos y definen juntos lo siguiente.

### 1. Modelo User (tabla `users`)

python

`# backend/app/shared/models/user.py
from sqlalchemy import Column, String, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from .base import Base
import uuid
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    email = Column(String(150), nullable=True)
    is_verified = Column(Boolean, default=False)
    is_onboarded = Column(Boolean, default=False)
    role = Column(String(20), default="user")  # user | admin | moderator
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)`

### 2. Schema User compartido

python

`# backend/app/shared/schemas/user.py
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    phone: str
    name: Optional[str] = None
    email: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: UUID
    is_verified: bool
    is_onboarded: bool
    role: str
    created_at: datetime

    class Config:
        from_attributes = True`

### 3. Webhook dispatcher (el router central)

python

`# backend/app/webhook/dispatcher.py
from app.shared.models.user import User

async def dispatch_message(phone: str, message: str, db):
    """
    Decide si el mensaje va a onboarding o a publication.
    REGLA: si el usuario no existe o no completó onboarding → onboarding
            si ya está onboarded → publication menu
    """
    user = db.query(User).filter(User.phone == phone).first()

    if not user or not user.is_onboarded:
        # Grupo A se encarga
        return {"module": "onboarding", "user": user, "message": message}
    else:
        # Grupo B se encarga
        return {"module": "publication", "user": user, "message": message}`

### 4. Endpoints acordados (API Contract)

| Método | Ruta | Grupo | Descripción |
| --- | --- | --- | --- |
| POST | `/api/v1/webhook` | Compartido | Recibe webhook de Kapso |
| POST | `/api/v1/onboarding/start` | A | Inicia onboarding |
| POST | `/api/v1/onboarding/step` | A | Avanza paso del onboarding |
| GET | `/api/v1/onboarding/status/{phone}` | A | Estado del onboarding |
| GET | `/api/v1/users` | A | Lista usuarios (admin) |
| GET | `/api/v1/users/{id}` | Compartido | Detalle usuario |
| POST | `/api/v1/publications` | B | Crear publicación |
| GET | `/api/v1/publications` | B | Listar publicaciones (feed) |
| GET | `/api/v1/publications/{id}` | B | Detalle publicación |
| PATCH | `/api/v1/publications/{id}/status` | B | Moderar (aprobar/rechazar) |
| GET | `/api/v1/publications/categories` | B | Listar categorías |
| POST | `/api/v1/publications/{id}/media` | B | Subir imagen |

---

## Plan paso a paso — GRUPO A (Onboarding)

### Fase 1: Setup base (30 min)

1. Clonar el repo y crear la branch `feature/onboarding`.
2. Instalar dependencias: `pip install fastapi uvicorn sqlalchemy alembic psycopg2-binary python-jose pydantic`.
3. Configurar `.env` con la connection string de Neon.
4. Verificar que el modelo `User` compartido ya existe en `shared/models/`.
5. Correr la primera migración de Alembic para crear la tabla `users`.

### Fase 2: Modelos propios (20 min)

python

`# backend/app/onboarding/models.py
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.shared.models.base import Base
import uuid
from datetime import datetime

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    city = Column(String(100))
    bio = Column(String(500))
    avatar_url = Column(String(500))
    preferences = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

class OnboardingSession(Base):
    __tablename__ = "onboarding_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    current_step = Column(Integer, default=0)
    data = Column(JSON, default={})  # Almacena respuestas parciales
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)`

Generar migración: `alembic revision --autogenerate -m "add profiles and onboarding_sessions"`.

### Fase 3: Lógica de negocio (45 min)

python

`# backend/app/onboarding/service.py
ONBOARDING_STEPS = [
    {"step": 0, "field": "name", "prompt": "¡Hola! Bienvenido. ¿Cómo te llamas?"},
    {"step": 1, "field": "email", "prompt": "Genial, {name}. ¿Cuál es tu email?"},
    {"step": 2, "field": "city", "prompt": "¿De qué ciudad sos?"},
    {"step": 3, "field": "bio", "prompt": "Contanos un poco sobre vos (breve bio):"},
]

class OnboardingService:
    def __init__(self, db):
        self.db = db

    async def process_step(self, phone: str, message: str) -> dict:
        """
        Procesa un paso del onboarding.
        Retorna: {"response": str, "completed": bool}
        """
        user = self._get_or_create_user(phone)
        session = self._get_or_create_session(user.id)

        if session.current_step >= len(ONBOARDING_STEPS):
            return {"response": "Ya completaste el registro.", "completed": True}

        # Guardar respuesta del paso actual
        step_config = ONBOARDING_STEPS[session.current_step]
        session.data[step_config["field"]] = message

        # Avanzar al siguiente paso
        session.current_step += 1
        self.db.commit()

        if session.current_step >= len(ONBOARDING_STEPS):
            # Completar onboarding
            self._finalize_onboarding(user, session)
            return {
                "response": "¡Registro completo! Ya podés publicar. Escribí 'publicar' para empezar.",
                "completed": True
            }

        # Enviar siguiente pregunta
        next_step = ONBOARDING_STEPS[session.current_step]
        prompt = next_step["prompt"].format(**session.data)
        return {"response": prompt, "completed": False}`

### Fase 4: Router de endpoints (30 min)

python

`# backend/app/onboarding/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.shared.deps import get_db
from .service import OnboardingService
from .schemas import OnboardingStepRequest, OnboardingStatusResponse

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])

@router.post("/step")
async def process_step(request: OnboardingStepRequest, db: Session = Depends(get_db)):
    service = OnboardingService(db)
    result = await service.process_step(request.phone, request.message)
    return result

@router.get("/status/{phone}", response_model=OnboardingStatusResponse)
async def get_status(phone: str, db: Session = Depends(get_db)):
    service = OnboardingService(db)
    return service.get_status(phone)`

### Fase 5: Configurar Kapso (30 min)

1. Crear el flujo de onboarding en Kapso.
2. Configurar el webhook que llame a `POST /api/v1/webhook`.
3. El dispatcher identifica que el usuario no está registrado y redirige a onboarding.
4. Kapso recibe la respuesta del endpoint y la envía de vuelta al usuario por WhatsApp.
5. Testear el flujo completo: un número nuevo escribe al bot → recibe las preguntas → completa el registro.

### Fase 6: Frontend — Panel admin (45 min)

Crear las páginas en `frontend/src/onboarding/`:

1. `AdminDashboard.tsx` — estadísticas: usuarios registrados hoy, en proceso, completados.
2. `UserList.tsx` — tabla con todos los usuarios, filtros por estado de onboarding.
3. `UserCard.tsx` — detalle de un usuario con su perfil.
4. Consumir endpoints: `GET /api/v1/users`, `GET /api/v1/onboarding/status/{phone}`.

---

## Plan paso a paso — GRUPO B (Publicación)

### Fase 1: Setup base (30 min)

1. Clonar el repo y crear la branch `feature/publication`.
2. Misma instalación de dependencias que Grupo A.
3. Verificar que el modelo `User` y la tabla `users` ya existen (Grupo A corre las migraciones primero).
4. Configurar `.env` con la misma connection string de Neon.

### Fase 2: Modelos propios (30 min)

python

`# backend/app/publication/models.py
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.shared.models.base import Base
import uuid, enum
from datetime import datetime

class PublicationStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)
    slug = Column(String(50), unique=True, nullable=False)

class Publication(Base):
    __tablename__ = "publications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), default=PublicationStatus.DRAFT)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="publications")
    media = relationship("Media", backref="publication", cascade="all, delete-orphan")

class Media(Base):
    __tablename__ = "media"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publication_id = Column(UUID(as_uuid=True), ForeignKey("publications.id"))
    url = Column(String(500), nullable=False)
    media_type = Column(String(20), default="image")  # image | video
    created_at = Column(DateTime, default=datetime.utcnow)`

Generar migración: `alembic revision --autogenerate -m "add publications categories and media"`.

### Fase 3: Lógica de negocio (45 min)

python

`# backend/app/publication/service.py

PUBLICATION_STEPS = [
    {"step": 0, "field": "category", "prompt": "¿Qué querés publicar?\n1. Venta\n2. Servicio\n3. Evento\n4. Otro"},
    {"step": 1, "field": "title", "prompt": "Dale un título a tu publicación:"},
    {"step": 2, "field": "body", "prompt": "Escribí la descripción:"},
    {"step": 3, "field": "media", "prompt": "Enviá una foto (o escribí 'omitir'):"},
    {"step": 4, "field": "confirm", "prompt": "Tu publicación:\n\n*{title}*\n{body}\n\n¿Confirmar? (sí/no)"},
]

class PublicationService:
    def __init__(self, db):
        self.db = db

    async def process_message(self, user_id, message: str) -> dict:
        """
        Gestiona la creación paso a paso de una publicación vía bot.
        """
        session = self._get_or_create_draft(user_id)

        if message.lower() in ["publicar", "nueva", "crear"]:
            return {"response": PUBLICATION_STEPS[0]["prompt"]}

        # Procesar paso actual y avanzar
        # (lógica similar al onboarding service)
        ...

    async def create_publication(self, user_id, data: dict) -> Publication:
        pub = Publication(
            user_id=user_id,
            title=data["title"],
            body=data["body"],
            category_id=data.get("category_id"),
            status=PublicationStatus.PENDING
        )
        self.db.add(pub)
        self.db.commit()
        return pub

    async def moderate(self, pub_id, action: str, reason: str = None):
        pub = self.db.query(Publication).get(pub_id)
        if action == "approve":
            pub.status = PublicationStatus.APPROVED
        elif action == "reject":
            pub.status = PublicationStatus.REJECTED
            pub.rejection_reason = reason
        self.db.commit()
        return pub`

### Fase 4: Router de endpoints (30 min)

python

`# backend/app/publication/router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.shared.deps import get_db
from .service import PublicationService
from .schemas import PublicationCreate, PublicationResponse, ModerationAction
from typing import Optional

router = APIRouter(prefix="/api/v1/publications", tags=["publications"])

@router.post("/", response_model=PublicationResponse)
async def create_publication(data: PublicationCreate, db: Session = Depends(get_db)):
    service = PublicationService(db)
    return await service.create_publication(data.user_id, data.dict())

@router.get("/", response_model=list[PublicationResponse])
async def list_publications(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db)
):
    service = PublicationService(db)
    return service.list_publications(status=status, category=category, page=page, limit=limit)

@router.get("/{pub_id}", response_model=PublicationResponse)
async def get_publication(pub_id: str, db: Session = Depends(get_db)):
    service = PublicationService(db)
    return service.get_by_id(pub_id)

@router.patch("/{pub_id}/status")
async def moderate_publication(pub_id: str, action: ModerationAction, db: Session = Depends(get_db)):
    service = PublicationService(db)
    return await service.moderate(pub_id, action.action, action.reason)

@router.get("/categories")
async def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()`

### Fase 5: Configurar Kapso (30 min)

1. Crear el flujo de publicación en Kapso (separado del flujo de onboarding).
2. El menú principal muestra opciones: "Publicar", "Mis publicaciones", "Ayuda".
3. Al elegir "Publicar" → inicia el flujo de pasos que llama a `POST /api/v1/publications`.
4. Cuando el usuario envía una imagen → Kapso la envía al webhook → se sube a Cloudinary/S3 → se asocia a la publicación.
5. Testear: usuario ya registrado escribe "publicar" → completa los pasos → la publicación queda en estado "pending".

### Fase 6: Frontend — Feed público + moderación (45 min)

Crear las páginas en `frontend/src/publication/`:

1. `Feed.tsx` — lista de publicaciones aprobadas, con filtro por categoría, paginación, búsqueda.
2. `PublicationDetail.tsx` — vista completa de una publicación con galería de imágenes.
3. `ModerationPanel.tsx` — lista de publicaciones pendientes con botones aprobar/rechazar.
4. `PublicationCard.tsx` — tarjeta reutilizable para mostrar cada publicación.
5. Consumir endpoints: `GET /api/v1/publications`, `PATCH /api/v1/publications/{id}/status`.

---

## Reglas para evitar colisiones

1. **Cada grupo trabaja en SU carpeta**: Grupo A solo toca `onboarding/`, Grupo B solo toca `publication/`. Nadie toca `shared/` sin avisar al otro grupo.
2. **Migraciones con prefijo**: Grupo A nombra sus migraciones con prefijo `a_` (ej: `a_001_add_profiles`), Grupo B con `b_` (ej: `b_001_add_publications`). Así Alembic no genera conflictos de merge.
3. **main.py se edita una sola vez al inicio** para registrar ambos routers:

python

`# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.webhook.router import router as webhook_router
from app.onboarding.router import router as onboarding_router
from app.publication.router import router as publication_router

app = FastAPI(title="Hackathon Bot API")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(webhook_router)
app.include_router(onboarding_router)
app.include_router(publication_router)`

1. **Frontend routing se define al inicio**:

tsx

`// frontend/src/App.tsx
<Routes>
  {/* Grupo A */}
  <Route path="/admin" element={<AdminDashboard />} />
  <Route path="/admin/users" element={<UserList />} />

  {/* Grupo B */}
  <Route path="/" element={<Feed />} />
  <Route path="/publication/:id" element={<PublicationDetail />} />
  <Route path="/moderation" element={<ModerationPanel />} />
</Routes>`

1. **Git workflow**: cada grupo trabaja en su branch (`feature/onboarding`, `feature/publication`). Se hace merge a `main` solo cuando un módulo está estable. Si necesitan tocar `shared/`, abren un PR y el otro grupo revisa antes de mergear.

---

## Cronograma sugerido (4 horas de hackathon)

| Hora | Grupo A (Onboarding) | Grupo B (Publicación) | Juntos |
| --- | --- | --- | --- |
| 0:00–0:30 | — | — | Definir contratos: User model, schemas, endpoints, dispatcher |
| 0:30–1:00 | Setup + modelos propios | Setup + modelos propios | — |
| 1:00–1:45 | Service + router | Service + router | — |
| 1:45–2:15 | Configurar Kapso (onboarding) | Configurar Kapso (publicación) | — |
| 2:15–2:30 | — | — | Sync: probar que el dispatcher funciona |
| 2:30–3:15 | Frontend admin panel | Frontend feed + moderación | — |
| 3:15–3:45 | — | — | Integración: flujo completo end-to-end |
| 3:45–4:00 | — | — | Demo prep + testing final |

---

## Checklist de integración final

Cuando ambos grupos terminan, verificar estos puntos:

- [ ]  Un número nuevo escribe al bot → entra al flujo de onboarding (Grupo A)
- [ ]  Completa el onboarding → `is_onboarded = true` en la DB
- [ ]  El mismo número escribe de nuevo → ve el menú principal (Grupo B)
- [ ]  Elige "publicar" → completa los pasos → publicación creada con status "pending"
- [ ]  En el panel de moderación web → se ve la publicación pendiente
- [ ]  Al aprobar → aparece en el feed público
- [ ]  Al rechazar → el usuario recibe notificación por WhatsApp (opcional)
- [ ]  El panel admin muestra la lista de usuarios registrados
- [ ]  Las rutas del frontend no colisionan

---

## Variables de entorno (.env)

env

`# Base de datos
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/hackathon?sslmode=require

# JWT
JWT_SECRET=tu-secreto-seguro-aqui
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# Kapso
KAPSO_WEBHOOK_SECRET=secreto-de-kapso
KAPSO_API_URL=https://api.kapso.io/v1

# Storage (opcional)
CLOUDINARY_URL=cloudinary://key:secret@cloud

# Frontend
VITE_API_URL=http://localhost:8000`

---

## Comandos rápidos

bash

`# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev

# Crear migración
alembic revision --autogenerate -m "descripcion"

# Aplicar migraciones
alembic upgrade head`