"""
Serviço de gerenciamento de tarefas.
"""

import unicodedata
from typing import List, Optional, Tuple
from urllib.parse import quote

from ..core import PJEHttpClient
from ..models import Tarefa, ProcessoTarefa
from ..utils import delay, get_logger


def normalizar_texto(texto: str) -> str:
    """Remove acentos e converte para minúsculo."""
    texto_normalizado = unicodedata.normalize('NFKD', texto)
    texto_sem_acento = ''.join(c for c in texto_normalizado if not unicodedata.combining(c))
    return texto_sem_acento.lower().strip()


class TaskService:
    """Serviço para tarefas e processos por tarefa."""
    
    def __init__(self, http_client: PJEHttpClient):
        self.client = http_client
        self.logger = get_logger()
        self.tarefas_cache: List[Tarefa] = []
        self.tarefas_favoritas_cache: List[Tarefa] = []
    
    def limpar_cache(self):
        """Limpa cache de tarefas."""
        self.tarefas_cache.clear()
        self.tarefas_favoritas_cache.clear()
    
    def listar_tarefas(self, force_refresh: bool = False) -> List[Tarefa]:
        """Lista tarefas gerais."""
        if self.tarefas_cache and not force_refresh:
            return self.tarefas_cache
        
        try:
            resp = self.client.api_post(
                "painelUsuario/tarefas",
                {"numeroProcesso": "", "competencia": "", "etiquetas": []}
            )
            if resp.status_code == 200:
                todas = resp.json()
                self.tarefas_cache = [
                    Tarefa.from_dict(t) for t in todas 
                    if t.get('quantidadePendente', 0) > 0
                ]
                self.logger.info(f"Encontradas {len(self.tarefas_cache)} tarefas")
                return self.tarefas_cache
        except Exception as e:
            self.logger.error(f"Erro ao listar tarefas: {e}")
        return []
    
    def listar_tarefas_favoritas(self, force_refresh: bool = False) -> List[Tarefa]:
        """Lista tarefas favoritas."""
        if self.tarefas_favoritas_cache and not force_refresh:
            return self.tarefas_favoritas_cache
        
        try:
            resp = self.client.api_post(
                "painelUsuario/tarefasFavoritas",
                {"numeroProcesso": "", "competencia": "", "etiquetas": []}
            )
            if resp.status_code == 200:
                todas = resp.json()
                self.tarefas_favoritas_cache = [
                    Tarefa.from_dict(t, favorita=True) for t in todas 
                    if t.get('quantidadePendente', 0) > 0
                ]
                self.logger.info(f"Encontradas {len(self.tarefas_favoritas_cache)} tarefas favoritas")
                return self.tarefas_favoritas_cache
        except Exception as e:
            self.logger.error(f"Erro ao listar favoritas: {e}")
        return []
    
    def buscar_tarefa_por_nome(self, nome: str, usar_favoritas: bool = False) -> Optional[Tarefa]:
        """Busca tarefa pelo nome (ignora acentos e maiúsculas)."""
        if usar_favoritas:
            lista = self.tarefas_favoritas_cache or self.listar_tarefas_favoritas()
        else:
            lista = self.tarefas_cache or self.listar_tarefas()
        
        # Normaliza o nome buscado (remove acentos, minúsculo)
        nome_normalizado = normalizar_texto(nome)
        
        # Busca exata (normalizada)
        for t in lista:
            if normalizar_texto(t.nome) == nome_normalizado:
                self.logger.info(f"Tarefa encontrada: {t.nome}")
                return t
        
        # Busca parcial (normalizada)
        for t in lista:
            if nome_normalizado in normalizar_texto(t.nome):
                self.logger.info(f"Tarefa encontrada: {t.nome}")
                return t
        
        self.logger.warning(f"Tarefa '{nome}' não encontrada")
        return None
    
    def listar_processos_tarefa(
        self, nome_tarefa: str, page: int = 0, 
        max_results: int = 100, apenas_favoritas: bool = False
    ) -> Tuple[List[ProcessoTarefa], int]:
        """Lista processos de uma tarefa."""
        try:
            endpoint = (
                f"painelUsuario/recuperarProcessosTarefaPendenteComCriterios/"
                f"{quote(nome_tarefa)}/{str(apenas_favoritas).lower()}"
            )
            resp = self.client.api_post(endpoint, {
                "numeroProcesso": "", "classe": None, "tags": [],
                "page": page, "maxResults": max_results, "competencia": ""
            })
            if resp.status_code == 200:
                data = resp.json()
                return [ProcessoTarefa.from_dict(p) for p in data.get("entities", [])], data.get("count", 0)
        except Exception as e:
            self.logger.error(f"Erro ao listar processos: {e}")
        return [], 0
    
    def listar_todos_processos_tarefa(self, nome_tarefa: str, apenas_favoritas: bool = False) -> List[ProcessoTarefa]:
        """Lista TODOS os processos (com paginação)."""
        todos = []
        page = 0
        while True:
            processos, total = self.listar_processos_tarefa(nome_tarefa, page, 100, apenas_favoritas)
            if not processos:
                break
            todos.extend(processos)
            if len(todos) >= total:
                break
            page += 1
            delay(0.5, 1.0)
        return todos
