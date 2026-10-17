from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Query, BackgroundTasks
from sqlalchemy import select, func, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

import models
from schemas import (
    UserCreate, 
    UserPrivate,
    UserUpdate, 
    PostResponse, 
    UserPublic, 
    Token, 
    PaginatedPostResponse, 
    ChangePasswordRequest, 
    ForgetPasswordRequest, 
    ResetPasswordRequest
)
from database import get_db
from datetime import timedelta, UTC, datetime
from fastapi.security import OAuth2PasswordRequestForm

from auth import create_access_token, hash_password, verify_password, CurrentUser, generate_reset_token, hash_reset_token
from config import settings
from PIL import UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from image_utils import process_profile_picture, upload_profile_image, delete_profile_image
from email_utils import send_password_reset_email
from botocore.exceptions import ClientError

router = APIRouter()


@router.post("", response_model=UserPrivate, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    #Check whether user exists with same username
    result = await db.execute(select(models.User).where(func.lower(models.User.username) == user.username.lower()))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this username already exists",
        )
    
    #Checking whether user exists with same email
    result = await db.execute(select(models.User).where(func.lower(models.User.email) == user.email.lower()))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )   
    
    #Creating new user
    new_user = models.User(
        username=user.username,
        email=user.email.lower(),
        password_hash = hash_password(user.password)
    )
    db.add(new_user) #no need of await, becasue it just add a object to the sessions pending list in memory
    try:
        await db.commit() #await is used here, becasue it write the data to the database
        await db.refresh(new_user)
        return new_user
    except IntegrityError as e:
        await db.rollback() #await is used here, becasue it rollback the transaction
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error occured: {str(e)}"
        )    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown error occured: {str(e)}",
        )    

@router.post("/token", response_model=Token) 
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Uses OAuth2PasswordRequestForm to get the username and password from the request body
    
    Validates user credentials and issues a JWT token upon successful authentication.
    """
    #Looking user by emnail as here username means email for authentication
    result = await db.execute(
        select(models.User).where(func.lower(models.User.email) == form_data.username.lower())
    )
    user = result.scalar_one_or_none()
    
    # Validate user existence and verify password and don't revel which one failed (Best security practice)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}, 
        )
    
    # Generate access token
    access_token_expires = timedelta(minutes=settings.access_token_expire)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


#Endpoint to get the current user
@router.get("/me", response_model=UserPrivate)
async def get_current_user(current_user:CurrentUser):
    """
    Returns a current user after verification
    """
    return current_user

#API for user details
@router.get("/{user_id}", response_model=UserPublic)
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
@router.get("/{user_id}/posts", response_model=PaginatedPostResponse)
async def get_user_posts(
    user_id: int, 
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)]= 0,
    limit: Annotated[int, Query(ge=1, le=100)] = settings.posts_per_page
    ):
    #Test user exists
    result = await db.execute(select(models.User).options(selectinload(models.User.posts)).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    #Fetch the user posts
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.user_id == user_id)
        .order_by(models.Post.date_posted.desc())
        .offset(skip)
        .limit(limit)
    )
    posts= result.scalars().all()

    #Test if any posts are found for the user
    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No posts found for this user",
        )    

    #Total posts
    count_total = await db.execute(select(func.count()).select_from(models.Post).where(models.Post.user_id == user_id))
    total_posts = count_total.scalar() or 0

    has_more = (skip + len(posts)) < total_posts
    
    return PaginatedPostResponse(
        posts= [PostResponse.model_validate(post) for post in posts],
        total=total_posts,
        skip=skip,
        limit=limit,
        has_more=has_more
    )

#patch request for user
@router.patch("/{user_id}", response_model=UserPrivate) 
async def update_user_partial(user_id: int, user_data: UserUpdate, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    """
    Updates a user's information
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this user",
        )
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Validate if username is changed and already taken by another user
    if user_data and user_data.username and user_data.username.lower() != user.username.lower():
        result = await db.execute(
            select(models.User).where(func.lower(models.User.username) == user_data.username.lower())
        )
        existing_user = result.scalar_one_or_none()
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

    # Validate if email is changed and already taken by another user
    if user_data and user_data.email and user_data.email.lower() != user.email.lower():
        result = await db.execute(
            select(models.User).where(func.lower(models.User.email) == user_data.email.lower())
        )
        existing_user_email = result.scalar_one_or_none()
        if existing_user_email and existing_user_email.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists",
            )

    update_data = user_data.model_dump(exclude_unset=True) if user_data else {}
    for key, value in update_data.items():
        if key == "email" and value:
            value = value.lower()
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return user

