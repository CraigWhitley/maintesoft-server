import bcrypt
import jwt
import os
from .enums import JwtStatus
from modules.core.logging.logging_service import LoggingService
from modules.core.logging.models import LogEntry, LogLevel
from modules.core.user.models import User
from .models import BlacklistedToken
import functools
from graphql import GraphQLResolveInfo
from modules.core.role.errors import UnauthorizedError
from .settings import AuthSettings


class AuthService:

    _logger = LoggingService(True)

    def hash_password(self, password: str) -> str:
        """Returns hashed user password using bcrypt"""

        return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    def check_password(self, password: str, hashed_password: str) -> bool:
        """Compares users password with hashed password"""

        if bcrypt.checkpw(password.encode(), hashed_password.encode()):
            return True
        else:
            return False

    def get_logger(self):
        return self._logger

    def encode_jwt(self, payload: dict) -> bytes:
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

    def decode_jwt(self, token: bytes) -> dict:
        """Returns a decoded JWT's payload"""

        key = os.getenv("JWT_SECRET")

        try:
            decoded = jwt.decode(
                token,
                key,
                algorithms="HS256",
                issuer=AuthSettings.JWT_ISSUER,
                options={"require": ["exp", "iss", "email"]},
            )
        except jwt.ExpiredSignatureError:
            self._logger.log(LogEntry(
                        LogLevel.INFO,
                        __name__,
                        "JWT Token expired for user."))
            raise jwt.ExpiredSignatureError("Expired token.")
            # return JwtStatus.EXPIRED

        except jwt.InvalidIssuerError:
            self._logger.log(LogEntry(
                        LogLevel.ERROR,
                        __name__,
                        "Attempted to decode token with invalid issuer."))
            raise jwt.InvalidIssuerError("Invalid JWT Issuer.")
            # return JwtStatus.INVALID_ISSUER

        except jwt.InvalidTokenError:
            self._logger.log(LogEntry(
                    LogLevel.ERROR,
                    __name__,
                    "JWT decoding error when trying to decode token."))
            raise jwt.InvalidTokenError("Invalid token.")
            # return JwtStatus.DECODE_ERROR

        return decoded

    def get_token_from_request_header(self, context: dict) -> str:
        """Parses the Bearer token from the authorization request header"""

        if "authorization" not in context["request"].headers:
            # TODO: [AUTH] Log the attempts from context?
            raise ValueError("Unauthorized. Please login.")

        token = context["request"].headers["authorization"].split(' ')

        if token[0] != "Bearer":
            raise ValueError("Unauthorized. Please login.")

        black_token = BlacklistedToken.objects(token=token[1]).first()

        if black_token is not None:
            raise ValueError("Unauthorized. Please login.")

        return token[1]

    def get_user_from_token(self, token: str) -> User:
        """Retrieves the tokens user from the database"""

        if token is None:
            raise ValueError("Token not found.")

        decoded = self.decode_jwt(token)

        # FIXME [AUTH] JwtStatus object is not subscriptable.
        # https://stackoverflow.com/questions/216972/what-does-it-mean-if-a-python-object-is-subscriptable-or-not
        # We're not handling the JwtStatus errors
        email = decoded["email"]

        user = User.objects(email=email).first()

        if user is not None:
            return user
        else:
            self._logger.log(LogEntry(
                    LogLevel.ERROR,
                    __name__,
                    "We decoded a valid token but did not find the "
                    "user with corresponding email in the database!"))

        raise ValueError("User not found.")


_auth = AuthService()


# TODO: [TEST] authenticate(permission) decorator
def authenticate(permission):
    """
    Decorator to authenticate queries and mutations on a
    route-by-route basis using the users request JWT token.
    """
    def decorator_repeat(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):

            error = "You do not have permission to access this resource."
            request = None

            for x in args:
                if isinstance(x, GraphQLResolveInfo):
                    request = x

            if request is None:
                raise UnauthorizedError(error)

            token = _auth.get_token_from_request_header(request.context)

            if token is None:
                raise UnauthorizedError(error)

            user = _auth.get_user_from_token(token)

            if user is None:
                raise UnauthorizedError(error)

            # blacklist takes precedence
            for perm in user.blacklist:
                if perm.route == permission:
                    _auth.get_logger().log(LogEntry(
                        LogLevel.WARN,
                        __name__,
                        "User {} tried to access blacklisted route"
                        .format(user.email)
                    ))
                    raise UnauthorizedError(error)

            for perm in user.whitelist:
                if perm.route == permission:
                    value = func(*args, **kwargs)
                    return value

            for role in user.roles:
                for perm in role.permissions:
                    if perm.route == permission:
                        value = func(*args, **kwargs)
                        return value

            _auth.get_logger().log(LogEntry(
                        LogLevel.WARN,
                        __name__,
                        "User {} tried to access route with no permission."
                        .format(user.email)))
            raise UnauthorizedError(error)
        return wrapper
    return decorator_repeat