"""
PJE Lib - Biblioteca compartilhada para automação do PJE.

Esta biblioteca pode ser importada por qualquer script na raiz do projeto.

Uso básico:
    from pje_lib import PJEClient
    
    pje = PJEClient()
    pje.login()
    pje.select_profile("Assessoria")
    pje.processar_tarefa("Minutar sentença")
    pje.close()

Uso avançado (acesso aos serviços individuais):
    from pje_lib import PJEClient
    from pje_lib.services import DownloadService
    from pje_lib.models import Processo, Tarefa
"""

import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path.cwd() / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

from .client import PJEClient
from .config import (
    BASE_URL, SSO_URL, API_BASE,
    TIPO_DOCUMENTO_VALUES,
    DEFAULT_TIMEOUT, DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX,
)
from .models import (
    Usuario, Perfil, Tarefa, ProcessoTarefa,
    Etiqueta, Processo, DownloadDisponivel,
    DiagnosticoDownload,
)

__version__ = "2.0.0"
__all__ = [
    "PJEClient",
    "BASE_URL", "SSO_URL", "API_BASE", "TIPO_DOCUMENTO_VALUES",
    "Usuario", "Perfil", "Tarefa", "ProcessoTarefa",
    "Etiqueta", "Processo", "DownloadDisponivel", "DiagnosticoDownload",
]
