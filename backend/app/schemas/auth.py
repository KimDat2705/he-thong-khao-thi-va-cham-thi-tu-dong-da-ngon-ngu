from pydantic import BaseModel, ConfigDict

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str

class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginPayload(BaseModel):
    username: str
    password: str
