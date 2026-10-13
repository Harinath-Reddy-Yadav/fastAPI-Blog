from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime


class PostBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(..., min_length=1, max_length=100, description="Title of the post")
    content: str = Field(..., min_length=1, description="Content of the post")
    
    

class PostCreate(PostBase):
    user_id: int = Field(..., description="ID of the author")

class PostUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str | None = Field(default=None, min_length=1, max_length=100, description="Title of the post")
    content: str | None = Field(default=None, min_length=1, description="Content of the post")


class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    author: UserResponse = Field(..., description="Author of the post")
    date_posted: datetime


class UserBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    username: str = Field(..., min_length=1, max_length = 50, description="Username of the user")
    email: EmailStr = Field(..., max_length=200, description="Email of the user")

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    image_file : str | None
    image_path : str 

class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    username: str | None = Field(default=None, min_length=1, max_length = 50, description="Username of the user")
    email: str | None = Field(default=None, max_length=200, description="Email of the user")
    image_file: str | None  = Field(default=None, description="Filename of the profile picture")