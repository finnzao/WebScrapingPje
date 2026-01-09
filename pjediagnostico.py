#!/usr/bin/env python3
"""
PJE Automação - Script Unificado com Diagnósticos
==================================================

Este script combina:
1. Sistema de autenticação robusto (sessão persistente)
2. Download de processos com diagnósticos detalhados
3. Identificação precisa de falhas

PROBLEMA IDENTIFICADO NO SCRIPT ORIGINAL:
- Usava navbar:j_id267 mas o botão correto é navbar:j_id280
- Faltavam campos do formulário (campos vazios com valor 'on')
- Não verificava corretamente a resposta da solicitação

CORREÇÕES IMPLEMENTADAS:
- ID do botão corrigido para j_id280
- Formulário completo com todos os campos
- Verificação robusta da resposta
- Diagnósticos detalhados para identificar falhas
"""

import os
import re
import json
import time
import random
import pickle
import requests
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import urlparse, quote, unquote
from typing import Optional, Dict, List, Any, Literal, Set, Tuple
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# CONFIGURAÇÕES E CONSTANTES
# ============================================================

BASE_URL = "https://pje.tjba.jus.br"
SSO_URL = "https://sso.cloud.pje.jus.br"
API_BASE = f"{BASE_URL}/pje/seam/resource/rest/pje-legacy"

# Tipos de documento disponíveis
TIPO_DOCUMENTO_VALUES: Dict[str, str] = {
    "Selecione": "0",
    "Peticao Inicial": "12",
    "Peticao": "36",
    "Documento de Identificacao": "52",
    "Documento de Comprovacao": "53",
    "Certidao": "57",
    "Decisao": "64",
    "Procuracao": "161",
    "Despacho": "63",
    "Sentenca": "62",
    "Acordao": "74",
    "Outros documentos": "93",
}


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class Usuario:
    id_usuario: int
    nome: str
    login: str
    id_orgao_julgador: int
    id_papel: int
    id_localizacao_fisica: int
    id_usuario_localizacao: int = 0
    
    @classmethod
    def from_dict(cls, data: dict) -> "Usuario":
        return cls(
            id_usuario=data.get("idUsuario", 0),
            nome=data.get("nomeUsuario", ""),
            login=data.get("login", ""),
            id_orgao_julgador=data.get("idOrgaoJulgador", 0),
            id_papel=data.get("idPapel", 0),
            id_localizacao_fisica=data.get("idLocalizacaoFisica", 0),
            id_usuario_localizacao=data.get("idUsuarioLocalizacaoMagistradoServidor", 0)
        )


@dataclass
class Tarefa:
    id: int
    nome: str
    quantidade_pendente: int = 0
    favorita: bool = False
    
    @classmethod
    def from_dict(cls, data: dict, favorita: bool = False) -> "Tarefa":
        return cls(
            id=data.get("id", 0),
            nome=data.get("nome", ""),
            quantidade_pendente=data.get("quantidadePendente", 0),
            favorita=favorita
        )


@dataclass
class ProcessoTarefa:
    id_processo: int
    numero_processo: str
    id_task_instance: int
    polo_ativo: str = ""
    polo_passivo: str = ""
    classe_judicial: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProcessoTarefa":
        return cls(
            id_processo=data.get("idProcesso", 0),
            numero_processo=data.get("numeroProcesso", ""),
            id_task_instance=data.get("idTaskInstance", 0),
            polo_ativo=data.get("poloAtivo", ""),
            polo_passivo=data.get("poloPassivo", ""),
            classe_judicial=data.get("classeJudicial", "")
        )


@dataclass
class DownloadDisponivel:
    id_usuario: int
    nome_arquivo: str
    hash_download: str
    data_expiracao: int
    situacao: str
    sistema_origem: str
    itens: List[Dict] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict) -> "DownloadDisponivel":
        return cls(
            id_usuario=data.get("idUsuario", 0),
            nome_arquivo=data.get("nomeArquivo", ""),
            hash_download=data.get("hashDownload", ""),
            data_expiracao=data.get("dataExpiracao", 0),
            situacao=data.get("situacaoDownload", ""),
            sistema_origem=data.get("sistemaOrigem", ""),
            itens=data.get("itens", [])
        )
    
    def get_numeros_processos(self) -> List[str]:
        return list(set([item.get("numeroProcesso", "") for item in self.itens if item.get("numeroProcesso")]))
    
    def contem_processo(self, numero_processo: str) -> bool:
        return numero_processo in self.get_numeros_processos()


@dataclass
class Perfil:
    index: int
    nome: str
    orgao: str = ""
    cargo: str = ""
    
    @property
    def nome_completo(self) -> str:
        partes = [self.nome]
        if self.orgao:
            partes.append(self.orgao)
        if self.cargo:
            partes.append(self.cargo)
        return " / ".join(partes)


@dataclass
class DiagnosticoDownload:
    """Armazena informações de diagnóstico sobre tentativa de download."""
    numero_processo: str
    id_processo: int
    timestamp: float
    etapa: str  # 'chave_acesso', 'abrir_processo', 'extrair_viewstate', 'solicitar', 'aguardar', 'baixar'
    sucesso: bool
    mensagem: str
    detalhes: Dict = field(default_factory=dict)


