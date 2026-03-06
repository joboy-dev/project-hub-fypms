from fastapi import HTTPException, Request


def _get_user(request: Request):
    """Return the authenticated user or raise."""
    user = getattr(request.state, 'current_user', None)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def _paginate(request: Request, endpoint: str):
    """Extract page/size from query params."""
    page = int(request.query_params.get('page', 1))
    size = int(request.query_params.get('size', 10))
    return page, size
