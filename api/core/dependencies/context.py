import datetime as dt
from functools import wraps
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import RedirectResponse


def inject_context(request: Request):
    return {
        "request": request,
        "app_name": "ProjectHub",
        "app_version": "1.0.0",
        "footer_message": "Final Year Project Management System",
        "year": dt.datetime.now().year
    }
  
  
def add_template_context(template_path: str):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs) -> Response:
            # Get the template engine from the request app state to avoid circular imports
            frontend = request.app.state.frontend
                        
            # Get additional context from the injected dependency
            context_data = inject_context(request)
                        
            # Run the route function to get extra context data from the function itself
            result = await func(request, *args, **kwargs)
            
            # Check if the function returned a RedirectResponse (usually for POST redirection)
            if isinstance(result, RedirectResponse):
                return result
            
            # Merge function data with context_data
            context = {
                'page': template_path.split('/')[-1].replace('.html', ''),
                **context_data, 
                **result
            }
            
            return frontend.TemplateResponse(template_path, context)
        return wrapper
    return decorator  
