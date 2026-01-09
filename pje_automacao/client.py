"""
PJE Automacao - Classe principal (Facade).
Integra todos os servicos em uma interface unificada.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from .config import DEFAULT_TIMEOUT
from .models import Tarefa, ProcessoTarefa
from .utils import Logger, delay, save_json, normalizar_nome_pasta
from .core import AuthService
from .services import ProfileService, TaskService, DownloadService


class PJEAutomacao:
    """
    Classe principal de automacao do PJE.
    
    Exemplo de uso:
        pje = PJEAutomacao(download_dir="./downloads")
        pje.login()
        pje.selecionar_perfil("V DOS FEITOS...")
        
        tarefas = pje.listar_tarefas()
        relatorio = pje.processar_tarefa("Minutar sentenca")
        
        pje.close()
    """
    
    def __init__(
        self,
        download_dir: str = "./downloads",
        log_dir: str = "./.logs",
        session_dir: str = "./.session",
        timeout: int = DEFAULT_TIMEOUT,
        debug: bool = True
    ):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = Logger(debug)
        
        # Servicos
        self.auth = AuthService(session_dir, timeout, debug)
        self.profile = ProfileService(self.auth, debug)
        self.task = TaskService(self.auth, debug)
        self.download = DownloadService(self.auth, debug)
        
        self.logger.info("PJE Automacao inicializada")
        self.logger.info(f"Downloads: {self.download_dir}")
    
    # === Autenticacao ===
    
    def login(self, username: str = None, password: str = None, force: bool = False) -> bool:
        """Realiza login no sistema."""
        return self.auth.login(username, password, force)
    
    def limpar_sessao(self):
        """Limpa sessao salva."""
        self.auth.limpar_sessao()
    
    # === Perfil ===
    
    def listar_perfis(self) -> list:
        """Lista perfis disponiveis."""
        return self.profile.listar()
    
    def selecionar_perfil(self, nome: str) -> bool:
        """Seleciona perfil por nome."""
        sucesso = self.profile.selecionar_por_nome(nome)
        if sucesso:
            # Limpa cache de tarefas ao mudar perfil
            self.task.limpar_cache()
        return sucesso
    
    # === Tarefas ===
    
    def listar_tarefas(self) -> List[Tarefa]:
        """Lista tarefas com processos pendentes."""
        return self.task.listar_tarefas()
    
    def listar_tarefas_favoritas(self) -> List[Tarefa]:
        """Lista tarefas favoritas com processos."""
        return self.task.listar_favoritas()
    
    def buscar_tarefa(self, nome: str, favoritas: bool = False) -> Optional[Tarefa]:
        """Busca tarefa por nome."""
        return self.task.buscar_por_nome(nome, favoritas)
    
    def listar_processos(self, tarefa: str, favoritas: bool = False) -> List[ProcessoTarefa]:
        """Lista processos de uma tarefa."""
        return self.task.listar_todos_processos(tarefa, favoritas)
    
    # === Download ===
    
    def processar_tarefa(
        self,
        nome_tarefa: str,
        nome_perfil: str = None,
        tipo_documento: str = "Selecione",
        limite: int = None,
        aguardar: bool = True,
        tempo_espera: int = 300,
        usar_favoritas: bool = False
    ) -> Dict[str, Any]:
        """
        Processa downloads de todos os processos de uma tarefa.
        
        Args:
            nome_tarefa: Nome da tarefa
            nome_perfil: Perfil a selecionar (opcional)
            tipo_documento: Filtro de tipo de documento
            limite: Limite de processos (None = todos)
            aguardar: Se True, aguarda downloads ficarem prontos
            tempo_espera: Tempo maximo de espera (segundos)
            usar_favoritas: Se True, busca em favoritas
        
        Returns:
            Relatorio do processamento
        """
        self.download.limpar()
        
        # Diretorio da tarefa
        nome_pasta = normalizar_nome_pasta(nome_tarefa)
        diretorio = self.download_dir / nome_pasta
        diretorio.mkdir(parents=True, exist_ok=True)
        
        relatorio = {
            "tarefa": nome_tarefa,
            "perfil": nome_perfil,
            "diretorio": str(diretorio),
            "data_inicio": datetime.now().isoformat(),
            "processos_encontrados": 0,
            "solicitacoes_sucesso": 0,
            "solicitacoes_falha": 0,
            "downloads_diretos": 0,
            "downloads_concluidos": 0,
            "arquivos": [],
            "falhas": [],
        }
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"PROCESSANDO: {nome_tarefa}")
        self.logger.info(f"{'='*60}")
        
        # Selecionar perfil
        if nome_perfil:
            if not self.selecionar_perfil(nome_perfil):
                relatorio["erro"] = "Falha ao selecionar perfil"
                return relatorio
            delay()
        
        # Buscar tarefa
        tarefa = self.buscar_tarefa(nome_tarefa, usar_favoritas)
        if not tarefa:
            relatorio["erro"] = "Tarefa nao encontrada"
            return relatorio
        
        self.logger.info(f"Tarefa: {tarefa.nome} ({tarefa.quantidade_pendente} processos)")
        
        # Listar processos
        processos = self.listar_processos(tarefa.nome, usar_favoritas)
        relatorio["processos_encontrados"] = len(processos)
        
        if not processos:
            self.logger.info("Nenhum processo encontrado")
            return relatorio
        
        if limite:
            processos = processos[:limite]
            self.logger.info(f"Limitado a {limite} processos")
        
        # Processar cada processo
        processos_para_area = []
        
        for i, proc in enumerate(processos, 1):
            self.logger.info(f"\n[{i}/{len(processos)}] {proc.numero_processo}")
            
            sucesso, detalhes = self.download.solicitar_download(
                proc.id_processo,
                proc.numero_processo,
                tipo_documento,
                diretorio
            )
            
            if sucesso:
                relatorio["solicitacoes_sucesso"] += 1
                
                if detalhes.get("tipo_download") == "direto" and detalhes.get("arquivo"):
                    relatorio["downloads_diretos"] += 1
                    relatorio["arquivos"].append(detalhes["arquivo"])
                else:
                    processos_para_area.append(proc.numero_processo)
            else:
                relatorio["solicitacoes_falha"] += 1
                relatorio["falhas"].append(proc.numero_processo)
            
            delay(2, 4)
        
        # Aguardar downloads da area
        if aguardar and processos_para_area:
            self.logger.info(f"\nAguardando {len(processos_para_area)} downloads...")
            
            downloads = self.download.aguardar_downloads(processos_para_area, tempo_espera)
            
            self.logger.info(f"\nBaixando arquivos...")
            
            for download in downloads:
                delay()
                arquivo = self.download.baixar_arquivo(download, diretorio)
                if arquivo:
                    relatorio["arquivos"].append(str(arquivo))
        
        relatorio["downloads_concluidos"] = len(relatorio["arquivos"])
        relatorio["data_fim"] = datetime.now().isoformat()
        
        # Salvar relatorio
        nome_relatorio = f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_json(relatorio, diretorio / nome_relatorio)
        
        # Resumo
        self.logger.info(f"\n{'='*60}")
        self.logger.info("RESUMO")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Processos: {relatorio['processos_encontrados']}")
        self.logger.info(f"Sucesso: {relatorio['solicitacoes_sucesso']}")
        self.logger.info(f"Falhas: {relatorio['solicitacoes_falha']}")
        self.logger.info(f"Downloads diretos: {relatorio['downloads_diretos']}")
        self.logger.info(f"Total baixados: {relatorio['downloads_concluidos']}")
        
        return relatorio
    
    def close(self):
        """Fecha conexoes."""
        self.auth.session.close()
        self.logger.info("Sessao encerrada")
