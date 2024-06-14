from typing import Optional
from pydantic import BaseModel
import datetime


class AccountCreation(BaseModel):
    kind_id: int = 19
    phone: Optional[str] = ''
    password: Optional[str] = ''
    info: Optional[dict] = None
    last_rent_time: Optional[datetime.datetime] = None
    creation_time: Optional[datetime.datetime] = None
    humanoid_id: Optional[int] = None
    last_cookies: list[dict] = None
