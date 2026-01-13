"""
Utilitários compartilhados do sistema PJE.
"""

import re
import json
import time
import random
import unicodedata
import logging
import sys
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Optional, List


# FUNÇÕES DE TEMPO E DELAY

def delay(min_sec: float = 1.0, max_sec: float = 3.0) -> None:
    """Pausa execução por tempo aleatório."""
    time.sleep(random.uniform(min_sec, max_sec))


def timestamp_str() -> str:
    """Timestamp para nomes de arquivo."""
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def current_month_year() -> str:
    """Mês/ano atual no formato MM/YYYY."""
    return datetime.now().strftime("%m/%Y")


# FUNÇÕES DE STRING

def normalizar_nome_pasta(nome: str) -> str:
    """Normaliza nome para uso em sistema de arquivos."""
    nome_normalizado = unicodedata.normalize('NFKD', nome)
    nome_sem_acento = ''.join(c for c in nome_normalizado if not unicodedata.combining(c))
    nome_limpo = re.sub(r'[<>:"/\\|?*]', '_', nome_sem_acento)
    nome_limpo = re.sub(r'\s+', ' ', nome_limpo).strip()
    return nome_limpo


def calcular_similaridade(str1: str, str2: str) -> float:
    """Calcula similaridade entre duas strings (0.0 a 1.0)."""
    str1 = str1.lower().strip()
    str2 = str2.lower().strip()
    return SequenceMatcher(None, str1, str2).ratio()


def buscar_texto_similar(
    busca: str, 
    lista: List[str], 
    threshold: float = 0.6
) -> Optional[int]:
    """
    Busca texto similar em uma lista.
    Retorna índice do item mais similar ou None.
    """
    busca_lower = busca.lower().strip()
    
    # Busca exata
    for i, item in enumerate(lista):
        if item.lower().strip() == busca_lower:
            return i
    
    # Busca por conteúdo
    for i, item in enumerate(lista):
        if busca_lower in item.lower():
            return i
    
    # Busca por similaridade
    melhor_match = None
    melhor_score = 0.0
    
    for i, item in enumerate(lista):
        score = calcular_similaridade(busca, item)
        if score > melhor_score and score >= threshold:
            melhor_score = score
            melhor_match = i
    
    return melhor_match


# FUNÇÕES DE HTML/VIEWSTATE

def extrair_viewstate(html: str) -> Optional[str]:
    """Extrai ViewState de HTML JSF."""
    match = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]*)"', html)
    return match.group(1) if match else None


# FUNÇÕES DE ARQUIVO

def save_json(data: Any, filepath: Path) -> None:
    """Salva dados em JSON."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(filepath: Path) -> Optional[Any]:
    """Carrega dados de JSON."""
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# LOGGER

class PJELogger:
    """Logger customizado para o sistema PJE."""
    
    _instances = {}
    
    def __new__(cls, name: str = "pje", log_dir: Optional[Path] = None, debug: bool = False):
        # Singleton por nome
        if name not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[name] = instance
        return cls._instances[name]
    
    def __init__(self, name: str = "pje", log_dir: Optional[Path] = None, debug: bool = False):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        self.name = name
        self.debug_mode = debug
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        self.logger.handlers.clear()
        
        # Console handler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG if debug else logging.INFO)
        console.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(console)
        
        # File handler
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(
                log_dir / f"pje_{datetime.now().strftime('%Y%m%d')}.log",
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            self.logger.addHandler(file_handler)
    
    def info(self, msg: str): self.logger.info(msg)
    def debug(self, msg: str): self.logger.debug(msg)
    def warning(self, msg: str): self.logger.warning(msg)
    def error(self, msg: str): self.logger.error(msg)
    def success(self, msg: str): self.logger.info(f"[OK] {msg}")
    
    def section(self, title: str, char: str = "=", width: int = 60):
        self.logger.info(char * width)
        self.logger.info(title)
        self.logger.info(char * width)


def get_logger(name: str = "pje", log_dir: Optional[Path] = None, debug: bool = False) -> PJELogger:
    """Obtém instância do logger."""
    return PJELogger(name, log_dir, debug)
