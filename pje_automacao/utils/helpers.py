"""
Utilitarios gerais do sistema.
"""

import re
import json
import time
import random
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import Any


class Logger:
    """Logger simples para o sistema."""
    
    def __init__(self, debug: bool = False):
        self.debug_enabled = debug
    
    def info(self, message: str):
        self._log(message, "INFO")
    
    def debug(self, message: str):
        if self.debug_enabled:
            self._log(message, "DEBUG")
    
    def warn(self, message: str):
        self._log(message, "WARN")
    
    def error(self, message: str):
        self._log(message, "ERROR")
    
    def _log(self, message: str, level: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")


def delay(min_sec: float = 1.0, max_sec: float = 3.0):
    """Aguarda um tempo aleatorio entre min e max segundos."""
    time.sleep(random.uniform(min_sec, max_sec))


def save_json(data: Any, filepath: Path):
    """Salva dados em arquivo JSON."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalizar_nome_pasta(nome: str) -> str:
    """Normaliza nome para usar como nome de pasta no sistema de arquivos."""
    # Remove acentos
    nome_normalizado = unicodedata.normalize('NFKD', nome)
    nome_sem_acento = ''.join(c for c in nome_normalizado if not unicodedata.combining(c))
    # Substitui caracteres invalidos
    nome_limpo = re.sub(r'[<>:"/\\|?*]', '_', nome_sem_acento)
    # Remove espacos extras
    return re.sub(r'\s+', ' ', nome_limpo).strip()


def extrair_viewstate(html: str) -> str | None:
    """Extrai o ViewState de uma pagina JSF."""
    match = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]*)"', html)
    return match.group(1) if match else None
