from typing import List
from fastapi import Request

def _convert_value(val):
    # Handle boolean-like values
    if isinstance(val, str):
        if val.lower() in ("true", "on", "1", "yes"):
            return True
        if val.lower() in ("false", "off", "0", "no"):
            return False
    return val

async def build_payload(request: Request, boolean_fields: List[str] = []):
    """
    Helper to build a dict payload from a FastAPI request, handling both form and JSON.
    Handles boolean values for form data.
    """
    if request.headers.get("content-type", "").startswith("application/json"):
        data = await request.json()
        # Optionally, handle boolean conversion for JSON as well
        if isinstance(data, dict):
            return {k: _convert_value(v) for k, v in data.items()}
        return data
    else:
        form = await request.form()
        # Convert form data to dict and handle boolean values
        data = {k: _convert_value(v) for k, v in dict(form).items()}
        
        for field in boolean_fields:
            if field not in data.keys():
                data[field] = False
        
        return data