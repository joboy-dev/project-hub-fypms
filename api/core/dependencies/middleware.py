from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from api.db.database import get_db_with_ctx_manager
from api.v1.models.user import User
from api.v1.services.auth import AuthService
from api.core.dependencies.flash_messages import flash, MessageCategory


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

        # Define route access
        self.unauthenticated_routes = [
            "/", "/auth/student", 
            "/auth/supervisor", "/auth/admin",
        ]
        self.protected_prefixes = [
            "/dashboard",
        ]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Check if path matches any protected prefix
        is_protected = any(path == prefix or path.startswith(prefix + "/") for prefix in self.protected_prefixes)

        # Always open DB session
        with get_db_with_ctx_manager() as db:
            access_token = request.cookies.get("access_token")
            refresh_token = request.cookies.get("refresh_token")

            # 1️⃣ If user tries to access a protected page
            if is_protected:
                if not access_token:
                    flash(request, "Please login to access this page.", MessageCategory.ERROR)
                    return RedirectResponse(url="/", status_code=303)
                
                user = await self._get_user_from_token(db, access_token, refresh_token, request)
                if not user:
                    flash(request, "Please login to access this page.", MessageCategory.ERROR)
                    return RedirectResponse(url="/", status_code=303)
                request.state.current_user = user
                return await call_next(request)

            # 2️⃣ If user is already logged in but visits login/register → redirect to dashboard
            if path in self.unauthenticated_routes and access_token:
                user = await self._get_user_from_token(db, access_token, refresh_token, request)
                if user:
                    return RedirectResponse(url="/dashboard", status_code=303)

            # 3️⃣ For any other route (public pages, APIs)
            if access_token:
                user = await self._get_user_from_token(db, access_token, refresh_token, request)
                request.state.current_user = user

            return await call_next(request)

    async def _get_user_from_token(
        self, 
        db: Session, 
        access_token: str, 
        refresh_token: str, 
        request: Request,
    ):
        if not access_token:
            return None
        
        credentials_exception = HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            token = AuthService.verify_access_token(db, access_token, credentials_exception)
            return User.fetch_by_id(db=db, id=token.user_id)
        except HTTPException as e:
            flash(request, e.detail, MessageCategory.ERROR)
            return None
            # Try refreshing the token
            # try:
            #     access, refresh = AuthService.refresh_access_token(db, refresh_token)
            #     response = RedirectResponse(url=request.url.path, status_code=303)
            #     response.set_cookie("access_token", access, httponly=True)
            #     response.set_cookie("refresh_token", refresh, httponly=True)
            #     return None  # Let user reload with new cookies
            # except HTTPException:
            #     return None
