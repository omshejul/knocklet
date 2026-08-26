from typing import Literal

from ninja import NinjaAPI, Schema, Status

from .cli_login import LoginAlreadyRunning, LoginManager


class HealthOut(Schema):
    status: Literal["ok"]


class LoginStatusOut(Schema):
    status: Literal["idle", "waiting", "authenticated", "failed"]
    message: str
    started_at: str | None
    updated_at: str


api = NinjaAPI(title="LinkedIn CLI local API", version="0.1.0")
login_manager = LoginManager()


@api.get("/health", response=HealthOut)
def health(request):
    return {"status": "ok"}


@api.get("/auth/status", response=LoginStatusOut)
def auth_status(request):
    return login_manager.status().to_dict()


@api.post("/auth/login", response={202: LoginStatusOut, 409: LoginStatusOut})
def start_login(request):
    try:
        return Status(202, login_manager.start().to_dict())
    except LoginAlreadyRunning:
        return Status(409, login_manager.status().to_dict())