# ============================================================
# GERENCIADOR DE SESSÃO
# ============================================================

class SessionManager:
    """Gerencia persistência de sessão (cookies)."""
    
    def __init__(self, session_dir: str = ".session"):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.cookies_file = self.session_dir / "cookies.pkl"
        self.session_info_file = self.session_dir / "session_info.json"
    
    def save_session(self, session: requests.Session) -> bool:
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
        except Exception as e:
            print(f"[ERRO] Falha ao salvar sessão: {e}")
            return False
    
    def load_session(self, session: requests.Session) -> bool:
        if not self.cookies_file.exists():
            return False
        
        try:
            with open(self.cookies_file, 'rb') as f:
                cookies = pickle.load(f)
            session.cookies.update(cookies)
            return True
        except Exception as e:
            print(f"[ERRO] Falha ao carregar sessão: {e}")
            return False
    
    def is_session_valid(self, max_age_hours: int = 8) -> bool:
        if not self.session_info_file.exists():
            return False
        
        try:
            with open(self.session_info_file, 'r', encoding='utf-8') as f:
                info = json.load(f)
            
            saved_timestamp = info.get("timestamp", 0)
            age_hours = (time.time() - saved_timestamp) / 3600
            
            return age_hours < max_age_hours
        except:
            return False
    
    def clear_session(self):
        if self.cookies_file.exists():
            self.cookies_file.unlink()
        if self.session_info_file.exists():
            self.session_info_file.unlink()


# ============================================================
# CLASSE PRINCIPAL
# ============================================================

