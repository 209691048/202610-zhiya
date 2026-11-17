from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api.v1.health import router
from app.api.v1.auth import router as auth_router
from app.api.v1.auth import error
from app.api.v1.profiles import router as profiles_router
from app.api.v1.storybooks import router as storybooks_router

app = FastAPI(title="知芽 API")
app.include_router(router)
app.include_router(auth_router)
app.include_router(profiles_router)
app.include_router(storybooks_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return error(422, "VALIDATION_ERROR", "请检查请求字段")
