from modules.core.user.models import User
from modules.core.auth.repository import AuthRepository

_repo = AuthRepository()


def resolve_register_user(_, info, data: dict) -> User:
    """
    Resolver for registering a new user
    :param data: The users data to register
    :type data: dict
    :return: Registered User
    :rtype: User
    """
    user = _repo.register_user(data)

    return user


def resolve_login_user(_, info, data: dict) -> User:
    """
    Resolver for logging in a user
    """
    user = _repo.login_user(data)

    return user