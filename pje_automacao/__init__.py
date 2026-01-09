"""
PJE Automacao - Sistema de automacao do PJE TJBA.

Exemplo de uso:
    from pje_automacao import PJEAutomacao
    
    pje = PJEAutomacao(download_dir="./downloads")
    pje.login()
    pje.selecionar_perfil("V DOS FEITOS...")
    
    tarefas = pje.listar_tarefas()
    for t in tarefas:
        print(f"{t.nome}: {t.quantidade_pendente}")
    
    relatorio = pje.processar_tarefa("Minutar sentenca")
    pje.close()
"""

from .client import PJEAutomacao
from .config import TIPO_DOCUMENTO

__version__ = "2.0.0"
__all__ = ["PJEAutomacao", "TIPO_DOCUMENTO"]
