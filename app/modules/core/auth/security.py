import bcrypt
import jwt
import os
from utils.enums import JwtStatus
from settings.app import AppSettings
from modules.logging.client import DbLogger, LogLevel
from modules.core.user.models import User


def hash_password(password: str) -> str:
    """Returns hashed user password using bcrypt"""

    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())


def check_password(password: str, hashed_password: str) -> bool:
    """Compares users password with hashed password"""

    if bcrypt.checkpw(password.encode(), hashed_password.encode()):
        return True
    else:
        return False


def encode_jwt(payload: dict) -> bytes:
    """
    Returns an encoded JWT token for supplied payload
    :param payload: JWT payload to be encoded
    :type payload: dict
    :return: Encoded JWT token
    :rtype: bytes
    """
    key = os.getenv("JWT_SECRET")

    encoded = jwt.encode(payload, key, algorithm="HS256")

    return encoded


def decode_jwt(token: bytes) -> dict:
    """Returns a decoded JWT's payload"""

    key = os.getenv("JWT_SECRET")

    try:
        decoded = jwt.decode(
            token,
            key,
            algorithms="HS256",
            issuer=AppSettings.JWT_ISSUER,
            options={"require": ["exp", "iss", "email"]},
        )
    except jwt.ExpiredSignatureError:
        return JwtStatus.expired

    except jwt.InvalidIssuerError:
        DbLogger(
            LogLevel.ERROR, __name__, "Attempted to "
                                      "decode token with invalid issuer."
        ).save()
        return JwtStatus.invalid_issuer

    except jwt.InvalidTokenError:
        DbLogger(LogLevel.WARN, __name__, "Attempted to "
                                          "decode an invalid token").save()
        return JwtStatus.decode_error

    else:
        return decoded


def get_token_from_request_header(info: dict) -> str:
    """Parses the Bearer token from the authorization request header"""
    # TODO: [AUTH] Request token, do some more validation

    token = info.context["request"].headers['authorization'].split(' ')[1]

    return token


def get_user_from_token(token: str) -> User:
    """Retrieves the tokens user from the database"""
    decoded = decode_jwt(token)
    email = decoded["email"]
    user = User.objects(email=email).first()

    if user is not None:
        return user
    else:
        DbLogger(LogLevel.ERROR, __name__,
                 "We decoded a valid token but did not find the user with "
                 "corresponding email in the database!")

    raise ValueError("User not found.")