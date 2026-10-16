from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from datetime import datetime, UTC
from auth import CurrentUser

import models
from database import get_db
from schemas import PostCreate, PostResponse, PostUpdate

router = APIRouter()



#Fetching all posts
@router.get("", response_model=list[PostResponse])
async def get_posts(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .order_by(models.Post.date_posted.desc())
        )
    posts = result.scalars().all()
    return posts

#Creating a post
@router.post("", response_model=PostResponse)
async def create_post(post:PostCreate, current_user:CurrentUser, db: Annotated [AsyncSession, Depends(get_db)]):
    
    new_post = models.Post(
        title=post.title,
        content=post.content,
        date_posted=datetime.now(UTC),
        user_id=current_user.id,
    )
    db.add(new_post)
    try:
        await db.commit()
        await db.refresh(new_post, attribute_names=['author'])
        return new_post
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Post creation failed",
        )    

# Url path parameters and fetching individual post
@router.get("/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: Annotated [AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  #ERROR HANDLING
    return post

#Put request for updating a post
@router.put("/{post_id}", response_model=PostResponse)
async def update_post_full(post_id: int,post_data:PostCreate, current_user:CurrentUser, db: Annotated [AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  #ERROR HANDLING
    
    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to update this post")

    post.title = post_data.title
    post.content = post_data.content
    post.user_id = current_user.id
    post.date_posted = datetime.now(UTC)
    await db.commit()
    await db.refresh(post, attribute_names=['author'])
    return post

#Patch request for partial update
@router.patch("/{post_id}", response_model=PostResponse)
async def update_post_partial(post_id: int,post_data:PostUpdate, current_user:CurrentUser, db: Annotated [AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to update this post")

    update_date = post_data.model_dump(exclude_unset=True)
    
    for key, value in update_date.items():
        setattr(post, key, value)
    
    post.user_id = current_user.id
    post.date_posted = datetime.now(UTC)
    await db.commit()
    await db.refresh(post, attribute_names=['author'])
    return post


#Delete post
@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: int, current_user: CurrentUser, db: Annotated [AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  #ERROR HANDLING
    
    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to delete this post")
    
    await db.delete(post)
    await db.commit()
    return  #No response for 204