class PJEAutomacaoUnificada:
    """
    Automação do sistema PJE via API REST.
    Versão unificada com diagnósticos detalhados.
    """
    
    def __init__(
        self,
        download_dir: str = None,
        log_dir: str = ".logs",
        session_dir: str = ".session",
        timeout: int = 30,
        delay_min: float = 1.0,
        delay_max: float = 3.0,
        debug: bool = True
    ):
        self.timeout = timeout
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.debug = debug
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            self.download_dir = Path.home() / "Downloads" / "pje_downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_manager = SessionManager(session_dir)
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
        })
        
        self.usuario: Optional[Usuario] = None
        self.perfis_disponiveis: List[Perfil] = []
        self.tarefas_cache: List[Tarefa] = []
        self.tarefas_favoritas_cache: List[Tarefa] = []
        
        # Diagnósticos
        self.diagnosticos: List[DiagnosticoDownload] = []
        self.downloads_solicitados: Set[str] = set()
        
        self._log(f"PJE Automação Unificada inicializada")
        self._log(f"Downloads: {self.download_dir}")
    
    # ==================== UTILITÁRIOS ====================
    
    def _delay(self, min_sec: float = None, max_sec: float = None):
        min_sec = min_sec or self.delay_min
        max_sec = max_sec or self.delay_max
        time.sleep(random.uniform(min_sec, max_sec))
    
    def _log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def _log_debug(self, message: str):
        if self.debug:
            self._log(message, "DEBUG")
    
    def _save_json(self, data: Any, filename: str):
        filepath = self.log_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._log_debug(f"JSON salvo: {filepath}")
    
    def _adicionar_diagnostico(
        self,
        numero_processo: str,
        id_processo: int,
        etapa: str,
        sucesso: bool,
        mensagem: str,
        detalhes: Dict = None
    ):
        """Adiciona um registro de diagnóstico."""
        diag = DiagnosticoDownload(
            numero_processo=numero_processo,
            id_processo=id_processo,
            timestamp=time.time(),
            etapa=etapa,
            sucesso=sucesso,
            mensagem=mensagem,
            detalhes=detalhes or {}
        )
        self.diagnosticos.append(diag)
        
        status = "✓" if sucesso else "✗"
        self._log(f"  [{status}] {etapa}: {mensagem}")
    
    # ==================== SESSÃO E AUTENTICAÇÃO ====================
    
    def limpar_sessao(self):
        """Limpa a sessão salva."""
        self._log("Limpando sessão salva...")
        self.session_manager.clear_session()
        self.session.cookies.clear()
    
    def _verificar_sessao_ativa(self) -> bool:
        """Verifica se há uma sessão ativa no servidor."""
        try:
            self._log_debug("Verificando sessão ativa no servidor...")
            resp = self.session.get(
                f"{API_BASE}/usuario/currentUser",
                timeout=self.timeout
            )
            self._log_debug(f"Resposta currentUser: status={resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                self._log_debug(f"Dados do usuario: {json.dumps(data, ensure_ascii=False)}")
                self.usuario = Usuario.from_dict(data)
                return True
        except Exception as e:
            self._log_debug(f"Erro ao verificar sessão: {e}")
        return False
    
    def _restaurar_sessao(self) -> bool:
        """Tenta restaurar sessão salva anteriormente."""
        if not self.session_manager.is_session_valid(8):
            self._log("Sessão salva expirada ou inexistente")
            return False
        
        if not self.session_manager.load_session(self.session):
            return False
        
        if self._verificar_sessao_ativa():
            self._log(f"Sessão restaurada. Usuario: {self.usuario.nome}")
            return True
        
        return False
    
    def login(self, username: str = None, password: str = None, force: bool = False) -> bool:
        """Realiza login no PJE."""
        username = username or os.getenv("USER")
        password = password or os.getenv("PASSWORD")
        
        if not username or not password:
            self._log("Credenciais não fornecidas", "ERROR")
            return False
        
        if not force:
            if self._verificar_sessao_ativa():
                self._log(f"Já está logado. Usuario: {self.usuario.nome}")
                return True
            
            if self._restaurar_sessao():
                return True
        else:
            self.session_manager.clear_session()
        
        self._log(f"Iniciando login para {username}...")
        
        try:
            login_url = f"{BASE_URL}/pje/login.seam"
            resp = self.session.get(login_url, allow_redirects=True, timeout=self.timeout)
            
            current_url = resp.url
            
            if "sso.cloud.pje.jus.br" not in current_url:
                self._log("Não redirecionou para SSO", "ERROR")
                return False
            
            action_match = re.search(r'action="([^"]*authenticate[^"]*)"', resp.text)
            if not action_match:
                self._log("Não encontrou URL de autenticação", "ERROR")
                return False
            
            auth_url = action_match.group(1).replace("&amp;", "&")
            if not auth_url.startswith("http"):
                auth_url = f"{SSO_URL}{auth_url}"
            
            self._delay()
            
            login_data = {
                "username": username,
                "password": password,
                "pjeoffice-code": "",
                "phrase": ""
            }
            
            resp = self.session.post(
                auth_url,
                data=login_data,
                allow_redirects=True,
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": SSO_URL,
                }
            )
            
            self._delay()
            
            if self._verificar_sessao_ativa():
                self._log(f"Login bem-sucedido! Usuario: {self.usuario.nome}")
                self.session_manager.save_session(self.session)
                return True
            else:
                self._log("Falha ao verificar usuario após login", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Erro durante login: {e}", "ERROR")
            return False
    
    def ensure_logged_in(self) -> bool:
        """Verifica se está logado, faz login se necessário."""
        if self._verificar_sessao_ativa():
            return True
        return self.login()
    
    # ==================== PERFIL ====================
    
    def _extrair_perfis_da_pagina(self, html: str) -> List[Perfil]:
        """Extrai lista de perfis disponíveis do HTML."""
        perfis = []
        
        pattern = r'dtPerfil:(\d+):j_id70[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.IGNORECASE)
        
        if not matches:
            pattern = r'<a[^>]*onclick="[^"]*dtPerfil:(\d+)[^"]*"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html, re.IGNORECASE)
        
        for index_str, nome in matches:
            partes = nome.strip().split(" / ")
            perfil = Perfil(
                index=int(index_str),
                nome=partes[0] if partes else nome.strip(),
                orgao=partes[1] if len(partes) > 1 else "",
                cargo=partes[2] if len(partes) > 2 else ""
            )
            perfis.append(perfil)
        
        return perfis
    
    def listar_perfis(self) -> List[Perfil]:
        """Lista perfis disponíveis."""
        if not self.ensure_logged_in():
            return []
        
        try:
            resp = self.session.get(f"{BASE_URL}/pje/ng2/dev.seam", timeout=self.timeout)
            
            if resp.status_code == 200:
                self.perfis_disponiveis = self._extrair_perfis_da_pagina(resp.text)
                self._log(f"Encontrados {len(self.perfis_disponiveis)} perfis")
                return self.perfis_disponiveis
                
        except Exception as e:
            self._log(f"Erro ao listar perfis: {e}", "ERROR")
        
        return []
    
    def select_profile_by_index(self, profile_index: int) -> bool:
        """Seleciona um perfil pelo índice."""
        if not self.ensure_logged_in():
            return False
        
        try:
            resp = self.session.get(f"{BASE_URL}/pje/ng2/dev.seam", timeout=self.timeout)
            
            viewstate_match = re.search(
                r'name="javax\.faces\.ViewState"[^>]*value="([^"]*)"',
                resp.text
            )
            viewstate = viewstate_match.group(1) if viewstate_match else "j_id1"
            
            self._delay()
            
            form_data = {
                "papeisUsuarioForm": "papeisUsuarioForm",
                "papeisUsuarioForm:j_id60": "",
                "papeisUsuarioForm:j_id72": "papeisUsuarioForm:j_id72",
                "javax.faces.ViewState": viewstate,
                f"papeisUsuarioForm:dtPerfil:{profile_index}:j_id70": f"papeisUsuarioForm:dtPerfil:{profile_index}:j_id70"
            }
            
            resp = self.session.post(
                f"{BASE_URL}/pje/ng2/dev.seam",
                data=form_data,
                allow_redirects=True,
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": BASE_URL,
                }
            )
            
            self._delay()
            
            if self._verificar_sessao_ativa():
                self._log(f"Perfil selecionado: {self.usuario.nome}")
                self.session_manager.save_session(self.session)
                return True
            
            return False
            
        except Exception as e:
            self._log(f"Erro ao selecionar perfil: {e}", "ERROR")
            return False
    
    def select_profile(self, nome_perfil: str) -> bool:
        """Seleciona um perfil pelo nome."""
        if not self.perfis_disponiveis:
            self.listar_perfis()
        
        for perfil in self.perfis_disponiveis:
            if nome_perfil.lower() in perfil.nome_completo.lower():
                self._log(f"Perfil encontrado: {perfil.nome_completo}")
                return self.select_profile_by_index(perfil.index)
        
        self._log(f"Perfil '{nome_perfil}' não encontrado", "ERROR")
        return False
    
    # ==================== TAREFAS ====================
    
    def listar_tarefas(self) -> List[Tarefa]:
        """Lista todas as tarefas disponíveis."""
        if not self.ensure_logged_in():
            return []
        
        try:
            resp = self.session.post(
                f"{API_BASE}/painelUsuario/tarefas",
                json={"numeroProcesso": "", "competencia": "", "etiquetas": []},
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code == 200:
                self.tarefas_cache = [Tarefa.from_dict(t) for t in resp.json()]
                self._log(f"Encontradas {len(self.tarefas_cache)} tarefas")
                return self.tarefas_cache
                
        except Exception as e:
            self._log(f"Erro ao listar tarefas: {e}", "ERROR")
        
        return []
    
    def listar_tarefas_favoritas(self) -> List[Tarefa]:
        """Lista as tarefas favoritas."""
        if not self.ensure_logged_in():
            return []
        
        try:
            resp = self.session.post(
                f"{API_BASE}/painelUsuario/tarefasFavoritas",
                json={"numeroProcesso": "", "competencia": "", "etiquetas": []},
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code == 200:
                self.tarefas_favoritas_cache = [Tarefa.from_dict(t, favorita=True) for t in resp.json()]
                self._log(f"Encontradas {len(self.tarefas_favoritas_cache)} tarefas favoritas")
                return self.tarefas_favoritas_cache
                
        except Exception as e:
            self._log(f"Erro ao listar tarefas favoritas: {e}", "ERROR")
        
        return []
    
    def buscar_tarefa_por_nome(self, nome: str) -> Optional[Tarefa]:
        """Busca uma tarefa pelo nome."""
        if not self.tarefas_favoritas_cache:
            self.listar_tarefas_favoritas()
        if not self.tarefas_cache:
            self.listar_tarefas()
        
        nome_lower = nome.lower()
        
        # Busca exata primeiro
        for tarefa in self.tarefas_favoritas_cache + self.tarefas_cache:
            if tarefa.nome.lower() == nome_lower:
                return tarefa
        
        # Busca parcial
        for tarefa in self.tarefas_favoritas_cache + self.tarefas_cache:
            if nome_lower in tarefa.nome.lower():
                return tarefa
        
        return None
    
    def listar_processos_tarefa(
        self,
        nome_tarefa: str,
        page: int = 0,
        max_results: int = 100,
        apenas_favoritas: bool = False
    ) -> Tuple[List[ProcessoTarefa], int]:
        """Lista processos de uma tarefa."""
        if not self.ensure_logged_in():
            return [], 0
        
        nome_tarefa_encoded = quote(nome_tarefa)
        
        payload = {
            "numeroProcesso": "",
            "classe": None,
            "tags": [],
            "page": page,
            "maxResults": max_results,
            "competencia": "",
        }
        
        try:
            endpoint = f"{API_BASE}/painelUsuario/recuperarProcessosTarefaPendenteComCriterios/{nome_tarefa_encoded}/{str(apenas_favoritas).lower()}"
            
            resp = self.session.post(
                endpoint,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                total = data.get("count", 0)
                processos = [ProcessoTarefa.from_dict(p) for p in data.get("entities", [])]
                return processos, total
                
        except Exception as e:
            self._log(f"Erro ao listar processos: {e}", "ERROR")
        
        return [], 0
    
    def listar_todos_processos_tarefa(self, nome_tarefa: str, favorita: bool = False) -> List[ProcessoTarefa]:
        """Lista TODOS os processos de uma tarefa (com paginação)."""
        todos = []
        page = 0
        
        while True:
            processos, total = self.listar_processos_tarefa(nome_tarefa, page, 100, favorita)
            if not processos:
                break
            
            todos.extend(processos)
            self._log(f"Carregados {len(todos)}/{total} processos")
            
            if len(todos) >= total:
                break
            
            page += 1
            self._delay(0.5, 1.0)
        
        return todos
    
    # ==================== DOWNLOAD - NÚCLEO CORRIGIDO ====================
    
    def gerar_chave_acesso(self, id_processo: int) -> Optional[str]:
        """Gera chave de acesso para um processo."""
        try:
            resp = self.session.get(
                f"{API_BASE}/painelUsuario/gerarChaveAcessoProcesso/{id_processo}",
                timeout=self.timeout
            )
            
            if resp.status_code == 200:
                ca = resp.text.strip().strip('"')
                self._log_debug(f"Chave acesso: {ca[:30]}...")
                return ca
                
        except Exception as e:
            self._log(f"Erro ao gerar chave de acesso: {e}", "ERROR")
        
        return None
    
    def abrir_processo(self, id_processo: int, ca: str = None) -> Optional[str]:
        """Abre a página de autos digitais."""
        if not ca:
            ca = self.gerar_chave_acesso(id_processo)
            if not ca:
                return None
        
        try:
            resp = self.session.get(
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam",
                params={"idProcesso": id_processo, "ca": ca},
                timeout=self.timeout
            )
            
            if resp.status_code == 200:
                self._log_debug(f"Processo aberto, HTML: {len(resp.text)} bytes")
                return resp.text
                
        except Exception as e:
            self._log(f"Erro ao abrir processo: {e}", "ERROR")
        
        return None
    
    def _extrair_viewstate(self, html: str) -> Optional[str]:
        """Extrai o ViewState do HTML."""
        match = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]*)"', html)
        if match:
            return match.group(1)
        return None
    
    def _identificar_botao_download(self, html: str) -> Optional[str]:
        """
        Identifica o ID correto do botão de download DINAMICAMENTE.
        
        O ID do botão varia entre processos (j_id270, j_id271, j_id278, j_id280, etc.)
        A identificação é feita baseada nas características do botão:
        1. Tem onclick="iniciarTemporizadorDownload()"
        2. Tem value="Download"
        3. Está dentro de um input com class="btn btn-primary"
        """
        botoes_encontrados = []
        
        # Padrão 1: Busca por botão com value="Download" e onclick com iniciarTemporizadorDownload
        # Este é o padrão mais confiável
        pattern1 = re.compile(
            r'<input[^>]*'
            r'id="(navbar:j_id\d+)"[^>]*'
            r'onclick="iniciarTemporizadorDownload\(\)[^"]*"[^>]*'
            r'value="Download"[^>]*>',
            re.IGNORECASE | re.DOTALL
        )
        
        # Padrão 2: Ordem diferente dos atributos (value antes de onclick)
        pattern2 = re.compile(
            r'<input[^>]*'
            r'value="Download"[^>]*'
            r'id="(navbar:j_id\d+)"[^>]*'
            r'onclick="iniciarTemporizadorDownload\(\)[^"]*"[^>]*>',
            re.IGNORECASE | re.DOTALL
        )
        
        # Padrão 3: Mais genérico - qualquer input com iniciarTemporizadorDownload no onclick
        pattern3 = re.compile(
            r'<input[^>]*id="(navbar:j_id\d+)"[^>]*onclick="[^"]*iniciarTemporizadorDownload[^"]*"[^>]*>',
            re.IGNORECASE | re.DOTALL
        )
        
        # Padrão 4: Busca dentro do div botoesDownload
        pattern4 = re.compile(
            r'id="navbar:botoesDownload"[^>]*>.*?<input[^>]*id="(navbar:j_id\d+)"[^>]*value="Download"',
            re.IGNORECASE | re.DOTALL
        )
        
        # Tenta cada padrão em ordem de especificidade
        for pattern in [pattern1, pattern2, pattern4, pattern3]:
            matches = pattern.findall(html)
            if matches:
                for match in matches:
                    if match not in botoes_encontrados:
                        botoes_encontrados.append(match)
        
        if botoes_encontrados:
            # Log de diagnóstico
            self._log_debug(f"Botões de download encontrados: {botoes_encontrados}")
            
            # Retorna o primeiro botão encontrado (geralmente há apenas um)
            botao = botoes_encontrados[0]
            self._log_debug(f"Usando botão: {botao}")
            return botao
        
        # Fallback: tentar IDs comuns conhecidos
        ids_conhecidos = ['navbar:j_id280', 'navbar:j_id278', 'navbar:j_id271', 
                         'navbar:j_id270', 'navbar:j_id267']
        
        for id_botao in ids_conhecidos:
            if id_botao in html:
                self._log_debug(f"Usando ID conhecido como fallback: {id_botao}")
                return id_botao
        
        self._log("AVISO: Nenhum botão de download identificado!", "WARN")
        return None
    
    def solicitar_download_diagnostico(
        self,
        id_processo: int,
        numero_processo: str,
        tipo_documento: str = "Selecione",
        html_processo: str = None
    ) -> Tuple[bool, Dict]:
        """
        Solicita download com diagnósticos detalhados.
        
        Retorna: (sucesso, detalhes_diagnostico)
        """
        detalhes = {
            "id_processo": id_processo,
            "numero_processo": numero_processo,
            "etapas": []
        }
        
        self._log(f"\n{'='*60}")
        self._log(f"SOLICITANDO DOWNLOAD: {numero_processo} (ID: {id_processo})")
        self._log(f"{'='*60}")
        
        # Etapa 1: Obter chave de acesso
        ca = self.gerar_chave_acesso(id_processo)
        if not ca:
            self._adicionar_diagnostico(
                numero_processo, id_processo, "chave_acesso",
                False, "Falha ao gerar chave de acesso"
            )
            detalhes["etapas"].append({"etapa": "chave_acesso", "sucesso": False})
            return False, detalhes
        
        detalhes["chave_acesso"] = ca[:30] + "..."
        self._adicionar_diagnostico(
            numero_processo, id_processo, "chave_acesso",
            True, f"Chave obtida: {ca[:30]}..."
        )
        
        # Etapa 2: Abrir processo (se não fornecido)
        if not html_processo:
            self._delay()
            html_processo = self.abrir_processo(id_processo, ca)
            
            if not html_processo:
                self._adicionar_diagnostico(
                    numero_processo, id_processo, "abrir_processo",
                    False, "Falha ao abrir página de autos digitais"
                )
                detalhes["etapas"].append({"etapa": "abrir_processo", "sucesso": False})
                return False, detalhes
        
        detalhes["html_tamanho"] = len(html_processo)
        self._adicionar_diagnostico(
            numero_processo, id_processo, "abrir_processo",
            True, f"Página carregada ({len(html_processo)} bytes)"
        )
        
        # Etapa 3: Extrair ViewState
        viewstate = self._extrair_viewstate(html_processo)
        if not viewstate:
            self._adicionar_diagnostico(
                numero_processo, id_processo, "extrair_viewstate",
                False, "ViewState não encontrado no HTML"
            )
            detalhes["etapas"].append({"etapa": "extrair_viewstate", "sucesso": False})
            return False, detalhes
        
        detalhes["viewstate"] = viewstate[:30] + "..."
        self._adicionar_diagnostico(
            numero_processo, id_processo, "extrair_viewstate",
            True, f"ViewState: {viewstate}"
        )
        
        # Etapa 4: Identificar botão de download
        botao_id = self._identificar_botao_download(html_processo)
        if not botao_id:
            self._adicionar_diagnostico(
                numero_processo, id_processo, "identificar_botao",
                False, "Botão de download não encontrado no HTML"
            )
            detalhes["etapas"].append({"etapa": "identificar_botao", "sucesso": False})
            # Salvar HTML para análise
            self._save_json({"html": html_processo[:10000]}, f"debug_html_{numero_processo.replace('.', '_')}.json")
            return False, detalhes
        
        detalhes["botao_id"] = botao_id
        self._adicionar_diagnostico(
            numero_processo, id_processo, "identificar_botao",
            True, f"Botão identificado: {botao_id}"
        )
        
        # Validação extra: verificar se o botão existe no HTML
        if f'id="{botao_id}"' not in html_processo and f"id='{botao_id}'" not in html_processo:
            self._log(f"AVISO: Botão {botao_id} identificado mas não confirmado no HTML", "WARN")
        
        # Etapa 5: Montar e enviar formulário
        self._delay()
        
        tipo_value = TIPO_DOCUMENTO_VALUES.get(tipo_documento, "0")
        
        # Formulário COMPLETO baseado no HAR (inclui campos vazios importantes)
        form_data = {
            "AJAXREQUEST": "_viewRoot",
            "navbar:cbTipoDocumento": tipo_value,
            "navbar:idDe": "",
            "navbar:idAte": "",
            "navbar:dtInicioInputDate": "",
            "navbar:dtInicioInputCurrentDate": datetime.now().strftime("%m/%Y"),
            "navbar:dtFimInputDate": "",
            "navbar:dtFimInputCurrentDate": datetime.now().strftime("%m/%Y"),
            "navbar:cbCronologia": "DESC",
            # Campos com nome vazio (checkboxes)
            "": "on",
            "navbar": "navbar",
            "autoScroll": "",
            "javax.faces.ViewState": viewstate,
            botao_id: botao_id,  # Usa o botão identificado dinamicamente
            "AJAX:EVENTS_COUNT": "1",
        }
        
        detalhes["form_data"] = {k: v[:50] if isinstance(v, str) and len(v) > 50 else v for k, v in form_data.items()}
        
        try:
            resp = self.session.post(
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam",
                data=form_data,
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "*/*",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam?idProcesso={id_processo}&ca={ca}"
                }
            )
            
            detalhes["response_status"] = resp.status_code
            detalhes["response_tamanho"] = len(resp.text)
            
            # Verificar resposta
            if resp.status_code != 200:
                self._adicionar_diagnostico(
                    numero_processo, id_processo, "solicitar",
                    False, f"HTTP {resp.status_code}",
                    {"response": resp.text[:500]}
                )
                return False, detalhes
            
            # Verificar mensagem de sucesso
            resposta_texto = resp.text
            
            # Procurar mensagens na resposta
            mensagens = re.findall(r'rich-messages-label[^>]*>([^<]+)<', resposta_texto)
            detalhes["mensagens_resposta"] = mensagens
            
            # Verificar se a solicitação foi aceita
            sucesso_patterns = [
                "documento solicitado será gerado",
                "Área de download",
                "download",
                "será disponibilizado"
            ]
            
            solicitacao_aceita = any(p.lower() in resposta_texto.lower() for p in sucesso_patterns)
            
            if solicitacao_aceita:
                self._adicionar_diagnostico(
                    numero_processo, id_processo, "solicitar",
                    True, f"Solicitação aceita. Mensagens: {mensagens}",
                    {"mensagens": mensagens}
                )
                self.downloads_solicitados.add(numero_processo)
                return True, detalhes
            else:
                # Verificar se há erros
                erro_patterns = ["erro", "falha", "não foi possível", "error"]
                tem_erro = any(p.lower() in resposta_texto.lower() for p in erro_patterns)
                
                self._adicionar_diagnostico(
                    numero_processo, id_processo, "solicitar",
                    False, f"Resposta inesperada. Erro detectado: {tem_erro}. Mensagens: {mensagens}",
                    {"resposta_parcial": resposta_texto[:1000], "mensagens": mensagens}
                )
                
                # Salvar resposta para análise
                self._save_json(
                    {"resposta": resposta_texto[:5000], "mensagens": mensagens},
                    f"debug_resposta_{numero_processo.replace('.', '_')}.json"
                )
                
                return False, detalhes
                
        except Exception as e:
            self._adicionar_diagnostico(
                numero_processo, id_processo, "solicitar",
                False, f"Exceção: {str(e)}"
            )
            return False, detalhes
    
    # ==================== ÁREA DE DOWNLOAD ====================
    
    def listar_downloads_disponiveis(self) -> List[DownloadDisponivel]:
        """Lista downloads disponíveis."""
        if not self.usuario:
            self._verificar_sessao_ativa()
        
        try:
            resp = self.session.get(
                f"{API_BASE}/pjedocs-api/v1/downloadService/recuperarDownloadsDisponiveis",
                params={
                    "idUsuario": self.usuario.id_usuario,
                    "sistemaOrigem": "PRIMEIRA_INSTANCIA"
                },
                timeout=self.timeout
            )
            
            if resp.status_code == 200:
                data = resp.json()
                downloads = [DownloadDisponivel.from_dict(d) for d in data.get("downloadsDisponiveis", [])]
                self._log(f"Downloads disponíveis: {len(downloads)}")
                return downloads
                
        except Exception as e:
            self._log(f"Erro ao listar downloads: {e}", "ERROR")
        
        return []
    
    def obter_url_download(self, hash_download: str) -> Optional[str]:
        """Obtém URL do S3 para download."""
        try:
            resp = self.session.get(
                f"{API_BASE}/pjedocs-api/v2/repositorio/gerar-url-download",
                params={"hashDownload": hash_download},
                timeout=self.timeout
            )
            
            if resp.status_code == 200:
                return resp.text.strip().strip('"')
                
        except Exception as e:
            self._log(f"Erro ao obter URL: {e}", "ERROR")
        
        return None
    
    def baixar_arquivo(self, download: DownloadDisponivel) -> Optional[Path]:
        """Baixa um arquivo."""
        self._log(f"Baixando: {download.nome_arquivo}")
        
        url = self.obter_url_download(download.hash_download)
        if not url:
            return None
        
        try:
            resp = requests.get(url, stream=True, timeout=120)
            
            if resp.status_code == 200:
                filepath = self.download_dir / download.nome_arquivo
                
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                tamanho = filepath.stat().st_size
                self._log(f"✓ Salvo: {filepath} ({tamanho} bytes)")
                return filepath
                
        except Exception as e:
            self._log(f"Erro ao baixar: {e}", "ERROR")
        
        return None
    
    def aguardar_downloads(
        self,
        processos_solicitados: List[str],
        tempo_maximo: int = 300,
        intervalo: int = 15
    ) -> List[DownloadDisponivel]:
        """Aguarda downloads ficarem disponíveis."""
        self._log(f"\nAguardando {len(processos_solicitados)} downloads...")
        self._log(f"Processos: {processos_solicitados}")
        
        # Espera inicial
        time.sleep(15)
        
        inicio = time.time()
        encontrados: Set[str] = set()
        downloads_encontrados: List[DownloadDisponivel] = []
        tempo_sem_novos = 0
        
        while (time.time() - inicio) < tempo_maximo:
            elapsed = int(time.time() - inicio)
            downloads = self.listar_downloads_disponiveis()
            
            novos = set()
            for download in downloads:
                for proc in download.get_numeros_processos():
                    if proc in processos_solicitados and proc not in encontrados:
                        novos.add(proc)
                        encontrados.add(proc)
                        if download not in downloads_encontrados:
                            downloads_encontrados.append(download)
            
            self._log(f"[{elapsed}s] Encontrados: {len(encontrados)}/{len(processos_solicitados)}")
            
            if novos:
                self._log(f"  Novos: {novos}")
                tempo_sem_novos = 0
            else:
                tempo_sem_novos += intervalo
            
            pendentes = set(processos_solicitados) - encontrados
            if pendentes:
                self._log(f"  Pendentes: {pendentes}")
            
            if len(encontrados) >= len(processos_solicitados):
                self._log(f"✓ Todos os downloads disponíveis!")
                return downloads_encontrados
            
            if tempo_sem_novos >= 90 and encontrados:
                self._log(f"Timeout parcial. Continuando com {len(encontrados)}/{len(processos_solicitados)}", "WARN")
                return downloads_encontrados
            
            time.sleep(intervalo)
        
        self._log(f"Timeout total atingido!", "WARN")
        return downloads_encontrados
    
    # ==================== FLUXO COMPLETO ====================
    
    def processar_tarefa_com_diagnostico(
        self,
        nome_tarefa: str,
        nome_perfil: str = None,
        tipo_documento: str = "Selecione",
        limite_processos: int = None,
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Dict[str, Any]:
        """
        Processa uma tarefa com diagnósticos completos.
        """
        # Limpar diagnósticos anteriores
        self.diagnosticos.clear()
        self.downloads_solicitados.clear()
        
        relatorio = {
            "tarefa": nome_tarefa,
            "perfil": nome_perfil,
            "data_inicio": datetime.now().isoformat(),
            "processos_encontrados": 0,
            "solicitacoes_sucesso": 0,
            "solicitacoes_falha": 0,
            "downloads_concluidos": 0,
            "arquivos_baixados": [],
            "processos_sem_download": [],
            "diagnosticos_falha": [],
            "erros": []
        }
        
        self._log("\n" + "=" * 70)
        self._log(f"PROCESSANDO TAREFA: {nome_tarefa}")
        self._log("=" * 70)
        
        # Selecionar perfil
        if nome_perfil:
            if not self.select_profile(nome_perfil):
                relatorio["erros"].append(f"Falha ao selecionar perfil")
                return relatorio
            self._delay()
        
        # Buscar tarefa
        tarefa = self.buscar_tarefa_por_nome(nome_tarefa)
        if not tarefa:
            relatorio["erros"].append(f"Tarefa não encontrada")
            return relatorio
        
        self._log(f"Tarefa: {tarefa.nome} ({tarefa.quantidade_pendente} processos)")
        
        # Listar processos
        processos = self.listar_todos_processos_tarefa(tarefa.nome, tarefa.favorita)
        relatorio["processos_encontrados"] = len(processos)
        
        if not processos:
            self._log("Nenhum processo encontrado")
            return relatorio
        
        if limite_processos:
            processos = processos[:limite_processos]
            self._log(f"Limitado a {limite_processos} processos")
        
        # Processar cada processo
        processos_solicitados = []
        
        for i, proc in enumerate(processos, 1):
            self._log(f"\n[{i}/{len(processos)}] {proc.numero_processo}")
            
            sucesso, detalhes = self.solicitar_download_diagnostico(
                proc.id_processo,
                proc.numero_processo,
                tipo_documento
            )
            
            if sucesso:
                relatorio["solicitacoes_sucesso"] += 1
                processos_solicitados.append(proc.numero_processo)
            else:
                relatorio["solicitacoes_falha"] += 1
                relatorio["diagnosticos_falha"].append(detalhes)
            
            self._delay(2, 4)
        
        # Aguardar e baixar
        if aguardar_download and processos_solicitados:
            self._log("\n" + "=" * 70)
            self._log("AGUARDANDO DOWNLOADS")
            self._log("=" * 70)
            
            downloads = self.aguardar_downloads(processos_solicitados, tempo_espera)
            
            self._log("\n" + "=" * 70)
            self._log("BAIXANDO ARQUIVOS")
            self._log("=" * 70)
            
            processos_com_download = set()
            
            for download in downloads:
                self._delay()
                arquivo = self.baixar_arquivo(download)
                if arquivo:
                    relatorio["arquivos_baixados"].append(str(arquivo))
                    relatorio["downloads_concluidos"] += 1
                    processos_com_download.update(download.get_numeros_processos())
            
            # Identificar processos sem download
            sem_download = set(processos_solicitados) - processos_com_download
            relatorio["processos_sem_download"] = list(sem_download)
        
        relatorio["data_fim"] = datetime.now().isoformat()
        
        # Salvar relatório
        nome_arquivo = f"relatorio_{nome_tarefa.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self._save_json(relatorio, nome_arquivo)
        
        # Resumo final
        self._log("\n" + "=" * 70)
        self._log("RESUMO FINAL")
        self._log("=" * 70)
        self._log(f"Processos encontrados: {relatorio['processos_encontrados']}")
        self._log(f"Solicitações com sucesso: {relatorio['solicitacoes_sucesso']}")
        self._log(f"Solicitações com falha: {relatorio['solicitacoes_falha']}")
        self._log(f"Downloads concluídos: {relatorio['downloads_concluidos']}")
        
        if relatorio["processos_sem_download"]:
            self._log(f"\n⚠️  PROCESSOS SEM DOWNLOAD:", "WARN")
            for proc in relatorio["processos_sem_download"]:
                self._log(f"    - {proc}", "WARN")
        
        if relatorio["diagnosticos_falha"]:
            self._log(f"\n⚠️  DIAGNÓSTICOS DE FALHA:", "WARN")
            for diag in relatorio["diagnosticos_falha"]:
                self._log(f"    - {diag.get('numero_processo')}: Última etapa com erro", "WARN")
        
        return relatorio
    
    def close(self):
        """Fecha a sessão."""
        self.session.close()
        self._log("Sessão encerrada")


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def main():
    """Exemplo de uso."""
    
    pje = PJEAutomacaoUnificada(
        download_dir="./downloads",
        log_dir="./.logs",
        debug=True
    )
    
    try:
        # Login
        if not pje.login():
            print("Falha no login!")
            return
        
        # Listar tarefas
        print("\n" + "=" * 60)
        print("TAREFAS DISPONÍVEIS")
        print("=" * 60)
        
        favoritas = pje.listar_tarefas_favoritas()
        for t in favoritas:
            print(f"  ⭐ {t.nome}: {t.quantidade_pendente}")
        
        tarefas = pje.listar_tarefas()
        for t in tarefas:
            print(f"  - {t.nome}: {t.quantidade_pendente}")
        
        # Processar tarefa com diagnósticos
        relatorio = pje.processar_tarefa_com_diagnostico(
            nome_tarefa="Minutar decisão urgente",
            nome_perfil="V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL / Assessoria / Assessor",
            aguardar_download=True,
            tempo_espera=300,
            # limite_processos=5  # Descomente para testar com poucos processos
        )
        
        print(f"\nRelatório salvo em: .logs/")
        
    finally:
        pje.close()


if __name__ == "__main__":
    main()