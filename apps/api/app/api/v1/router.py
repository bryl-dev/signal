from fastapi import APIRouter

from app.api.v1 import auth, documents, feed, health, interests, stories, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(interests.router)
api_router.include_router(documents.router)
api_router.include_router(stories.router)
api_router.include_router(feed.router)
