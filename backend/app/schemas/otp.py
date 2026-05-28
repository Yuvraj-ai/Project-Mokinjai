from pydantic import BaseModel


class OTPSendRequest(BaseModel):
    """Request to generate and send an OTP. No body needed — authenticated by config."""
    pass


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
    message: str = "Admin login successful"
