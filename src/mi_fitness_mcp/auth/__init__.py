"""Authentication helpers for Mi Fitness cloud API."""

import logging

import keyring

logger = logging.getLogger(__name__)


SERVICE_NAME = "mi-fitness-mcp"
ACCOUNT_NAME = "mi_fitness_auth"

# Module/class name fragments of keyring backends that store secrets weakly
# or not at all (fail, null, keyrings.alt plaintext/file backends).
_WEAK_BACKEND_MARKERS = ("fail", "null", "plaintext", "keyrings.alt")


def keyring_backend_warning() -> str | None:
    """Return a warning when the active keyring backend is weak, else None.

    Detection is heuristic and never raises: a backend we cannot inspect is
    reported as unknown rather than crashing setup/doctor.
    """
    try:
        backend = keyring.get_keyring()
    except Exception as exc:
        return f"无法确定 keyring 后端（{exc}）；凭据可能不会被安全存储"
    name = f"{type(backend).__module__}.{type(backend).__name__}"
    if any(marker in name.lower() for marker in _WEAK_BACKEND_MARKERS):
        return (
            f"当前 keyring 后端 {name} 不安全（明文存储或不可用）；"
            "passToken 可能以明文落盘，请配置系统钥匙串后重试"
        )
    return None


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
