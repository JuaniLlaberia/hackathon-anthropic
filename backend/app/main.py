from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.webhook.router import router as webhook_router
from app.onboarding.router import router as onboarding_router
from app.publication.router import router as publication_router
from app.auth.router import router as auth_router

app = FastAPI(title="Hackathon Bot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)
app.include_router(onboarding_router)
app.include_router(publication_router)
app.include_router(auth_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
