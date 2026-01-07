"""
PJE Automacao via API
Automacao completa do sistema PJE TJBA usando requests (sem Selenium).

Funcionalidades:
- Login via OAuth2/OpenID Connect (Keycloak)
- Persistencia de sessao (cookies salvos em arquivo)
- Selecao de perfil por nome (com busca por semelhanca)
- Busca de processos por etiqueta
- Download de documentos
- Gerenciamento da area de download
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
from urllib.parse import urlparse
from typing import Optional, Dict, List, Any, Literal
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


# Tipos e Constantes

DocumentoTipo = Literal[
    "Selecione", "Peticao Inicial", "Peticao", "Documento de Identificacao",
    "Documento de Comprovacao", "Certidao", "Decisao", "Procuracao",
    "Despacho", "Sentenca", "Acordao", "Outros documentos"
]

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

BASE_URL = "https://pje.tjba.jus.br"
SSO_URL = "https://sso.cloud.pje.jus.br"
API_BASE = f"{BASE_URL}/pje/seam/resource/rest/pje-legacy"


# Dataclasses

@dataclass
class Etiqueta:
    id: int
    nome: str
    nome_completo: str = ""
    favorita: bool = False
    possui_filhos: bool = False
    
    @classmethod
    def from_dict(cls, data: dict) -> "Etiqueta":
        return cls(
            id=data.get("id", 0),
            nome=data.get("nomeTag", ""),
            nome_completo=data.get("nomeTagCompleto", ""),
            favorita=data.get("favorita", False),
            possui_filhos=data.get("possuiFilhos", False)
        )


@dataclass
class Processo:
    id_processo: int
    numero_processo: str
    polo_ativo: str = ""
    polo_passivo: str = ""
    classe_judicial: str = ""
    orgao_julgador: str = ""
    id_orgao_julgador: int = 0
    assunto_principal: str = ""
    sigiloso: bool = False
    prioridade: bool = False
    data_chegada: int = 0
    ultimo_movimento: int = 0
    descricao_ultimo_movimento: str = ""
    tags: List[Dict] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Processo":
        return cls(
            id_processo=data.get("idProcesso", 0),
            numero_processo=data.get("numeroProcesso", ""),
            polo_ativo=data.get("poloAtivo", ""),
            polo_passivo=data.get("poloPassivo", ""),
            classe_judicial=data.get("classeJudicial", ""),
            orgao_julgador=data.get("orgaoJulgador", ""),
            id_orgao_julgador=data.get("idOrgaoJulgador", 0),
            assunto_principal=data.get("assuntoPrincipal", ""),
            sigiloso=data.get("sigiloso", False),
            prioridade=data.get("prioridade", False),
            data_chegada=data.get("dataChegada", 0),
            ultimo_movimento=data.get("ultimoMovimento", 0),
            descricao_ultimo_movimento=data.get("descricaoUltimoMovimento", ""),
            tags=data.get("tagsProcessoList", [])
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


@dataclass
class Usuario:
    id_usuario: int
    nome: str
    login: str
    id_orgao_julgador: int
    id_papel: int
    id_localizacao_fisica: int
    
    @classmethod
    def from_dict(cls, data: dict) -> "Usuario":
        return cls(
            id_usuario=data.get("idUsuario", 0),
            nome=data.get("nomeUsuario", ""),
            login=data.get("login", ""),
            id_orgao_julgador=data.get("idOrgaoJulgador", 0),
            id_papel=data.get("idPapel", 0),
            id_localizacao_fisica=data.get("idLocalizacaoFisica", 0)
        )


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


class SessionManager:
    """Gerencia persistencia de sessao (cookies)."""
    
    def __init__(self, session_dir: str = ".session"):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.cookies_file = self.session_dir / "cookies.pkl"
        self.session_info_file = self.session_dir / "session_info.json"
    
    def save_session(self, session: requests.Session) -> bool:
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
        except Exception as e:
            print(f"[ERRO] Falha ao salvar sessao: {e}")
            return False
    
    def load_session(self, session: requests.Session) -> bool:
        """Carrega cookies salvos na sessao."""
        if not self.cookies_file.exists():
            return False
        
        try:
            with open(self.cookies_file, 'rb') as f:
                cookies = pickle.load(f)
            session.cookies.update(cookies)
            return True
        except Exception as e:
            print(f"[ERRO] Falha ao carregar sessao: {e}")
            return False
    
    def is_session_valid(self, max_age_hours: int = 8) -> bool:
        """Verifica se a sessao salva ainda e valida pelo tempo."""
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
        """Remove dados de sessao salvos."""
        if self.cookies_file.exists():
            self.cookies_file.unlink()
        if self.session_info_file.exists():
            self.session_info_file.unlink()


class PJEAutomation:
    """Automacao do sistema PJE via API REST."""
    
    def __init__(
        self,
        download_dir: str = None,
        log_dir: str = ".logs",
        session_dir: str = ".session",
        timeout: int = 30,
        delay_min: float = 1.0,
        delay_max: float = 3.0,
        session_max_age_hours: int = 8
    ):
        self.timeout = timeout
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.session_max_age_hours = session_max_age_hours
        
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
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
        })
        
        self.usuario: Optional[Usuario] = None
        self.perfis_disponiveis: List[Perfil] = []
        
        self._log(f"PJEAutomation inicializado")
        self._log(f"Downloads: {self.download_dir}")
        self._log(f"Logs: {self.log_dir}")
    
    # Utilitarios
    
    def _delay(self, min_sec: float = None, max_sec: float = None):
        min_sec = min_sec or self.delay_min
        max_sec = max_sec or self.delay_max
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def _log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def _save_json(self, data: Any, filename: str):
        filepath = self.log_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _calcular_similaridade(self, str1: str, str2: str) -> float:
        """Calcula similaridade entre duas strings (0.0 a 1.0)."""
        str1 = str1.lower().strip()
        str2 = str2.lower().strip()
        return SequenceMatcher(None, str1, str2).ratio()
    
    def _buscar_texto_similar(self, busca: str, lista: List[str], threshold: float = 0.6) -> Optional[int]:
        """
        Busca texto similar em uma lista.
        Retorna o indice do item mais similar ou None se nenhum atingir o threshold.
        """
        busca_lower = busca.lower().strip()
        
        # Primeiro, busca por correspondencia exata
        for i, item in enumerate(lista):
            if item.lower().strip() == busca_lower:
                return i
        
        # Segundo, busca por conteudo (se a busca esta contida no item)
        for i, item in enumerate(lista):
            if busca_lower in item.lower():
                return i
        
        # Terceiro, busca por similaridade
        melhor_match = None
        melhor_score = 0.0
        
        for i, item in enumerate(lista):
            score = self._calcular_similaridade(busca, item)
            if score > melhor_score and score >= threshold:
                melhor_score = score
                melhor_match = i
        
        return melhor_match
    
    # Sessao e Autenticacao
    
    def _verificar_sessao_ativa(self) -> bool:
        """Verifica se ha uma sessao ativa no servidor."""
        try:
            resp = self.session.get(
                f"{API_BASE}/usuario/currentUser",
                timeout=self.timeout
            )
            if resp.status_code == 200:
                self.usuario = Usuario.from_dict(resp.json())
                return True
        except:
            pass
        return False
    
    def _restaurar_sessao(self) -> bool:
        """Tenta restaurar sessao salva anteriormente."""
        if not self.session_manager.is_session_valid(self.session_max_age_hours):
            self._log("Sessao salva expirada ou inexistente")
            return False
        
        if not self.session_manager.load_session(self.session):
            self._log("Falha ao carregar cookies da sessao")
            return False
        
        if self._verificar_sessao_ativa():
            self._log(f"Sessao restaurada com sucesso. Usuario: {self.usuario.nome}")
            return True
        
        self._log("Cookies carregados mas sessao invalida no servidor")
        return False
    
    def login(self, username: str = None, password: str = None, force: bool = False) -> bool:
        """
        Realiza login no PJE.
        Primeiro tenta restaurar sessao existente, se falhar faz login novo.
        
        Args:
            username: CPF do usuario (sem pontos)
            password: Senha
            force: Se True, ignora sessao existente e faz novo login
        """
        username = username or os.getenv("USER")
        password = password or os.getenv("PASSWORD")
        
        if not username or not password:
            self._log("Credenciais nao fornecidas", "ERROR")
            return False
        
        # Tenta restaurar sessao existente (se nao for forcado)
        if not force:
            self._log("Verificando sessao existente...")
            
            if self._verificar_sessao_ativa():
                self._log(f"Ja esta logado. Usuario: {self.usuario.nome}")
                return True
            
            if self._restaurar_sessao():
                return True
        else:
            self._log("Login forcado - ignorando sessao existente")
            self.session_manager.clear_session()
        
        self._log(f"Iniciando novo login para {username}...")
        
        try:
            self._log("Obtendo parametros de autenticacao...")
            login_url = f"{BASE_URL}/pje/login.seam"
            resp = self.session.get(login_url, allow_redirects=True, timeout=self.timeout)
            
            current_url = resp.url
            
            if "sso.cloud.pje.jus.br" not in current_url:
                self._log("Nao redirecionou para SSO", "ERROR")
                return False
            
            self._log("Extraindo parametros do formulario...")
            action_match = re.search(r'action="([^"]*authenticate[^"]*)"', resp.text)
            if not action_match:
                self._log("Nao encontrou URL de autenticacao", "ERROR")
                return False
            
            auth_url = action_match.group(1).replace("&amp;", "&")
            if not auth_url.startswith("http"):
                auth_url = f"{SSO_URL}{auth_url}"
            
            self._delay()
            
            self._log("Enviando credenciais...")
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
            
            self._log("Verificando autenticacao...")
            self._delay()
            
            if self._verificar_sessao_ativa():
                self._log(f"Login bem-sucedido! Usuario: {self.usuario.nome}")
                self.session_manager.save_session(self.session)
                self._log("Sessao salva para uso futuro")
                return True
            else:
                self._log("Falha ao verificar usuario apos login", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Erro durante login: {e}", "ERROR")
            return False
    
    def ensure_logged_in(self) -> bool:
        """Verifica se esta logado, faz login se necessario."""
        if self._verificar_sessao_ativa():
            return True
        
        self._log("Sessao expirada, fazendo novo login...")
        return self.login()
    
    # Perfil
    
    def get_current_user(self) -> Optional[Usuario]:
        """Obtem informacoes do usuario atual."""
        try:
            resp = self.session.get(
                f"{API_BASE}/usuario/currentUser",
                timeout=self.timeout
            )
            if resp.status_code == 200:
                self.usuario = Usuario.from_dict(resp.json())
                return self.usuario
        except Exception as e:
            self._log(f"Erro ao obter usuario: {e}", "ERROR")
        return None
    
    def _extrair_perfis_da_pagina(self, html: str) -> List[Perfil]:
        """Extrai lista de perfis disponiveis do HTML."""
        perfis = []
        
        # Procura por links de perfil no dropdown
        pattern = r'dtPerfil:(\d+):j_id70[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.IGNORECASE)
        
        if not matches:
            pattern = r'<a[^>]*onclick="[^"]*dtPerfil:(\d+)[^"]*"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html, re.IGNORECASE)
        
        for index_str, nome in matches:
            index = int(index_str)
            nome_limpo = nome.strip()
            
            partes = nome_limpo.split(" / ")
            perfil = Perfil(
                index=index,
                nome=partes[0] if partes else nome_limpo,
                orgao=partes[1] if len(partes) > 1 else "",
                cargo=partes[2] if len(partes) > 2 else ""
            )
            perfis.append(perfil)
        
        return perfis
    
    def listar_perfis(self) -> List[Perfil]:
        """Lista perfis disponiveis para o usuario."""
        if not self.ensure_logged_in():
            return []
        
        self._log("Listando perfis disponiveis...")
        
        try:
            resp = self.session.get(
                f"{BASE_URL}/pje/ng2/dev.seam",
                timeout=self.timeout
            )
            
            if resp.status_code == 200:
                self.perfis_disponiveis = self._extrair_perfis_da_pagina(resp.text)
                self._log(f"Encontrados {len(self.perfis_disponiveis)} perfis")
                
                for perfil in self.perfis_disponiveis:
                    self._log(f"  [{perfil.index}] {perfil.nome_completo}")
                
                return self.perfis_disponiveis
                
        except Exception as e:
            self._log(f"Erro ao listar perfis: {e}", "ERROR")
        
        return []
    
    def select_profile_by_index(self, profile_index: int) -> bool:
        """Seleciona um perfil pelo indice."""
        if not self.ensure_logged_in():
            return False
        
        self._log(f"Selecionando perfil indice {profile_index}...")
        
        try:
            resp = self.session.get(
                f"{BASE_URL}/pje/ng2/dev.seam",
                timeout=self.timeout
            )
            
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
                    "Referer": f"{BASE_URL}/pje/ng2/dev.seam"
                }
            )
            
            self._delay()
            new_user = self.get_current_user()
            
            if new_user:
                self._log(f"Perfil selecionado: {new_user.nome} (Papel: {new_user.id_papel})")
                self.session_manager.save_session(self.session)
                return True
            
            return False
            
        except Exception as e:
            self._log(f"Erro ao selecionar perfil: {e}", "ERROR")
            return False
    
    def select_profile(self, nome_perfil: str) -> bool:
        """
        Seleciona um perfil pelo nome.
        Primeiro busca correspondencia exata, depois por semelhanca.
        
        Args:
            nome_perfil: Nome do perfil (ex: "Direcao Criminal", "V DOS FEITOS...")
        """
        if not self.ensure_logged_in():
            return False
        
        self._log(f"Buscando perfil: '{nome_perfil}'...")
        
        if not self.perfis_disponiveis:
            self.listar_perfis()
        
        if not self.perfis_disponiveis:
            self._log("Nenhum perfil disponivel", "ERROR")
            return False
        
        nomes_perfis = [p.nome_completo for p in self.perfis_disponiveis]
        
        indice_encontrado = self._buscar_texto_similar(nome_perfil, nomes_perfis, threshold=0.4)
        
        if indice_encontrado is None:
            self._log(f"Perfil '{nome_perfil}' nao encontrado", "ERROR")
            self._log("Perfis disponiveis:")
            for p in self.perfis_disponiveis:
                self._log(f"  - {p.nome_completo}")
            return False
        
        perfil = self.perfis_disponiveis[indice_encontrado]
        self._log(f"Perfil encontrado: '{perfil.nome_completo}'")
        
        return self.select_profile_by_index(perfil.index)
    
    # Etiquetas
    
    def buscar_etiquetas(
        self,
        busca: str = "",
        page: int = 0,
        max_results: int = 30
    ) -> List[Etiqueta]:
        """Busca etiquetas pelo nome."""
        if not self.ensure_logged_in():
            return []
        
        self._log(f"Buscando etiquetas: '{busca}'...")
        
        try:
            resp = self.session.post(
                f"{API_BASE}/painelUsuario/etiquetas",
                json={
                    "page": page,
                    "maxResults": max_results,
                    "tagsString": busca
                },
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                etiquetas = [Etiqueta.from_dict(e) for e in data.get("entities", [])]
                self._log(f"Encontradas {len(etiquetas)} etiquetas (total: {data.get('count', 0)})")
                return etiquetas
            else:
                self._log(f"Erro ao buscar etiquetas: {resp.status_code}", "ERROR")
                
        except Exception as e:
            self._log(f"Erro ao buscar etiquetas: {e}", "ERROR")
        
        return []
    
    def buscar_etiqueta_por_nome(self, nome: str) -> Optional[Etiqueta]:
        """Busca uma etiqueta especifica pelo nome."""
        etiquetas = self.buscar_etiquetas(nome)
        for et in etiquetas:
            if et.nome.lower() == nome.lower():
                return et
        return etiquetas[0] if etiquetas else None
    
    # Processos
    
    def listar_processos_etiqueta(
        self,
        id_etiqueta: int,
        limit: int = 100
    ) -> List[Processo]:
        """Lista processos de uma etiqueta."""
        if not self.ensure_logged_in():
            return []
        
        self._log(f"Listando processos da etiqueta {id_etiqueta}...")
        
        try:
            resp_total = self.session.get(
                f"{API_BASE}/painelUsuario/etiquetas/{id_etiqueta}/processos/total",
                timeout=self.timeout
            )
            total = int(resp_total.text) if resp_total.status_code == 200 else 0
            self._log(f"Total de processos: {total}")
            
            self._delay()
            
            resp = self.session.get(
                f"{API_BASE}/painelUsuario/etiquetas/{id_etiqueta}/processos",
                params={"limit": limit},
                timeout=self.timeout
            )
            
            if resp.status_code == 200:
                processos = [Processo.from_dict(p) for p in resp.json()]
                self._log(f"Retornados {len(processos)} processos")
                return processos
                
        except Exception as e:
            self._log(f"Erro ao listar processos: {e}", "ERROR")
        
        return []
    
    def gerar_chave_acesso(self, id_processo: int) -> Optional[str]:
        """Gera chave de acesso para um processo."""
        try:
            resp = self.session.get(
                f"{API_BASE}/painelUsuario/gerarChaveAcessoProcesso/{id_processo}",
                timeout=self.timeout
            )
            
            if resp.status_code == 200:
                return resp.text.strip()
                
        except Exception as e:
            self._log(f"Erro ao gerar chave de acesso: {e}", "ERROR")
        
        return None
    
    def abrir_processo(self, id_processo: int) -> Optional[str]:
        """Abre a pagina de autos digitais de um processo."""
        if not self.ensure_logged_in():
            return None
        
        self._log(f"Abrindo processo {id_processo}...")
        
        ca = self.gerar_chave_acesso(id_processo)
        if not ca:
            self._log("Nao foi possivel gerar chave de acesso", "ERROR")
            return None
        
        self._delay()
        
        try:
            resp = self.session.get(
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam",
                params={
                    "idProcesso": id_processo,
                    "ca": ca
                },
                timeout=self.timeout
            )
            
            if resp.status_code == 200:
                self._log("Processo aberto")
                return resp.text
                
        except Exception as e:
            self._log(f"Erro ao abrir processo: {e}", "ERROR")
        
        return None
    
    # Download de Documentos
    
    def solicitar_download(
        self,
        id_processo: int,
        tipo_documento: str = "Selecione",
        html_processo: str = None
    ) -> bool:
        """Solicita download de documentos de um processo."""
        if not self.ensure_logged_in():
            return False
        
        self._log(f"Solicitando download - Processo {id_processo}, Tipo: {tipo_documento}")
        
        if not html_processo:
            html_processo = self.abrir_processo(id_processo)
            if not html_processo:
                return False
        
        viewstate_match = re.search(
            r'name="javax\.faces\.ViewState"[^>]*value="([^"]*)"',
            html_processo
        )
        viewstate = viewstate_match.group(1) if viewstate_match else "j_id37"
        
        tipo_value = TIPO_DOCUMENTO_VALUES.get(tipo_documento, "0")
        
        self._delay()
        
        try:
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
                "navbar": "navbar",
                "autoScroll": "",
                "javax.faces.ViewState": viewstate,
                "navbar:j_id267": "navbar:j_id267",
                "AJAX:EVENTS_COUNT": "1",
            }
            
            resp = self.session.post(
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam",
                data=form_data,
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam"
                }
            )
            
            if resp.status_code == 200:
                self._log("Solicitacao de download enviada")
                return True
            else:
                self._log(f"Erro ao solicitar download: {resp.status_code}", "ERROR")
                
        except Exception as e:
            self._log(f"Erro ao solicitar download: {e}", "ERROR")
        
        return False
    
    # Area de Download
    
    def listar_downloads_disponiveis(self) -> List[DownloadDisponivel]:
        """Lista downloads disponiveis na area de download."""
        if not self.ensure_logged_in():
            return []
        
        if not self.usuario:
            self.get_current_user()
        
        self._log("Listando downloads disponiveis...")
        
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
                downloads = [
                    DownloadDisponivel.from_dict(d) 
                    for d in data.get("downloadsDisponiveis", [])
                ]
                self._log(f"Encontrados {len(downloads)} downloads")
                return downloads
                
        except Exception as e:
            self._log(f"Erro ao listar downloads: {e}", "ERROR")
        
        return []
    
    def obter_url_download(self, hash_download: str) -> Optional[str]:
        """Obtem URL pre-assinada do S3 para download."""
        try:
            resp = self.session.get(
                f"{API_BASE}/pjedocs-api/v2/repositorio/gerar-url-download",
                params={"hashDownload": hash_download},
                timeout=self.timeout
            )
            
            if resp.status_code == 200:
                return resp.text.strip()
                
        except Exception as e:
            self._log(f"Erro ao obter URL de download: {e}", "ERROR")
        
        return None
    
    def baixar_arquivo(
        self,
        download: DownloadDisponivel,
        diretorio: Path = None
    ) -> Optional[Path]:
        """Baixa um arquivo da area de download."""
        diretorio = diretorio or self.download_dir
        
        self._log(f"Baixando: {download.nome_arquivo}")
        
        url = self.obter_url_download(download.hash_download)
        if not url:
            self._log("Nao foi possivel obter URL de download", "ERROR")
            return None
        
        try:
            resp = requests.get(url, stream=True, timeout=60)
            
            if resp.status_code == 200:
                filepath = diretorio / download.nome_arquivo
                
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                self._log(f"Arquivo salvo: {filepath}")
                return filepath
            else:
                self._log(f"Erro ao baixar: {resp.status_code}", "ERROR")
                
        except Exception as e:
            self._log(f"Erro ao baixar arquivo: {e}", "ERROR")
        
        return None
    
    def baixar_todos_downloads(self, filtro_processo: str = None) -> List[Path]:
        """Baixa todos os arquivos disponiveis na area de download."""
        downloads = self.listar_downloads_disponiveis()
        arquivos_baixados = []
        
        for download in downloads:
            if filtro_processo:
                processos_no_download = [
                    item.get("numeroProcesso", "") 
                    for item in download.itens
                ]
                if filtro_processo not in processos_no_download:
                    continue
            
            self._delay()
            
            arquivo = self.baixar_arquivo(download)
            if arquivo:
                arquivos_baixados.append(arquivo)
        
        self._log(f"Total de arquivos baixados: {len(arquivos_baixados)}")
        return arquivos_baixados
    
    # Fluxo Completo
    
    def processar_etiqueta(
        self,
        nome_etiqueta: str,
        nome_perfil: str = None,
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 30
    ) -> Dict[str, Any]:
        """
        Processa todos os processos de uma etiqueta.
        
        Args:
            nome_etiqueta: Nome da etiqueta
            nome_perfil: Nome do perfil a selecionar (opcional)
            tipo_documento: Tipo de documento para download
            aguardar_download: Se deve aguardar e baixar automaticamente
            tempo_espera: Tempo de espera em segundos para processamento
        """
        relatorio = {
            "etiqueta": nome_etiqueta,
            "perfil": nome_perfil,
            "tipo_documento": tipo_documento,
            "data_inicio": datetime.now().isoformat(),
            "processos_encontrados": 0,
            "downloads_solicitados": 0,
            "downloads_concluidos": 0,
            "erros": [],
            "arquivos_baixados": []
        }
        
        self._log(f"PROCESSANDO ETIQUETA: {nome_etiqueta}")
        
        # Seleciona perfil se especificado
        if nome_perfil:
            if not self.select_profile(nome_perfil):
                relatorio["erros"].append(f"Falha ao selecionar perfil '{nome_perfil}'")
                self._log("Falha ao selecionar perfil", "ERROR")
                return relatorio
            self._delay()
        
        # Busca etiqueta
        etiqueta = self.buscar_etiqueta_por_nome(nome_etiqueta)
        if not etiqueta:
            relatorio["erros"].append(f"Etiqueta '{nome_etiqueta}' nao encontrada")
            self._log("Etiqueta nao encontrada", "ERROR")
            return relatorio
        
        self._log(f"Etiqueta encontrada: ID={etiqueta.id}")
        self._delay()
        
        # Lista processos
        processos = self.listar_processos_etiqueta(etiqueta.id)
        relatorio["processos_encontrados"] = len(processos)
        
        if not processos:
            self._log("Nenhum processo encontrado na etiqueta")
            return relatorio
        
        # Processa cada processo
        for i, processo in enumerate(processos, 1):
            self._log(f"Processo {i}/{len(processos)} - {processo.numero_processo}")
            
            try:
                html = self.abrir_processo(processo.id_processo)
                if not html:
                    relatorio["erros"].append(f"Falha ao abrir processo {processo.numero_processo}")
                    continue
                
                self._delay()
                
                if self.solicitar_download(processo.id_processo, tipo_documento, html):
                    relatorio["downloads_solicitados"] += 1
                else:
                    relatorio["erros"].append(f"Falha ao solicitar download: {processo.numero_processo}")
                
                self._delay(2, 4)
                
            except Exception as e:
                relatorio["erros"].append(f"Erro no processo {processo.numero_processo}: {str(e)}")
                self._log(f"Erro: {e}", "ERROR")
        
        # Aguarda processamento e baixa
        if aguardar_download and relatorio["downloads_solicitados"] > 0:
            self._log(f"Aguardando {tempo_espera}s para processamento dos downloads...")
            time.sleep(tempo_espera)
            
            self._log("Baixando arquivos da area de download...")
            arquivos = self.baixar_todos_downloads()
            relatorio["arquivos_baixados"] = [str(a) for a in arquivos]
            relatorio["downloads_concluidos"] = len(arquivos)
        
        relatorio["data_fim"] = datetime.now().isoformat()
        
        self._save_json(relatorio, f"relatorio_{nome_etiqueta}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        self._log("RESUMO DO PROCESSAMENTO")
        self._log(f"Processos encontrados: {relatorio['processos_encontrados']}")
        self._log(f"Downloads solicitados: {relatorio['downloads_solicitados']}")
        self._log(f"Downloads concluidos: {relatorio['downloads_concluidos']}")
        self._log(f"Erros: {len(relatorio['erros'])}")
        
        return relatorio
    
    def close(self):
        """Fecha a sessao."""
        self.session.close()
        self._log("Sessao encerrada")


def main():
    """Funcao principal de exemplo."""
    
    pje = PJEAutomation(
        download_dir="./downloads",
        log_dir="./.logs",
        session_dir="./.session"
    )
    
    try:
        if not pje.login():
            print("Falha no login")
            return
        
        relatorio = pje.processar_etiqueta(
            nome_etiqueta="Felipe",
            nome_perfil="V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL",
            tipo_documento="Selecione",
            aguardar_download=True,
            tempo_espera=30
        )
        
        print(f"\nProcessamento concluido!")
        print(f"Arquivos baixados: {len(relatorio['arquivos_baixados'])}")
        
    finally:
        pje.close()


if __name__ == "__main__":
    main()