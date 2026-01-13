"""
Gerenciador de sessão HTTP.
"""

import json
import pickle
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests

from ..config import MAX_SESSION_AGE_HOURS


class SessionManager:
    """Gerencia persistência de sessão (cookies)."""
    
    def __init__(self, session_dir: str = ".session"):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.cookies_file = self.session_dir / "cookies.pkl"
        self.session_info_file = self.session_dir / "session_info.json"
    
    def save_session(self, session: requests.Session) -> bool:
        """Salva cookies da sessão."""
        try:
            with open(self.cookies_file, 'wb') as f:
                pickle.dump(session.cookies, f)
            
            with open(self.session_info_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "saved_at": datetime.now().isoformat(),
                    "timestamp": time.time()
                }, f, indent=2)
            return True
        except Exception:
            return False
    
    def load_session(self, session: requests.Session) -> bool:
        """Carrega cookies salvos."""
        if not self.cookies_file.exists():
            return False
        try:
            with open(self.cookies_file, 'rb') as f:
                session.cookies.update(pickle.load(f))
            return True
        except Exception:
            return False
    
    def is_session_valid(self, max_age_hours: Optional[int] = None) -> bool:
        """Verifica se sessão ainda é válida."""
        max_age = max_age_hours or MAX_SESSION_AGE_HOURS
        if not self.session_info_file.exists():
            return False
        try:
            with open(self.session_info_file, 'r') as f:
                info = json.load(f)
            age_hours = (time.time() - info.get("timestamp", 0)) / 3600
            return age_hours < max_age
        except Exception:
            return False
    
    def clear_session(self):
        """Remove sessão salva."""
        if self.cookies_file.exists():
            self.cookies_file.unlink()
        if self.session_info_file.exists():
            self.session_info_file.unlink()
