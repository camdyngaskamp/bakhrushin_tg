from fastapi import FastAPI
from app.api.routes import router
from app.middleware.auth import AuthMiddleware

app = FastAPI(title="Bakhrushin Museum News")
app.add_middleware(AuthMiddleware)
app.include_router(router)
