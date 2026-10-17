from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime


class UserBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    username: str = Field(..., min_length=1, max_length = 50, description="Username of the user")
    email: EmailStr = Field(..., max_length=200, description="Email of the user")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Password of the user")
    

class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    image_file : str | None
    image_path : str 

class UserPrivate(UserPublic):
    email: EmailStr

class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    username: str | None = Field(default=None, min_length=1, max_length = 50, description="Username of the user")
    email: str | None = Field(default=None, max_length=200, description="Email of the user")


class Token(BaseModel):
    access_token: str
    token_type: str

class PostBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(..., min_length=1, max_length=100, description="Title of the post")
    content: str = Field(..., min_length=1, description="Content of the post")
    
    

class PostCreate(PostBase):
    pass

class PostUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str | None = Field(default=None, min_length=1, max_length=100, description="Title of the post")
    content: str | None = Field(default=None, min_length=1, description="Content of the post")


class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    author: UserPublic = Field(..., description="Author of the post")
    date_posted: datetime

class PaginatedPostResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    skip: int
    limit: int
    has_more: bool
    
class ForgetPasswordRequest(BaseModel):
    email: EmailStr = Field(..., max_length=200, description="Email of the user")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Token of the user")
    new_password: str = Field(..., min_length=8, description="New password of the user")

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=8, description="Current password of the user")
    new_password: str = Field(..., min_length=8, description="New password of the user")
    