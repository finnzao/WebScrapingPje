"""
Servico de gerenciamento de tarefas do PJE.
"""

from typing import List, Optional, Tuple
from urllib.parse import quote

from ..config import API_BASE
from ..models import Tarefa, ProcessoTarefa
from ..utils import Logger, delay
from ..core.auth import AuthService


class TaskService:
    """
    Gerencia listagem e busca de tarefas e processos.
    """
    
    def __init__(self, auth: AuthService, debug: bool = False):
        self.auth = auth
        self.logger = Logger(debug)
        self.tarefas_cache: List[Tarefa] = []
        self.tarefas_favoritas_cache: List[Tarefa] = []
    
    def limpar_cache(self):
        """Limpa cache de tarefas (usar apos trocar perfil)."""
        self.tarefas_cache.clear()
        self.tarefas_favoritas_cache.clear()
    
    def listar_tarefas(self) -> List[Tarefa]:
        """Lista tarefas disponiveis para o perfil atual."""
        if not self.auth.ensure_logged_in():
            return []
        
        try:
            headers = self.auth._get_api_headers()
            self.logger.debug(
                f"Headers: X-pje-usuario-localizacao="
                f"{headers.get('X-pje-usuario-localizacao', 'NAO DEFINIDO')}"
            )
            
            resp = self.auth.session.post(
                f"{API_BASE}/painelUsuario/tarefas",
                json={"numeroProcesso": "", "competencia": "", "etiquetas": []},
                timeout=self.auth.timeout,
                headers=headers
            )
            
            if resp.status_code == 200:
                todas = resp.json()
                self.logger.debug(f"API retornou {len(todas)} tarefas")
                
                # Filtra apenas com processos pendentes
                com_processos = [t for t in todas if t.get('quantidadePendente', 0) > 0]
                self.tarefas_cache = [Tarefa.from_dict(t) for t in com_processos]
                
                self.logger.info(f"Encontradas {len(self.tarefas_cache)} tarefas com processos")
                return self.tarefas_cache
                
        except Exception as e:
            self.logger.error(f"Erro ao listar tarefas: {e}")
        
        return []
    
    def listar_favoritas(self) -> List[Tarefa]:
        """Lista tarefas favoritas do usuario."""
        if not self.auth.ensure_logged_in():
            return []
        
        try:
            resp = self.auth.session.post(
                f"{API_BASE}/painelUsuario/tarefasFavoritas",
                json={"numeroProcesso": "", "competencia": "", "etiquetas": []},
                timeout=self.auth.timeout,
                headers=self.auth._get_api_headers()
            )
            
            if resp.status_code == 200:
                todas = resp.json()
                com_processos = [t for t in todas if t.get('quantidadePendente', 0) > 0]
                self.tarefas_favoritas_cache = [
                    Tarefa.from_dict(t, favorita=True) for t in com_processos
                ]
                
                self.logger.info(f"Encontradas {len(self.tarefas_favoritas_cache)} favoritas")
                return self.tarefas_favoritas_cache
                
        except Exception as e:
            self.logger.error(f"Erro ao listar favoritas: {e}")
        
        return []
    
    def buscar_por_nome(self, nome: str, usar_favoritas: bool = False) -> Optional[Tarefa]:
        """
        Busca uma tarefa pelo nome.
        
        Args:
            nome: Nome da tarefa
            usar_favoritas: Se True, busca nas favoritas
        """
        if usar_favoritas:
            if not self.tarefas_favoritas_cache:
                self.listar_favoritas()
            lista = self.tarefas_favoritas_cache
            tipo = "FAVORITAS"
        else:
            if not self.tarefas_cache:
                self.listar_tarefas()
            lista = self.tarefas_cache
            tipo = "GERAIS"
        
        self.logger.info(f"Buscando '{nome}' em {tipo} ({len(lista)} tarefas)")
        
        nome_lower = nome.lower()
        
        # Busca exata
        for tarefa in lista:
            if tarefa.nome.lower() == nome_lower:
                self.logger.info(f"[OK] Match exato: {tarefa.nome} - {tarefa.quantidade_pendente}")
                return tarefa
        
        # Busca parcial
        for tarefa in lista:
            if nome_lower in tarefa.nome.lower():
                self.logger.info(f"[OK] Match parcial: {tarefa.nome} - {tarefa.quantidade_pendente}")
                return tarefa
        
        self.logger.warn(f"Tarefa '{nome}' nao encontrada em {tipo}")
        return None
    
    def listar_processos(
        self,
        nome_tarefa: str,
        page: int = 0,
        max_results: int = 100,
        apenas_favoritas: bool = False
    ) -> Tuple[List[ProcessoTarefa], int]:
        """Lista processos de uma tarefa com paginacao."""
        if not self.auth.ensure_logged_in():
            return [], 0
        
        nome_encoded = quote(nome_tarefa)
        
        payload = {
            "numeroProcesso": "",
            "classe": None,
            "tags": [],
            "page": page,
            "maxResults": max_results,
            "competencia": "",
        }
        
        try:
            endpoint = (
                f"{API_BASE}/painelUsuario/"
                f"recuperarProcessosTarefaPendenteComCriterios/"
                f"{nome_encoded}/{str(apenas_favoritas).lower()}"
            )
            
            resp = self.auth.session.post(
                endpoint,
                json=payload,
                timeout=self.auth.timeout,
                headers=self.auth._get_api_headers()
            )
            
            if resp.status_code == 200:
                data = resp.json()
                total = data.get("count", 0)
                processos = [ProcessoTarefa.from_dict(p) for p in data.get("entities", [])]
                return processos, total
                
        except Exception as e:
            self.logger.error(f"Erro ao listar processos: {e}")
        
        return [], 0
    
    def listar_todos_processos(
        self,
        nome_tarefa: str,
        apenas_favoritas: bool = False
    ) -> List[ProcessoTarefa]:
        """Lista TODOS os processos de uma tarefa (com paginacao automatica)."""
        todos = []
        page = 0
        
        while True:
            processos, total = self.listar_processos(
                nome_tarefa, page, 100, apenas_favoritas
            )
            
            if not processos:
                break
            
            todos.extend(processos)
            self.logger.info(f"Carregados {len(todos)}/{total} processos")
            
            if len(todos) >= total:
                break
            
            page += 1
            delay(0.5, 1.0)
        
        return todos
