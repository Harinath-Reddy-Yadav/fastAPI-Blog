from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
#Error handling
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


from typing import Annotated
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import models
from database import Base, engine, get_db
from datetime import datetime, UTC

from contextlib import asynccontextmanager
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler, request_validation_exception_handler
from sqlalchemy.orm import selectinload
from routers import posts, users


#lifespan function
@asynccontextmanager
async def lifespan(_app: FastAPI):
    print("starting up")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    print("shutting down")
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

#Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

#mount media files for user uploaded profile pics
app.mount("/media", StaticFiles(directory="media"), name="media")

#Mount templates
templates = Jinja2Templates(directory="templates")

#Include routers
app.include_router(users.router, prefix="/api/users", tags=["Users"])

app.include_router(posts.router, prefix="/api/posts", tags=["Posts"])

#HTML routes for all posts
@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
async def home(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)))
    posts = result.scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "posts": posts,
            "title": "Home",
            "limit": len(posts),
            "has_more": False,
        },
    )

#HTM route for single post

@app.get("/posts/{post_id}", include_in_schema=False, name="post_page")
async def get_post(
    request:Request, 
    post_id:int, 
    db: Annotated[AsyncSession, Depends(get_db)]
    ):
    #validate whether the post exists
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    return templates.TemplateResponse(
                request=request,
                name="post.html",
                context={
                    "id":post_id,
                    "post": post,
                    "title": post.title,
                },
            )


#Html rout for user post
@app.get("/users/{user_id}/posts", include_in_schema=False, name="user_posts")
async def get_user_posts(request:Request, user_id:int, db:Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).options(selectinload(models.User.posts)).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    posts = user.posts
    return templates.TemplateResponse(
                request=request,
                name="user_posts.html",
                context={
                    "id":user_id,
                    "posts": posts,
                    "title": f"{user.username}'s posts",
                },
            )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    
    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request=request,exc=exc)

    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
           "status_code":status.HTTP_422_UNPROCESSABLE_ENTITY,
           "message":"Invalid request. Please check your imput and try again"
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api"):
        return await default_http_exception_handler(
            request=request,
            exc=exc
        )
    message = (
        exc.detail if exc.detail else "An error occured during processing. Please check your input and try again"
    )    
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
           "status_code":exc.status_code,
           "message":message,
           "title":f"{exc.status_code} Error"
        },
    ) 