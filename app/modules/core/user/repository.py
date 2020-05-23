from .models import User
from modules.core.user.validators import validate_email
from modules.core.auth.security import get_token_from_request_header, \
                                       get_user_from_token


def fetch_all_users(skip=0, take=25):
    return User.objects[skip:take+skip]


def find_user_by_email(email: str):
    if validate_email(email):
        return User.objects(email=email).first()
    else:
        raise ValueError("Invalid email provided.")


def me(info):
    token = get_token_from_request_header(info.context)

    if token is not None:
        user = get_user_from_token(token)
        return user

    raise ValueError("User not found.")