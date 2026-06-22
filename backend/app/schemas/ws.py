from pydantic import BaseModel


class WSIn(BaseModel):
    type: str
    payload: dict = {}


class WSOut(BaseModel):
    type: str
    payload: dict = {}
