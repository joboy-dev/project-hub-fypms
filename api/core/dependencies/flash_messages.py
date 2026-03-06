import enum
from fastapi import Request


class MessageCategory(enum.Enum):
    
    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'
    SUCCESS = 'success'
    

def flash(
    request: Request, 
    message: str, 
    category: MessageCategory = MessageCategory.INFO
):
    '''Function to flash a message on screen'''
    
    try:
        if '_messages' not in request.session:
            request.session['_messages'] = []
        
        message_dict = {
            'category': category.value,
            'message': message
        }
        
        request.session['_messages'].append(message_dict)
    except Exception:
        # Session might not be available, skip flash message
        pass


def get_flashed_messages(request: Request):
    '''Function to retrieve and clear flashed messages'''
    
    try:
        if '_messages' in request.session:
            messages = request.session.pop('_messages')
            return messages
    except Exception:
        # Session might not be available
        pass
    
    return []
