from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

import models
from schemas import UserCreate, UserResponse,UserUpdate, PostResponse
from database import get_db

router = APIRouter()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    #Check whether user exists with same username
    result = await db.execute(select(models.User).where(models.User.username == user.username))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this username already exists",
        )
    
    #Checking whether user exists with same email
    result = await db.execute(select(models.User).where(models.User.email == user.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )   
    
    #Creating new user
    new_user = models.User(
        username=user.username,
        email=user.email,
    )
    db.add(new_user) #no need of await, becasue it just add a object to the sessions pending list in memory
    try:
        await db.commit() #await is used here, becasue it write the data to the database
        await db.refresh(new_user)
        return new_user
    except IntegrityError as e:
        await db.rollback() #await is used here, becasue it rollback the transaction
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists",
        )    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )    

#API for user details
@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user    

#API for returning user posts
@router.get("/{user_id}/posts", response_model=list[PostResponse])
async def get_user_posts(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    #Test user exists
    result = await db.execute(select(models.User).options(selectinload(models.User.posts)).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    #Fetch the user posts
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.user_id == user_id))
    posts= result.scalars().all()

    #Test if any posts are found for the user
    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No posts found for this user",
        )    
    
    return posts   


#patch request for user
@router.patch("/{user_id}", response_model=UserResponse) 
async def update_user_partial(user_id:int, user_data: UserUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    #validate the username exists for other users
    if user_data.username:
        result = await db.execute(select(models.User).where(models.User.username == user_data.username))
        existing_user = result.scalar_one_or_none()
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )
    if user_data.email:
        result = await db.execute(select(models.User).where(models.User.email == user_data.email))
        existing_user_email = result.scalar_one_or_none()
        if existing_user_email and existing_user_email.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists",
            )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    update_date = user_data.model_dump(exclude_unset=True)
    for key, value in update_date.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return user

#Delete user
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    await db.delete(user) #We need to await here compared to db.add becasue delete needs to update the database
    await db.commit()
    return