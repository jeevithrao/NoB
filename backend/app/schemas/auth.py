import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserOut


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None
    device_identifier: str = Field(min_length=1, max_length=255)
    accepted_terms: bool  # must be true: the Terms/Privacy checkbox
    marketing_opt_in: bool = False  # optional updates checkbox

    @field_validator("accepted_terms")
    @classmethod
    def _terms_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("You must accept the Terms of Service and Privacy Policy.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_identifier: str = Field(min_length=1, max_length=255)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str
    device_identifier: str = Field(min_length=1, max_length=255)


class SignupResponse(BaseModel):
    user_id: uuid.UUID
    message: str = "Account created."


# OTP flow

class OtpRequestBody(BaseModel):
    email: EmailStr


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    device_identifier: str = Field(min_length=1, max_length=255)


# Google Sign-In

class GoogleSignInRequest(BaseModel):
    id_token: str
    device_identifier: str = Field(min_length=1, max_length=255)

