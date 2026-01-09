"""
Gerenciador de sessao HTTP com persistencia de cookies.
"""

import json
import time
import pickle
import requests
from pathlib import Path
from datetime import datetime


class SessionManager:
    """
    Gerencia persistencia de sessao (cookies) em disco.
    Permite restaurar sessoes entre execucoes do script.
    """
    
    def __init__(self, session_dir: str = ".session"):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.cookies_file = self.session_dir / "cookies.pkl"
        self.session_info_file = self.session_dir / "session_info.json"
    
    def save(self, session: requests.Session) -> bool:
        """Salva cookies da sessao em arquivo."""
        try:
            with open(self.cookies_file, 'wb') as f:
                pickle.dump(session.cookies, f)
            
            session_info = {
                "saved_at": datetime.now().isoformat(),
                "timestamp": time.time()
            }
            with open(self.session_info_file, 'w', encoding='utf-8') as f:
                json.dump(session_info, f, indent=2)
            
            return True
        except Exception:
            return False
    
    def load(self, session: requests.Session) -> bool:
        """Carrega cookies salvos para a sessao."""
        if not self.cookies_file.exists():
            return False
        
        try:
            with open(self.cookies_file, 'rb') as f:
                cookies = pickle.load(f)
            session.cookies.update(cookies)
            return True
        except Exception:
            return False
    
    def is_valid(self, max_age_hours: int = 8) -> bool:
        """Verifica se a sessao salva ainda e valida."""
        if not self.session_info_file.exists():
            return False
        
        try:
            with open(self.session_info_file, 'r', encoding='utf-8') as f:
                info = json.load(f)
            
            saved_timestamp = info.get("timestamp", 0)
            age_hours = (time.time() - saved_timestamp) / 3600
            
            return age_hours < max_age_hours
        except Exception:
            return False
    
    def clear(self):
        """Remove arquivos de sessao salvos."""
        if self.cookies_file.exists():
            self.cookies_file.unlink()
        if self.session_info_file.exists():
            self.session_info_file.unlink()
