"""Authentication helpers for Mi Fitness cloud API."""

import logging

import keyring

logger = logging.getLogger(__name__)


SERVICE_NAME = "mi-fitness-mcp"
ACCOUNT_NAME = "mi_fitness_auth"


def save_mi_fitness_token(user_id: str, pass_token: str) -> None:
    try:
        keyring.set_password(SERVICE_NAME, f"{ACCOUNT_NAME}_user_id", user_id)
        keyring.set_password(SERVICE_NAME, f"{ACCOUNT_NAME}_pass_token", pass_token)
    except Exception as exc:
        logger.error("Failed to save Mi Fitness credentials: %s", exc)
        raise


def load_mi_fitness_token() -> tuple[str | None, str | None]:
    try:
        user_id = keyring.get_password(SERVICE_NAME, f"{ACCOUNT_NAME}_user_id")
        pass_token = keyring.get_password(SERVICE_NAME, f"{ACCOUNT_NAME}_pass_token")
        return user_id, pass_token
    except Exception as exc:
        logger.error("Failed to load Mi Fitness credentials: %s", exc)
        return None, None


def delete_mi_fitness_token() -> None:
    try:
        keyring.delete_password(SERVICE_NAME, f"{ACCOUNT_NAME}_user_id")
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception as exc:
        logger.error("Failed to delete Mi Fitness user_id: %s", exc)
    try:
        keyring.delete_password(SERVICE_NAME, f"{ACCOUNT_NAME}_pass_token")
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception as exc:
        logger.error("Failed to delete Mi Fitness passToken: %s", exc)
