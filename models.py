# future annotations should be top for models but from 3.14 it's not required, just a good practice
from __future__ import annotations
from datetime import datetime, UTC
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from config import settings



class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    image_file: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    
    posts : Mapped[list["Post"]] = relationship(back_populates="author", cascade="all, delete-orphan")
    password_reset_tokens : Mapped[list["PasswordResetToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def image_path(self) -> str:
        if self.image_file:
            return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.S3_REGION}.amazonaws.com/profile_pics/{self.image_file}"
        else:
            #local image path
            return f"/static/profile_pics/default.jpg"
    


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    date_posted: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=lambda:datetime.now(UTC)) #sqlite store datetime in string so using lamda function
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  ## Importatnt when we add the not null columj to the databse which has data already

    author: Mapped["User"] = relationship(back_populates="posts")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=lambda:datetime.now(UTC)
        )
        
    user: Mapped["User"] = relationship(back_populates="password_reset_tokens")