from typing import Any, Optional, Annotated
import datetime as dt
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyQuery
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from decouple import config

from api.core.dependencies.email_sending_service import send_email
from api.db.database import get_db
from api.utils.loggers import create_logger
from api.utils.settings import settings
from api.v1.models.token import BlacklistedToken, Token, TokenType
from api.v1.models.user import User, UserRole
from api.v1.schemas.token import TokenData
from api.v1.services.token import TokenService


bearer_scheme = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = create_logger(__name__)


class AuthService:
    
    @classmethod
    def authenticate(cls, db: Session, email: str, password: str, create_token: bool=True):
        user = User.fetch_one_by_field(
            db=db, 
            email=email, 
            error_message='Invalid user credentials',
        )

        if not user.is_active:
            raise HTTPException(status_code=400, detail="User is inactive")
        
        if user.password and not cls.verify_hash(password, user.password):
            raise HTTPException(status_code=400, detail="Invalid user credentials")
        
        # Update last_login of user
        user = User.update(db, user.id, last_login=dt.datetime.now())
        
        if create_token:
            access_token = cls.create_access_token(db, user.id)
            refresh_token = cls.create_refresh_token(db, user.id)
            
            return user, access_token, refresh_token
        
        return user, None, None
    
    @classmethod
    def hash_secret(cls, secret: str):
        return pwd_context.hash(secret)
    
    @classmethod
    def verify_hash(cls, secret: str, hash: str):
        return pwd_context.verify(secret, hash)
    
    @classmethod
    def create_access_token(cls, db: Session, user_id: str, expiry_in_minutes: Optional[int] = None):
        
        # Check if user has a token already
        TokenService.check_and_revoke_existing_token(db, user_id=user_id, token_type=TokenType.ACCESS.value)
        
        encoded_jwt = TokenService.create_token(
            db=db,
            token_type=TokenType.ACCESS.value,
            expiry_in_minutes=expiry_in_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            user_id=user_id
        )
        return encoded_jwt

    @classmethod
    def create_refresh_token(cls, db: Session, user_id: str, expiry_in_minutes: Optional[int] = None):
        
        # Check if user has a token already and it has not expired
        TokenService.check_and_revoke_existing_token(db, user_id=user_id, token_type=TokenType.REFRESH.value)
        
        encoded_jwt = TokenService.create_token(
            db=db,
            token_type=TokenType.REFRESH.value,
            expiry_in_minutes=expiry_in_minutes or settings.REFRESH_TOKEN_EXPIRE_MINUTES,
            user_id=user_id
        )
        return encoded_jwt
    
    @classmethod
    def verify_token(cls, db: Session, token: str, expected_token_type: str, credentials_exception):
        """Base function to verify a token to get the user id"""
        
        payload = TokenService.decode_and_verify_token(
            db=db,
            token=token,
            expected_token_type=expected_token_type,
            credentials_exception=credentials_exception
        )
        
        user_id = payload.get("user_id")
        return user_id
        
    
    @classmethod
    def verify_access_token(cls, db: Session, access_token: str, credentials_exception):
        """Funtcion to decode and verify access token"""
        
        user_id = cls.verify_token(
            db=db,
            token=access_token,
            expected_token_type=TokenType.ACCESS.value,
            credentials_exception=credentials_exception
        )
        
        token_data = TokenData(user_id=user_id)
        return token_data

    @classmethod
    def verify_refresh_token(cls, db: Session, refresh_token: str, credentials_exception):
        """Funtcion to decode and verify refresh token"""
        
        user_id = cls.verify_token(
            db=db,
            token=refresh_token,
            expected_token_type=TokenType.REFRESH.value,
            credentials_exception=credentials_exception
        )
        
        token_data = TokenData(user_id=user_id)
        return token_data
    
    @classmethod
    def refresh_access_token(cls, db: Session, current_refresh_token: str):
        """Function to generate new access token and rotate refresh token"""

        credentials_exception = HTTPException(
            status_code=401, detail="Refresh token expired"
        )

        token = cls.verify_refresh_token(
            db=db, 
            refresh_token=current_refresh_token, 
            credentials_exception=credentials_exception
        )

        if token:
            access = cls.create_access_token(db=db, user_id=token.user_id)
            refresh = cls.create_refresh_token(db=db, user_id=token.user_id)

            return access, refresh
    
    @classmethod
    def logout(cls, db: Session, user_id: str):
        """Function to log a user out of their account"""
        
        # get both access and refresh tokens of the user
        access_token_obj = Token.fetch_one_by_field(db=db, user_id=user_id, token_type='access')
        refresh_token_obj = Token.fetch_one_by_field(db=db, user_id=user_id, token_type='refresh')
        
        # Revoke both tokens
        TokenService.revoke_token(db, access_token_obj.token, user_id)
        TokenService.revoke_token(db, refresh_token_obj.token, user_id)
        
    @classmethod
    def send_magic_link(cls, db: Session, email: str, bg_tasks: BackgroundTasks):
        """Function to send magic link to user"""
        
        user = User.fetch_one_by_field(db=db, email=email)
        
        # Check and revoke existing token
        TokenService.check_and_revoke_existing_token(db, user_id=user.id, token_type=TokenType.MAGIC.value)
        
        expiry_minutes = 15
        # Generate a magic link token
        magic_link_token = TokenService.create_token(
            db=db, 
            token_type=TokenType.MAGIC.value,
            expiry_in_minutes=expiry_minutes,
            user_id=user.id,
        )
        
        # TODO: Update the url
        # bg_tasks.add_task(
        #     send_email,
        #     recipients=[user.email],
        #     template_name='magic-login.html',
        #     subject='Securely log in to your account',
        #     template_data={
        #         'user': user,
        #         'magic_link': f"{config('AUTH_APP_URL')}/magic/verify",
        #         'token': magic_link_token,
        #         'expiry_minutes': expiry_minutes
        #     }
        # )
        
        return magic_link_token

    @classmethod
    def verify_magic_token(cls, db:Session, token: str):
        """Function to verify the magic link token"""
        
        credentials_exception = HTTPException(
            status_code=401, detail="Invalid token"
        )
        
        user_id = cls.verify_token(
            db=db,
            token=token,
            expected_token_type=TokenType.MAGIC.value,
            credentials_exception=credentials_exception
        )
        
        user = User.fetch_by_id(db, user_id)
        access_token = cls.create_access_token(db, user.id)
        refresh_token = cls.create_refresh_token(db, user.id)
        
        # Revoke token
        TokenService.revoke_token(db, token, user_id)

        return user, access_token, refresh_token
    
    
    @classmethod
    async def send_password_reset_link(cls, db: Session, email: str, bg_tasks: BackgroundTasks, base_url: str = ''):
        """Function to send password reset link to user"""
        
        user = User.fetch_one_by_field(db=db, email=email)
        
        # Check and revoke existing token
        TokenService.check_and_revoke_existing_token(db, user_id=user.id, token_type=TokenType.PASSWORD_RESET.value)
        
        expiry_minutes = 15
        # Generate a password reset token
        password_reset_token = TokenService.create_token(
            db=db, 
            token_type=TokenType.PASSWORD_RESET.value,
            expiry_in_minutes=expiry_minutes,
            user_id=user.id,
        )

        reset_url = f"{base_url.rstrip('/')}/auth/reset-password?token={password_reset_token}"

        bg_tasks.add_task(
            send_email,
            recipients=[user.email],
            template_name='password_reset.html',
            subject='ProjectHub - Reset Your Password',
            template_data={
                'user_name': user.first_name,
                'reset_url': reset_url,
                'expiry_minutes': expiry_minutes,
            }
        )
        
        return password_reset_token

    @classmethod
    def verify_password_reset_token(cls, db:Session, token: str):
        """Function to verify the password reset token"""
        
        credentials_exception = HTTPException(
            status_code=401, detail="Invalid token"
        )
        
        user_id = cls.verify_token(
            db=db,
            token=token,
            expected_token_type=TokenType.PASSWORD_RESET.value,
            credentials_exception=credentials_exception
        )
        
        TokenService.revoke_token(db, token, user_id)
        
        return user_id
    
    
    @classmethod
    def _validate_token(cls, db: Session, token: HTTPAuthorizationCredentials, credentials_exception):
        '''THis function validates the access token'''
        
        try:
            # Extract the token from the HTTPBearer credentials
            token_str = token.credentials

            # Verify the token
            token_data = cls.verify_access_token(
                db=db, 
                access_token=token_str, 
                credentials_exception=credentials_exception
            )
            
            user = User.fetch_by_id(db, token_data.user_id)
            
            return user
        
        except AttributeError:
            raise credentials_exception
        
        except Exception as e:
            logger.error(e)
            raise credentials_exception
        
    
    @classmethod
    def get_current_user(
        cls, 
        token: HTTPAuthorizationCredentials = Depends(bearer_scheme), 
        db: Session = Depends(get_db)
    ):
        """Function to get current logged-in user"""
        
        credentials_exception = HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        user = cls._validate_token(db, token, credentials_exception)
        return user
    
    
    @classmethod
    def is_user_admin(cls, db: Session, user_id: str):
        user = User.fetch_by_id(db, user_id, "User does not exist")
        
        if user.role != UserRole.ADMIN.value:
            raise HTTPException(403, "Permission denied")
