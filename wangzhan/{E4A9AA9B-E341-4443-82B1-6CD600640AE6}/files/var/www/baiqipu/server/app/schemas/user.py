from pydantic import BaseModel


class UserCreate(BaseModel):
    phone: str | None = None
    nickname: str
    password: str


class UserLogin(BaseModel):
    phone: str
    password: str


class UserOut(BaseModel):
    id: str
    nickname: str
    avatar: str = ""
    role: str = "user"
    tier: str = "new"
    purchase_count: int = 0

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class UserUpdate(BaseModel):
    nickname: str | None = None
    avatar: str | None = None
    phone: str | None = None


class UserProfileOut(UserOut):
    phone: str | None = None
    checkin_streak: int = 0
    total_checkins: int = 0
    last_checkin_date: str | None = None
    created_at: str | None = None