#Delete user
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    """
    Deletes a user
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this user",
        )
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    old_filename = user.image_file

    await db.delete(user) #We need to await here compared to db.add becasue delete needs to update the database
    await db.commit()

    if old_filename:
        await delete_profile_image(old_filename)


#Forgot password endpont
@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    request_data: ForgetPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Forgot password endpoint
    """
    result = await db.execute(select(models.User).where(func.lower(models.User.email) == request_data.email.lower()))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    token = generate_reset_token()
    token_hash = hash_reset_token(token)
    expires_at = datetime.now(UTC)+timedelta(minutes=settings.reset_token_expire_minutes)

    reset_token = models.PasswordResetToken(
        user_id=user.id,
        token_hash = token_hash,
        expires_at = expires_at,
    )

    db.add(reset_token)
    await db.commit()

    background_tasks.add_task(
            send_password_reset_email,
            to_email=user.email,
            user_name=user.username,
            token=token,
        )
    return {"message": "If an email exists with this email, you will receive an password reset email with instructions"}
    

#Reset password endpoint 
@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request_data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Reset password endpoint
    """
    token_hash = hash_reset_token(request_data.token)
    
    #validate token exists
    result = await db.execute(
        select(models.PasswordResetToken)
        .where(models.PasswordResetToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired token",
        )
    
    #validate token expired or not
    if token.expires_at < datetime.now(UTC):   #Sqlite way once postgresql migration no need of replace
        await db.delete(token)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token expired, request a new password reset token",
        )
    
    #Fetch the user and raise exception if the user not found
    result = await db.execute(
        select(models.User)
        .where(models.User.id == token.user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid token or user",
        )
    
    user.password_hash = hash_password(request_data.new_password)
    
    #Delete all old reset tokens for the user
    await db.execute(
        sql_delete(models.PasswordResetToken)
        .where(models.PasswordResetToken.user_id == user.id)
    )
    await db.commit()
    await db.refresh(user)

    return {"message": "Password reset successful. You can now log in with your new password"}


#Change password endpoint
@router.patch("/me/change_password", status_code=status.HTTP_200_OK)
async def change_password(
    request_data: ChangePasswordRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Change password endpoint
    """
    #Verify current password
    if not verify_password(request_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid current password",
        )
    current_user.password_hash = hash_password(request_data.new_password)

    #Delete oustanding reset token for best practice
    await db.execute(
        sql_delete(models.PasswordResetToken)
        .where(models.PasswordResetToken.user_id == current_user.id)
    )

    await db.commit()
    await db.refresh(current_user)

    return {"message": "Password changed successfully"}
    

#Profile pic upload endpoint
@router.patch("/{user_id}/profile_pic", response_model=UserPrivate)
async def upload_profile_pic(user_id: int, file: UploadFile, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    """
    Uploads a profile picture for a user
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to upload a profile picture for this user",
        )

    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds the limit of {settings.max_upload_size_bytes} bytes",
        )    

    try:
        processed_bytes, file_name = await run_in_threadpool(process_profile_picture, content)
    
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid image file (JPEG, PNG, GIF or WebP)",
        )    

    try:
        await upload_profile_image(processed_bytes, file_name)
    
    except ClientError as e:
       raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Error uploading profile pic. Please try again {e}",
       )

    old_filename = current_user.image_file
    current_user.image_file = file_name
    await db.commit()
    await db.refresh(current_user)

    # Delete the old profile pic
    if old_filename:
        try:
            await delete_profile_image(old_filename)
        except ClientError as e:
            print(f"Warning: Failed to delete old image {old_filename}: {e}")

    return current_user    

    
#Delete profile picture endpoint
@router.delete("/{user_id}/profile_pic", response_model=UserPrivate)
async def delete_profile_pic(user_id: int, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    """
    Deletes the profile picture of a user
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete the profile picture for this user",
        )
    
    old_filename = current_user.image_file
    if old_filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No profile picture exists",
        )
        
    current_user.image_file = None
    await db.commit()
    await db.refresh(current_user)

    try:
        await delete_profile_image(old_filename)
    
    except ClientError as e:
       return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Error deleting profile picture. please try again"
       )