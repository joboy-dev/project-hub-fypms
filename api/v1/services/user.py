from datetime import datetime
from typing import List
from fastapi import BackgroundTasks, HTTPException, Request
from fastapi.datastructures import FormData
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from decouple import config

from api.core.dependencies.email_sending_service import send_email
from api.core.dependencies.flash_messages import MessageCategory, flash
from api.utils.loggers import create_logger
from api.utils.telex_notification import TelexNotification
from api.v1.models.token import TokenType
from api.v1.models.user import User, UserRole
from api.v1.services.auth import AuthService
from api.v1.services.token import TokenService


logger = create_logger(__name__)

class UserService:
    @classmethod
    def create(
        cls, 
        db: Session, 
        payload: FormData, 
        bg_tasks: BackgroundTasks,
        role: str = UserRole.STUDENT.value,
        is_active: bool = True,
        create_token: bool = True
    ):
        """Creates a new user"""
        
        first_name = payload.get('first_name', '').strip()
        last_name = payload.get('last_name', '').strip()
        email = payload.get('email').lower().strip()
        
        if not first_name or not last_name:
            raise HTTPException(400, 'First name and last name are required')
        
        user_with_email_exists = User.fetch_one_by_field(db, throw_error=False, email=email)
        if user_with_email_exists:
            raise HTTPException(400, 'User with email already exists')
        
        password = payload.get('password')
        confirm_password = payload.get('confirm_password')
        if password != confirm_password:
            raise HTTPException(400, 'Passwords do not match')
        
        password = AuthService.hash_secret(password)
        
        new_user = User.create(
            db=db,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            role=role,
            is_active=is_active,
        )
        
        if create_token:
            access_token = AuthService.create_access_token(db, new_user.id)
            refresh_token = AuthService.create_refresh_token(db, new_user.id)
        else:
            access_token = None
            refresh_token = None
        
        return new_user, access_token, refresh_token
    
    @classmethod
    def check_user_role(cls, db: Session, user_id: str, allowed_roles: List[str]):
        """Check if the user's role is in the list of allowed roles.
        
        Args:
            db: Database session.
            user_id: The ID of the user to check.
            allowed_roles: A list of role strings (e.g. ['admin', 'supervisor']).
        
        Returns:
            The user object if the role is allowed.
        
        Raises:
            HTTPException(403) if the user's role is not in allowed_roles.
        """
        user = User.fetch_by_id(db, user_id, "User does not exist")
        
        if user.role not in allowed_roles:
            raise HTTPException(403, "Permission denied")
        
        return user
    
    @classmethod
    def verify_password_change(cls, db: Session, email: str, old_password: str, new_password: str):
        """Fucntion to change user password"""
        
        user, _, _ = AuthService.authenticate(
            db, 
            email=email, 
            password=old_password, 
            create_token=False
        )
        
        if new_password == old_password:
            raise HTTPException(400, 'New and old password cannot be the same')
        
        password_hash = AuthService.hash_secret(new_password)
        
        return password_hash
    
    # @classmethod
    # def change_email(cls, db: Session, payload: UpdateUser, user_id: str):
    #     user = User.fetch_one_by_field(db, throw_error=False, email=payload.email)
    #     if user:
    #         raise HTTPException(400, 'Email already in use')
        
    #     user = User.update(db, user_id, email=payload.email)
    #     return user

    @classmethod
    async def send_account_reactivation_token(cls, db: Session, email: str, bg_tasks: BackgroundTasks):
        """Function to send account reactivation token to user"""
        
        user = User.fetch_one_by_field(db=db, email=email)
        
        # Generate a account reactivation token
        expiry_minutes = 1440  # 24 hours
        account_reactivation_token = TokenService.create_token(
            db=db, 
            token_type=TokenType.ACCOUNT_REACTIVATION.value,
            expiry_in_minutes=expiry_minutes,
            user_id=user.id,
        )
        
        # TODO: Update the url
        # bg_tasks.add_task(
        #     send_email,
        #     recipients=[user.email],
        #     template_name='account-reactivate-request.html',
        #     subject='Reactivate your account',
        #     template_data={
        #         'user': user,
        #         'reactivation_url': f"{config('APP_URL')}/users/reactivate-account",
        #         'token': account_reactivation_token,
        #         'expiry_hours': expiry_minutes/60
        #     }
        # )
        
        return account_reactivation_token

    @classmethod
    def verify_account_reactivation_token(cls, db: Session, token: str):
        """Function to verify the account reactivation token"""
        
        credentials_exception = HTTPException(
            status_code=401, detail="Invalid token"
        )
        
        user_id = AuthService.verify_token(
            db=db,
            token=token,
            expected_token_type=TokenType.ACCOUNT_REACTIVATION.value,
            credentials_exception=credentials_exception
        )
        
        TokenService.revoke_token(db, token, user_id)
        
        return user_id  
