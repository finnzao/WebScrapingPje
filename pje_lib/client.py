"""
Cliente principal do PJE - Interface unificada.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from .config import DEFAULT_TIMEOUT, DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX
from .core import SessionManager, PJEHttpClient
from .services import AuthService, TaskService, TagService, DownloadService
from .models import (
    Usuario, Perfil, Tarefa, ProcessoTarefa, 
    Etiqueta, Processo, DownloadDisponivel
)
from .utils import delay, normalizar_nome_pasta, save_json, timestamp_str, get_logger


class PJEClient:
    """
    Cliente principal para automação do PJE.
    
    Uso:
        from pje_lib import PJEClient
        
        pje = PJEClient()
        pje.login()
        pje.select_profile("Assessoria")
        
        # Processar por tarefa
        pje.processar_tarefa("Minutar sentença")
        
        # Processar por etiqueta
        pje.processar_etiqueta("Felipe")
    """
    
    def __init__(
        self,
        download_dir: str = "./downloads",
        log_dir: str = "./.logs",
        session_dir: str = "./.session",
        timeout: int = DEFAULT_TIMEOUT,
        debug: bool = True
    ):
        self.timeout = timeout
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = get_logger("pje", self.log_dir, debug)
        
        # Componentes
        self._http = PJEHttpClient(timeout)
        self._session = SessionManager(session_dir)
        
        # Serviços
        self._auth = AuthService(self._http, self._session)
        self._tasks = TaskService(self._http)
        self._tags = TagService(self._http)
        self._downloads = DownloadService(self._http, self.download_dir)
        
        self.logger.info(f"PJEClient inicializado. Downloads: {self.download_dir}")
    
    # ==================== PROPRIEDADES ====================
    
    @property
    def usuario(self) -> Optional[Usuario]:
        return self._auth.usuario
    
    @property
    def perfis(self) -> List[Perfil]:
        return self._auth.perfis_disponiveis
    
    @property
    def tarefas(self) -> List[Tarefa]:
        return self._tasks.tarefas_cache
    
    @property
    def tarefas_favoritas(self) -> List[Tarefa]:
        return self._tasks.tarefas_favoritas_cache
    
    # ==================== AUTENTICAÇÃO ====================
    
    def login(self, username: str = None, password: str = None, force: bool = False) -> bool:
        return self._auth.login(username, password, force)
    
    def limpar_sessao(self):
        self._auth.limpar_sessao()
    
    def ensure_logged_in(self) -> bool:
        return self._auth.ensure_logged_in()
    
    # ==================== PERFIL ====================
    
    def listar_perfis(self) -> List[Perfil]:
        return self._auth.listar_perfis()
    
    def select_profile(self, nome: str) -> bool:
        result = self._auth.select_profile(nome)
        if result:
            self._tasks.limpar_cache()
        return result
    
    # ==================== TAREFAS ====================
    
    def listar_tarefas(self, force: bool = False) -> List[Tarefa]:
        if not self.ensure_logged_in():
            return []
        return self._tasks.listar_tarefas(force)
    
    def listar_tarefas_favoritas(self, force: bool = False) -> List[Tarefa]:
        if not self.ensure_logged_in():
            return []
        return self._tasks.listar_tarefas_favoritas(force)
    
    def buscar_tarefa(self, nome: str, favoritas: bool = False) -> Optional[Tarefa]:
        return self._tasks.buscar_tarefa_por_nome(nome, favoritas)
    
    def listar_processos_tarefa(self, nome: str, favoritas: bool = False) -> List[ProcessoTarefa]:
        if not self.ensure_logged_in():
            return []
        return self._tasks.listar_todos_processos_tarefa(nome, favoritas)
    
    # ==================== ETIQUETAS ====================
    
    def buscar_etiquetas(self, busca: str = "") -> List[Etiqueta]:
        if not self.ensure_logged_in():
            return []
        return self._tags.buscar_etiquetas(busca)
    
    def buscar_etiqueta(self, nome: str) -> Optional[Etiqueta]:
        if not self.ensure_logged_in():
            return None
        return self._tags.buscar_etiqueta_por_nome(nome)
    
    def listar_processos_etiqueta(self, id_etiqueta: int, limit: int = 100) -> List[Processo]:
        if not self.ensure_logged_in():
            return []
        return self._tags.listar_processos_etiqueta(id_etiqueta, limit)
    
    # ==================== DOWNLOAD ====================
    
    def solicitar_download(self, id_processo: int, numero_processo: str, 
                          tipo: str = "Selecione", diretorio: Path = None) -> bool:
        sucesso, _ = self._downloads.solicitar_download(
            id_processo, numero_processo, tipo, diretorio_download=diretorio
        )
        return sucesso
    
    def listar_downloads(self) -> List[DownloadDisponivel]:
        return self._downloads.listar_downloads_disponiveis()
    
    def baixar_arquivo(self, download: DownloadDisponivel, diretorio: Path = None) -> Optional[Path]:
        return self._downloads.baixar_arquivo(download, diretorio)
    
    # ==================== FLUXOS COMPLETOS ====================
    
    def processar_tarefa(
        self,
        nome_tarefa: str,
        perfil: str = None,
        tipo_documento: str = "Selecione",
        limite: int = None,
        aguardar_download: bool = True,
        tempo_espera: int = 300,
        usar_favoritas: bool = False
    ) -> Dict[str, Any]:
        """Processa todos os processos de uma tarefa."""
        
        self._downloads.limpar_diagnosticos()
        
        nome_pasta = normalizar_nome_pasta(nome_tarefa)
        diretorio = self.download_dir / nome_pasta
        diretorio.mkdir(parents=True, exist_ok=True)
        
        relatorio = {
            "tarefa": nome_tarefa, "perfil": perfil, "diretorio": str(diretorio),
            "data_inicio": datetime.now().isoformat(),
            "processos": 0, "sucesso": 0, "falha": 0, "arquivos": [], "erros": []
        }
        
        self.logger.section(f"PROCESSANDO TAREFA: {nome_tarefa}")
        
        if perfil and not self.select_profile(perfil):
            relatorio["erros"].append("Falha ao selecionar perfil")
            return relatorio
        
        tarefa = self.buscar_tarefa(nome_tarefa, usar_favoritas)
        if not tarefa:
            relatorio["erros"].append("Tarefa não encontrada")
            return relatorio
        
        processos = self.listar_processos_tarefa(tarefa.nome, usar_favoritas)
        if limite:
            processos = processos[:limite]
        relatorio["processos"] = len(processos)
        
        processos_solicitados = []
        
        for i, proc in enumerate(processos, 1):
            self.logger.info(f"[{i}/{len(processos)}] {proc.numero_processo}")
            
            sucesso, detalhes = self._downloads.solicitar_download(
                proc.id_processo, proc.numero_processo, tipo_documento,
                diretorio_download=diretorio
            )
            
            if sucesso:
                relatorio["sucesso"] += 1
                if detalhes.get("arquivo_baixado"):
                    relatorio["arquivos"].append(detalhes["arquivo_baixado"])
                else:
                    processos_solicitados.append(proc.numero_processo)
            else:
                relatorio["falha"] += 1
            
            delay(2, 4)
        
        if aguardar_download and processos_solicitados:
            downloads = self._downloads.aguardar_downloads(processos_solicitados, tempo_espera)
            for dl in downloads:
                delay()
                arquivo = self._downloads.baixar_arquivo(dl, diretorio)
                if arquivo:
                    relatorio["arquivos"].append(str(arquivo))
        
        relatorio["data_fim"] = datetime.now().isoformat()
        save_json(relatorio, diretorio / f"relatorio_{timestamp_str()}.json")
        
        self.logger.section("RESUMO")
        self.logger.info(f"Processos: {relatorio['processos']}")
        self.logger.info(f"Sucesso: {relatorio['sucesso']}")
        self.logger.info(f"Arquivos: {len(relatorio['arquivos'])}")
        
        return relatorio
    
    def processar_etiqueta(
        self,
        nome_etiqueta: str,
        perfil: str = None,
        tipo_documento: str = "Selecione",
        limite: int = None,
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Dict[str, Any]:
        """Processa todos os processos de uma etiqueta."""
        
        self._downloads.limpar_diagnosticos()
        
        nome_pasta = normalizar_nome_pasta(nome_etiqueta)
        diretorio = self.download_dir / nome_pasta
        diretorio.mkdir(parents=True, exist_ok=True)
        
        relatorio = {
            "etiqueta": nome_etiqueta, "perfil": perfil, "diretorio": str(diretorio),
            "data_inicio": datetime.now().isoformat(),
            "processos": 0, "sucesso": 0, "falha": 0, "arquivos": [], "erros": []
        }
        
        self.logger.section(f"PROCESSANDO ETIQUETA: {nome_etiqueta}")
        
        if perfil and not self.select_profile(perfil):
            relatorio["erros"].append("Falha ao selecionar perfil")
            return relatorio
        
        etiqueta = self.buscar_etiqueta(nome_etiqueta)
        if not etiqueta:
            relatorio["erros"].append("Etiqueta não encontrada")
            return relatorio
        
        processos = self.listar_processos_etiqueta(etiqueta.id)
        if limite:
            processos = processos[:limite]
        relatorio["processos"] = len(processos)
        
        processos_solicitados = []
        
        for i, proc in enumerate(processos, 1):
            self.logger.info(f"[{i}/{len(processos)}] {proc.numero_processo}")
            
            sucesso, detalhes = self._downloads.solicitar_download(
                proc.id_processo, proc.numero_processo, tipo_documento,
                diretorio_download=diretorio
            )
            
            if sucesso:
                relatorio["sucesso"] += 1
                if detalhes.get("arquivo_baixado"):
                    relatorio["arquivos"].append(detalhes["arquivo_baixado"])
                else:
                    processos_solicitados.append(proc.numero_processo)
            else:
                relatorio["falha"] += 1
            
            delay(2, 4)
        
        if aguardar_download and processos_solicitados:
            downloads = self._downloads.aguardar_downloads(processos_solicitados, tempo_espera)
            for dl in downloads:
                delay()
                arquivo = self._downloads.baixar_arquivo(dl, diretorio)
                if arquivo:
                    relatorio["arquivos"].append(str(arquivo))
        
        relatorio["data_fim"] = datetime.now().isoformat()
        save_json(relatorio, diretorio / f"relatorio_{timestamp_str()}.json")
        
        self.logger.section("RESUMO")
        self.logger.info(f"Processos: {relatorio['processos']}")
        self.logger.info(f"Sucesso: {relatorio['sucesso']}")
        self.logger.info(f"Arquivos: {len(relatorio['arquivos'])}")
        
        return relatorio
    
    def close(self):
        self._http.close()
        self.logger.info("Conexão encerrada")
