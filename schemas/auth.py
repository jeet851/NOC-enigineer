from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    username: str
    password: str

class VerifyOtpRequest(BaseModel):
    challengeId: str
    otp: str

class LoginOtpResponse(BaseModel):
    otpRequired: bool = True
    challengeId: str
    simulatedOtp: str

class UserInfo(BaseModel):
    username: str
    role: str
    name: str

class LoginSuccessResponse(BaseModel):
    token: str          # Backward compatibility field
    accessToken: str
    refreshToken: str
    user: UserInfo

class TokenRefreshRequest(BaseModel):
    refreshToken: str
