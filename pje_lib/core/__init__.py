"""Módulo core - componentes fundamentais."""

from .session_manager import SessionManager
from .http_client import PJEHttpClient

__all__ = ["SessionManager", "PJEHttpClient"]
