from pydantic import BaseModel

class UserOut(BaseModel):
    user_id: str
    name: str

    class Config:
        from_attributes=True
