from pydantic import BaseModel


class OTPSendResponse(BaseModel):
    session_token: str
    expires_in: int
    message: str


class OTPValidateRequest(BaseModel):
    session_token: str
    code: str


class OTPValidateResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
