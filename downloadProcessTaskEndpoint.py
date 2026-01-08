"""
PJE Automacao via API - Tarefas
Automacao completa do sistema PJE TJBA usando requests (sem Selenium).

Funcionalidades:
- Login via OAuth2/OpenID Connect (Keycloak)
- Persistencia de sessao (cookies salvos em arquivo)
- Selecao de perfil por nome (com busca por semelhanca)
- Listagem de tarefas (favoritas e todas)
- Busca de processos por tarefa
- Download de documentos de processos
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
from urllib.parse import urlparse, quote
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
class Tarefa:
    """Representa uma tarefa no painel do PJE."""
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
    """Representa um processo dentro de uma tarefa."""
    id_processo: int
    numero_processo: str
    id_task_instance: int
    id_task_instance_proximo: int = 0
    polo_ativo: str = ""
    polo_passivo: str = ""
    classe_judicial: str = ""
    orgao_julgador: str = ""
    id_orgao_julgador: int = 0
    assunto_principal: str = ""
    sigiloso: bool = False
    prioridade: bool = False
    conferido: bool = False
    nome_tarefa: str = ""
    cargo_judicial: str = ""
    data_chegada: int = 0
    ultimo_movimento: int = 0
    descricao_ultimo_movimento: str = ""
    tags: List[Dict] = field(default_factory=list)
    pode_minutar_em_lote: bool = False
    pode_movimentar_em_lote: bool = False
    pode_intimar_em_lote: bool = False
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProcessoTarefa":
        return cls(
            id_processo=data.get("idProcesso", 0),
            numero_processo=data.get("numeroProcesso", ""),
            id_task_instance=data.get("idTaskInstance", 0),
            id_task_instance_proximo=data.get("idTaskInstanceProximo", 0),
            polo_ativo=data.get("poloAtivo", ""),
            polo_passivo=data.get("poloPassivo", ""),
            classe_judicial=data.get("classeJudicial", ""),
            orgao_julgador=data.get("orgaoJulgador", ""),
            id_orgao_julgador=data.get("idOrgaoJulgador", 0),
            assunto_principal=data.get("assuntoPrincipal", ""),
            sigiloso=data.get("sigiloso", False),
            prioridade=data.get("prioridade", False),
            conferido=data.get("conferido", False),
            nome_tarefa=data.get("nomeTarefa", ""),
            cargo_judicial=data.get("cargoJudicial", ""),
            data_chegada=data.get("dataChegada", 0),
            ultimo_movimento=data.get("ultimoMovimento", 0),
            descricao_ultimo_movimento=data.get("descricaoUltimoMovimento", ""),
            tags=data.get("tagsProcessoList", []),
            pode_minutar_em_lote=data.get("podeMinutarEmLote", False),
            pode_movimentar_em_lote=data.get("podeMovimentarEmLote", False),
            pode_intimar_em_lote=data.get("podeIntimarEmLote", False)
        )


@dataclass
class Etiqueta:
    id: int
    nome: str
    nome_completo: str = ""
    favorita: bool = False
    possui_filhos: bool = False
    qtde_processos: int = 0
    
    @classmethod
    def from_dict(cls, data: dict) -> "Etiqueta":
        return cls(
            id=data.get("id", 0),
            nome=data.get("nomeTag", data.get("nomeTagCompleto", "")),
            nome_completo=data.get("nomeTagCompleto", ""),
            favorita=data.get("favorita", False),
            possui_filhos=data.get("possuiFilhos", False),
            qtde_processos=data.get("qtdeProcessos", 0)
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


class PJEAutomacaoTarefas:
    """Automacao do sistema PJE via API REST - Foco em Tarefas."""
    
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
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
        })
        
        self.usuario: Optional[Usuario] = None
        self.perfis_disponiveis: List[Perfil] = []
        self.tarefas_cache: List[Tarefa] = []
        self.tarefas_favoritas_cache: List[Tarefa] = []
        
        self._log(f"PJEAutomacaoTarefas inicializado")
        self._log(f"Downloads: {self.download_dir}")
        self._log(f"Logs: {self.log_dir}")
    
    # ==================== UTILITARIOS ====================
    
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
    
    def _normalizar_texto(self, texto: str) -> str:
        """Normaliza texto para comparação (remove acentos, lowercase, etc)."""
        import unicodedata
        # Remove acentos
        texto_normalizado = unicodedata.normalize('NFKD', texto)
        texto_sem_acento = ''.join(c for c in texto_normalizado if not unicodedata.combining(c))
        return texto_sem_acento.lower().strip()
    
    def _buscar_texto_similar(self, busca: str, lista: List[str], threshold: float = 0.6) -> Optional[int]:
        """
        Busca texto similar em uma lista.
        Retorna o indice do item mais similar ou None se nenhum atingir o threshold.
        
        Ordem de prioridade:
        1. Correspondência EXATA (case insensitive, com e sem acentos)
        2. Correspondência por conteúdo (busca contida no item) - prioriza match mais específico
        3. Similaridade por algoritmo (SequenceMatcher) - prioriza maior score
        """
        busca_lower = busca.lower().strip()
        busca_normalizada = self._normalizar_texto(busca)
        
        # 1. PRIORIDADE MÁXIMA: Correspondência EXATA (case insensitive)
        for i, item in enumerate(lista):
            item_lower = item.lower().strip()
            item_normalizado = self._normalizar_texto(item)
            
            # Match exato com ou sem acentos
            if item_lower == busca_lower or item_normalizado == busca_normalizada:
                return i
        
        # 2. SEGUNDA PRIORIDADE: Busca está contida no item
        # Ordena por quão específico é o match (menor diferença de tamanho = melhor)
        matches_contem = []
        for i, item in enumerate(lista):
            item_lower = item.lower().strip()
            item_normalizado = self._normalizar_texto(item)
            
            # Verifica se a busca está contida no item (com e sem acentos)
            if busca_lower in item_lower or busca_normalizada in item_normalizado:
                # Quanto menor a diferença, mais específico é o match
                diferenca = abs(len(item_lower) - len(busca_lower))
                # Também calcula a similaridade para desempate
                similaridade = self._calcular_similaridade(busca, item)
                matches_contem.append((i, diferenca, similaridade, item))
        
        if matches_contem:
            # Ordena por: menor diferença primeiro, depois maior similaridade
            matches_contem.sort(key=lambda x: (x[1], -x[2]))
            melhor = matches_contem[0]
            self._log(f"Match por conteudo: '{busca}' -> '{melhor[3]}' (diff={melhor[1]}, sim={melhor[2]:.2f})", "DEBUG")
            return melhor[0]
        
        # 3. TERCEIRA PRIORIDADE: Item está contido na busca
        matches_inverso = []
        for i, item in enumerate(lista):
            item_lower = item.lower().strip()
            item_normalizado = self._normalizar_texto(item)
            
            if item_lower in busca_lower or item_normalizado in busca_normalizada:
                diferenca = abs(len(busca_lower) - len(item_lower))
                similaridade = self._calcular_similaridade(busca, item)
                matches_inverso.append((i, diferenca, similaridade, item))
        
        if matches_inverso:
            matches_inverso.sort(key=lambda x: (x[1], -x[2]))
            melhor = matches_inverso[0]
            self._log(f"Match inverso: '{busca}' -> '{melhor[3]}' (diff={melhor[1]}, sim={melhor[2]:.2f})", "DEBUG")
            return melhor[0]
        
        # 4. ÚLTIMA PRIORIDADE: Similaridade por algoritmo
        matches_similaridade = []
        for i, item in enumerate(lista):
            score = self._calcular_similaridade(busca, item)
            if score >= threshold:
                matches_similaridade.append((i, score, item))
        
        if matches_similaridade:
            # Ordena por maior score
            matches_similaridade.sort(key=lambda x: -x[1])
            melhor = matches_similaridade[0]
            self._log(f"Match por similaridade: '{busca}' -> '{melhor[2]}' (score={melhor[1]:.2f})", "DEBUG")
            return melhor[0]
        
        return None
    
    # ==================== SESSAO E AUTENTICACAO ====================
    
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
    
    # ==================== PERFIL ====================
    
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
                # Limpa cache de tarefas pois mudou de perfil
                self.tarefas_cache = []
                self.tarefas_favoritas_cache = []
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
    
    # ==================== TAREFAS ====================
    
    def limpar_cache_tarefas(self):
        """Limpa o cache de tarefas (deve ser chamado após mudar de perfil)."""
        self.tarefas_cache = []
        self.tarefas_favoritas_cache = []
        self._log("Cache de tarefas limpo")
    
    def listar_tarefas(
        self,
        numero_processo: str = "",
        competencia: str = "",
        etiquetas: List[int] = None
    ) -> List[Tarefa]:
        """
        Lista todas as tarefas disponiveis no painel.
        
        Args:
            numero_processo: Filtro por numero de processo
            competencia: Filtro por competencia
            etiquetas: Lista de IDs de etiquetas para filtrar
        """
        if not self.ensure_logged_in():
            return []
        
        self._log("Listando tarefas...")
        
        try:
            payload = {
                "numeroProcesso": numero_processo,
                "competencia": competencia,
                "etiquetas": etiquetas or []
            }
            
            resp = self.session.post(
                f"{API_BASE}/painelUsuario/tarefas",
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self.tarefas_cache = [Tarefa.from_dict(t) for t in data]
                self._log(f"Encontradas {len(self.tarefas_cache)} tarefas")
                
                for tarefa in self.tarefas_cache:
                    self._log(f"  [{tarefa.id}] {tarefa.nome}: {tarefa.quantidade_pendente} processos")
                
                return self.tarefas_cache
            else:
                self._log(f"Erro ao listar tarefas: {resp.status_code}", "ERROR")
                
        except Exception as e:
            self._log(f"Erro ao listar tarefas: {e}", "ERROR")
        
        return []
    
    def listar_tarefas_favoritas(
        self,
        numero_processo: str = "",
        competencia: str = "",
        etiquetas: List[int] = None
    ) -> List[Tarefa]:
        """
        Lista as tarefas favoritas (Minhas Tarefas) do painel.
        
        Args:
            numero_processo: Filtro por numero de processo
            competencia: Filtro por competencia
            etiquetas: Lista de IDs de etiquetas para filtrar
        """
        if not self.ensure_logged_in():
            return []
        
        self._log("Listando tarefas favoritas...")
        
        try:
            payload = {
                "numeroProcesso": numero_processo,
                "competencia": competencia,
                "etiquetas": etiquetas or []
            }
            
            resp = self.session.post(
                f"{API_BASE}/painelUsuario/tarefasFavoritas",
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self.tarefas_favoritas_cache = [Tarefa.from_dict(t, favorita=True) for t in data]
                self._log(f"Encontradas {len(self.tarefas_favoritas_cache)} tarefas favoritas")
                
                for tarefa in self.tarefas_favoritas_cache:
                    self._log(f"  [{tarefa.id}] {tarefa.nome}: {tarefa.quantidade_pendente} processos")
                
                return self.tarefas_favoritas_cache
            else:
                self._log(f"Erro ao listar tarefas favoritas: {resp.status_code}", "ERROR")
                
        except Exception as e:
            self._log(f"Erro ao listar tarefas favoritas: {e}", "ERROR")
        
        return []
    
    def buscar_tarefa_por_nome(self, nome: str, favoritas_primeiro: bool = True, forcar_atualizacao: bool = False) -> Optional[Tarefa]:
        """
        Busca uma tarefa pelo nome (com busca por similaridade).
        
        Args:
            nome: Nome da tarefa
            favoritas_primeiro: Se True, busca primeiro nas favoritas
            forcar_atualizacao: Se True, força atualização do cache de tarefas
        """
        # Atualiza cache se necessario ou se forcado
        if forcar_atualizacao or (favoritas_primeiro and not self.tarefas_favoritas_cache):
            self.listar_tarefas_favoritas()
        if forcar_atualizacao or not self.tarefas_cache:
            self.listar_tarefas()
        
        nome_normalizado = self._normalizar_texto(nome)
        
        # PRIMEIRO: Busca por match EXATO em TODAS as tarefas (favoritas + todas)
        # Isso garante que se existe uma tarefa com nome exato, ela será encontrada
        todas_tarefas = []
        if favoritas_primeiro:
            todas_tarefas.extend(self.tarefas_favoritas_cache)
        todas_tarefas.extend(self.tarefas_cache)
        
        for tarefa in todas_tarefas:
            tarefa_normalizada = self._normalizar_texto(tarefa.nome)
            if tarefa_normalizada == nome_normalizado:
                self._log(f"Match EXATO encontrado: '{tarefa.nome}'")
                return tarefa
        
        # SEGUNDO: Busca nas favoritas com threshold alto (só aceita matches muito bons)
        if favoritas_primeiro and self.tarefas_favoritas_cache:
            nomes_favoritas = [t.nome for t in self.tarefas_favoritas_cache]
            indice = self._buscar_texto_similar(nome, nomes_favoritas, threshold=0.85)
            if indice is not None:
                return self.tarefas_favoritas_cache[indice]
        
        # TERCEIRO: Busca em todas as tarefas com threshold normal
        nomes_todas = [t.nome for t in self.tarefas_cache]
        indice = self._buscar_texto_similar(nome, nomes_todas, threshold=0.4)
        if indice is not None:
            return self.tarefas_cache[indice]
        
        return None
    
    def listar_processos_tarefa(
        self,
        nome_tarefa: str,
        page: int = 0,
        max_results: int = 100,
        filtros: Dict = None,
        apenas_favoritas: bool = False
    ) -> tuple[List[ProcessoTarefa], int]:
        """
        Lista processos de uma tarefa especifica.
        
        Args:
            nome_tarefa: Nome da tarefa
            page: Pagina (começa em 0)
            max_results: Maximo de resultados por pagina
            filtros: Filtros adicionais
            apenas_favoritas: Se True, busca usando endpoint de favoritas
        
        Returns:
            Tupla (lista de processos, total de processos)
        """
        if not self.ensure_logged_in():
            return [], 0
        
        self._log(f"Listando processos da tarefa '{nome_tarefa}'...")
        
        # Codifica o nome da tarefa para URL
        nome_tarefa_encoded = quote(nome_tarefa)
        
        # Payload padrao
        payload = {
            "numeroProcesso": "",
            "classe": None,
            "tags": [],
            "tagsString": None,
            "poloAtivo": None,
            "poloPassivo": None,
            "orgao": None,
            "ordem": None,
            "page": page,
            "maxResults": max_results,
            "idTaskInstance": None,
            "apelidoSessao": None,
            "idTipoSessao": None,
            "dataSessao": None,
            "somenteFavoritas": None,
            "objeto": None,
            "semEtiqueta": None,
            "assunto": None,
            "dataAutuacao": None,
            "nomeParte": None,
            "nomeFiltro": None,
            "numeroDocumento": None,
            "competencia": "",
            "relator": None,
            "orgaoJulgador": None,
            "somenteLembrete": None,
            "somenteSigiloso": None,
            "somenteLiminar": None,
            "eleicao": None,
            "estado": None,
            "municipio": None,
            "prioridadeProcesso": None,
            "cpfCnpj": None,
            "porEtiqueta": None,
            "conferidos": None,
            "orgaoJulgadorColegiado": None,
            "naoLidos": None,
            "tipoProcessoDocumento": None
        }
        
        # Aplica filtros adicionais
        if filtros:
            payload.update(filtros)
        
        try:
            # Endpoint depende se é favorita ou não
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
                
                self._log(f"Encontrados {len(processos)} processos (total: {total})")
                return processos, total
            else:
                self._log(f"Erro ao listar processos da tarefa: {resp.status_code}", "ERROR")
                self._log(f"Resposta: {resp.text[:500]}", "DEBUG")
                
        except Exception as e:
            self._log(f"Erro ao listar processos da tarefa: {e}", "ERROR")
        
        return [], 0
    
    def listar_todos_processos_tarefa(
        self,
        nome_tarefa: str,
        filtros: Dict = None,
        apenas_favoritas: bool = False,
        batch_size: int = 100
    ) -> List[ProcessoTarefa]:
        """
        Lista TODOS os processos de uma tarefa (com paginacao automatica).
        
        Args:
            nome_tarefa: Nome da tarefa
            filtros: Filtros adicionais
            apenas_favoritas: Se True, busca usando endpoint de favoritas
            batch_size: Tamanho do batch por requisicao
        
        Returns:
            Lista completa de processos
        """
        todos_processos = []
        page = 0
        
        while True:
            processos, total = self.listar_processos_tarefa(
                nome_tarefa=nome_tarefa,
                page=page,
                max_results=batch_size,
                filtros=filtros,
                apenas_favoritas=apenas_favoritas
            )
            
            if not processos:
                break
            
            todos_processos.extend(processos)
            self._log(f"Carregados {len(todos_processos)}/{total} processos")
            
            if len(todos_processos) >= total:
                break
            
            page += 1
            self._delay(0.5, 1.0)
        
        return todos_processos
    
    def listar_etiquetas_tarefa(
        self,
        nome_tarefa: str,
        filtros: Dict = None,
        apenas_favoritas: bool = False
    ) -> List[Etiqueta]:
        """
        Lista etiquetas associadas aos processos de uma tarefa.
        
        Args:
            nome_tarefa: Nome da tarefa
            filtros: Filtros adicionais
            apenas_favoritas: Se True, usa endpoint de favoritas
        
        Returns:
            Lista de etiquetas com quantidade de processos
        """
        if not self.ensure_logged_in():
            return []
        
        self._log(f"Listando etiquetas da tarefa '{nome_tarefa}'...")
        
        nome_tarefa_encoded = quote(nome_tarefa)
        
        payload = {
            "numeroProcesso": "",
            "classe": None,
            "tags": [],
            "tagsString": None,
            "poloAtivo": None,
            "poloPassivo": None,
            "orgao": None,
            "ordem": None,
            "page": 0,
            "maxResults": 30,
            "idTaskInstance": None,
            "apelidoSessao": None,
            "idTipoSessao": None,
            "dataSessao": None,
            "somenteFavoritas": None,
            "objeto": None,
            "semEtiqueta": None,
            "assunto": None,
            "dataAutuacao": None,
            "nomeParte": None,
            "nomeFiltro": None,
            "numeroDocumento": None,
            "competencia": "",
            "relator": None,
            "orgaoJulgador": None,
            "somenteLembrete": None,
            "somenteSigiloso": None,
            "somenteLiminar": None,
            "eleicao": None,
            "estado": None,
            "municipio": None,
            "prioridadeProcesso": None,
            "cpfCnpj": None,
            "porEtiqueta": None,
            "conferidos": None,
            "orgaoJulgadorColegiado": None,
            "naoLidos": None,
            "tipoProcessoDocumento": None
        }
        
        if filtros:
            payload.update(filtros)
        
        try:
            endpoint = f"{API_BASE}/painelUsuario/recuperarEtiquetasQuantitativoProcessoTarefaPendente/{nome_tarefa_encoded}/{str(apenas_favoritas).lower()}"
            
            resp = self.session.post(
                endpoint,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                etiquetas = [Etiqueta.from_dict(e) for e in data]
                self._log(f"Encontradas {len(etiquetas)} etiquetas")
                return etiquetas
            else:
                self._log(f"Erro ao listar etiquetas: {resp.status_code}", "ERROR")
                
        except Exception as e:
            self._log(f"Erro ao listar etiquetas: {e}", "ERROR")
        
        return []
    
    # ==================== ETIQUETAS (METODOS EXISTENTES) ====================
    
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
    
    # ==================== PROCESSOS ====================
    
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
    
    # ==================== DOWNLOAD DE DOCUMENTOS ====================
    
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
    
    # ==================== AREA DE DOWNLOAD ====================
    
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
    
    def aguardar_downloads_prontos(
        self,
        quantidade_esperada: int,
        tempo_maximo: int = 300,
        intervalo_verificacao: int = 10,
        tempo_minimo_inicial: int = 15
    ) -> List[DownloadDisponivel]:
        """
        Aguarda até que os downloads estejam prontos no servidor.
        
        Args:
            quantidade_esperada: Quantidade de downloads esperados
            tempo_maximo: Tempo máximo de espera em segundos (default: 5 minutos)
            intervalo_verificacao: Intervalo entre verificações em segundos
            tempo_minimo_inicial: Tempo mínimo de espera antes da primeira verificação
        
        Returns:
            Lista de downloads disponíveis
        """
        self._log(f"Aguardando {quantidade_esperada} downloads ficarem prontos...")
        self._log(f"Tempo máximo de espera: {tempo_maximo}s, verificação a cada {intervalo_verificacao}s")
        
        # Espera mínima inicial para dar tempo do servidor processar
        self._log(f"Aguardando {tempo_minimo_inicial}s inicial...")
        time.sleep(tempo_minimo_inicial)
        
        tempo_decorrido = tempo_minimo_inicial
        downloads_anteriores = 0
        tempo_sem_novos = 0
        
        while tempo_decorrido < tempo_maximo:
            downloads = self.listar_downloads_disponiveis()
            quantidade_atual = len(downloads)
            
            self._log(f"Downloads disponíveis: {quantidade_atual}/{quantidade_esperada} (tempo: {tempo_decorrido}s)")
            
            # Se já tem todos os downloads esperados, retorna
            if quantidade_atual >= quantidade_esperada:
                self._log(f"Todos os {quantidade_esperada} downloads estão prontos!")
                return downloads
            
            # Verifica se houve progresso
            if quantidade_atual > downloads_anteriores:
                self._log(f"Novos downloads detectados: +{quantidade_atual - downloads_anteriores}")
                tempo_sem_novos = 0
            else:
                tempo_sem_novos += intervalo_verificacao
            
            downloads_anteriores = quantidade_atual
            
            # Se ficou muito tempo sem novos downloads e já tem alguns, pode ser que o servidor não vá gerar mais
            if tempo_sem_novos >= 60 and quantidade_atual > 0:
                self._log(f"Sem novos downloads há {tempo_sem_novos}s. Continuando com {quantidade_atual} downloads.", "WARN")
                return downloads
            
            # Aguarda antes da próxima verificação
            time.sleep(intervalo_verificacao)
            tempo_decorrido += intervalo_verificacao
        
        self._log(f"Tempo máximo atingido. Downloads disponíveis: {len(downloads)}/{quantidade_esperada}", "WARN")
        return self.listar_downloads_disponiveis()
    
    #  FLUXO COMPLETO - TAREFAS 
    
    def processar_tarefa(
        self,
        nome_tarefa: str,
        nome_perfil: str = None,
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 30,
        limite_processos: int = None,
        filtros: Dict = None
    ) -> Dict[str, Any]:
        """
        Processa todos os processos de uma tarefa.
        
        Args:
            nome_tarefa: Nome da tarefa (ex: "Minutar ato de julgamento")
            nome_perfil: Nome do perfil a selecionar (opcional)
            tipo_documento: Tipo de documento para download
            aguardar_download: Se deve aguardar e baixar automaticamente
            tempo_espera: Tempo de espera em segundos para processamento
            limite_processos: Limite de processos a processar (None = todos)
            filtros: Filtros adicionais para a busca de processos
        
        Returns:
            Relatorio do processamento
        """
        relatorio = {
            "tarefa": nome_tarefa,
            "perfil": nome_perfil,
            "tipo_documento": tipo_documento,
            "data_inicio": datetime.now().isoformat(),
            "processos_encontrados": 0,
            "processos_processados": 0,
            "downloads_solicitados": 0,
            "downloads_concluidos": 0,
            "erros": [],
            "arquivos_baixados": [],
            "processos_detalhes": []
        }
        
        
        self._log(f"PROCESSANDO TAREFA: {nome_tarefa}")
        
        
        # Seleciona perfil se especificado 
        perfil_alterado = False
        if nome_perfil:
            if not self.select_profile(nome_perfil):
                relatorio["erros"].append(f"Falha ao selecionar perfil '{nome_perfil}'")
                self._log("Falha ao selecionar perfil", "ERROR")
                return relatorio
            perfil_alterado = True
            self._delay()
        
        # Busca tarefa pelo nome (força atualização se mudou de perfil)
        tarefa = self.buscar_tarefa_por_nome(nome_tarefa, forcar_atualizacao=perfil_alterado)
        if not tarefa:
            relatorio["erros"].append(f"Tarefa '{nome_tarefa}' nao encontrada")
            self._log("Tarefa nao encontrada", "ERROR")
            return relatorio
        
        self._log(f"Tarefa encontrada: ID={tarefa.id}, Pendentes={tarefa.quantidade_pendente}")
        self._delay()
        
        # Lista processos da tarefa
        processos = self.listar_todos_processos_tarefa(
            nome_tarefa=tarefa.nome,
            filtros=filtros,
            apenas_favoritas=tarefa.favorita
        )
        
        relatorio["processos_encontrados"] = len(processos)
        
        if not processos:
            self._log("Nenhum processo encontrado na tarefa")
            return relatorio
        
        # Aplica limite se especificado
        if limite_processos:
            processos = processos[:limite_processos]
            self._log(f"Limitando a {limite_processos} processos")
        
        # Processa cada processo
        for i, processo in enumerate(processos, 1):
            self._log(f"-" * 40)
            self._log(f"Processo {i}/{len(processos)} - {processo.numero_processo}")
            self._log(f"  Polo Ativo: {processo.polo_ativo[:50]}..." if len(processo.polo_ativo) > 50 else f"  Polo Ativo: {processo.polo_ativo}")
            self._log(f"  Polo Passivo: {processo.polo_passivo[:50]}..." if len(processo.polo_passivo) > 50 else f"  Polo Passivo: {processo.polo_passivo}")
            
            processo_info = {
                "numero": processo.numero_processo,
                "id": processo.id_processo,
                "status": "pendente"
            }
            
            try:
                html = self.abrir_processo(processo.id_processo)
                if not html:
                    processo_info["status"] = "erro_abrir"
                    relatorio["erros"].append(f"Falha ao abrir processo {processo.numero_processo}")
                    relatorio["processos_detalhes"].append(processo_info)
                    continue
                
                self._delay()
                
                if self.solicitar_download(processo.id_processo, tipo_documento, html):
                    relatorio["downloads_solicitados"] += 1
                    processo_info["status"] = "download_solicitado"
                else:
                    processo_info["status"] = "erro_download"
                    relatorio["erros"].append(f"Falha ao solicitar download: {processo.numero_processo}")
                
                relatorio["processos_processados"] += 1
                relatorio["processos_detalhes"].append(processo_info)
                
                self._delay(2, 4)
                
            except Exception as e:
                processo_info["status"] = "erro"
                processo_info["erro"] = str(e)
                relatorio["erros"].append(f"Erro no processo {processo.numero_processo}: {str(e)}")
                relatorio["processos_detalhes"].append(processo_info)
                self._log(f"Erro: {e}", "ERROR")
        
        # Aguarda processamento e baixa
        if aguardar_download and relatorio["downloads_solicitados"] > 0:
            # Usa o método inteligente de aguardar downloads
            downloads_prontos = self.aguardar_downloads_prontos(
                quantidade_esperada=relatorio["downloads_solicitados"],
                tempo_maximo=tempo_espera * 10,  # 10x o tempo base como máximo
                intervalo_verificacao=10,
                tempo_minimo_inicial=min(15, tempo_espera)
            )
            
            self._log("Baixando arquivos da area de download...")
            arquivos_baixados = []
            for download in downloads_prontos:
                self._delay()
                arquivo = self.baixar_arquivo(download)
                if arquivo:
                    arquivos_baixados.append(arquivo)
            
            relatorio["arquivos_baixados"] = [str(a) for a in arquivos_baixados]
            relatorio["downloads_concluidos"] = len(arquivos_baixados)
            self._log(f"Total de arquivos baixados: {len(arquivos_baixados)}")
        
        relatorio["data_fim"] = datetime.now().isoformat()
        
        # Salva relatorio
        nome_arquivo = f"relatorio_tarefa_{nome_tarefa.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self._save_json(relatorio, nome_arquivo)
        
        
        self._log("RESUMO DO PROCESSAMENTO")
        
        self._log(f"Processos encontrados: {relatorio['processos_encontrados']}")
        self._log(f"Processos processados: {relatorio['processos_processados']}")
        self._log(f"Downloads solicitados: {relatorio['downloads_solicitados']}")
        self._log(f"Downloads concluidos: {relatorio['downloads_concluidos']}")
        self._log(f"Erros: {len(relatorio['erros'])}")
        
        return relatorio
    
    def processar_multiplas_tarefas(
        self,
        nomes_tarefas: List[str],
        nome_perfil: str = None,
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 30,
        limite_processos_por_tarefa: int = None
    ) -> Dict[str, Any]:
        """
        Processa multiplas tarefas em sequencia.
        
        Args:
            nomes_tarefas: Lista de nomes de tarefas
            nome_perfil: Nome do perfil a selecionar
            tipo_documento: Tipo de documento para download
            aguardar_download: Se deve aguardar e baixar
            tempo_espera: Tempo de espera para downloads
            limite_processos_por_tarefa: Limite de processos por tarefa
        
        Returns:
            Relatorio consolidado
        """
        relatorio_consolidado = {
            "tarefas": nomes_tarefas,
            "perfil": nome_perfil,
            "data_inicio": datetime.now().isoformat(),
            "total_processos_encontrados": 0,
            "total_processos_processados": 0,
            "total_downloads_solicitados": 0,
            "total_downloads_concluidos": 0,
            "total_erros": 0,
            "relatorios_tarefas": []
        }
        
        # Seleciona perfil uma vez
        if nome_perfil:
            if not self.select_profile(nome_perfil):
                relatorio_consolidado["erro_geral"] = f"Falha ao selecionar perfil '{nome_perfil}'"
                return relatorio_consolidado
            self._delay()
        
        for nome_tarefa in nomes_tarefas:
            relatorio = self.processar_tarefa(
                nome_tarefa=nome_tarefa,
                nome_perfil=None,  # Ja selecionou acima
                tipo_documento=tipo_documento,
                aguardar_download=aguardar_download,
                tempo_espera=tempo_espera,
                limite_processos=limite_processos_por_tarefa
            )
            
            relatorio_consolidado["relatorios_tarefas"].append(relatorio)
            relatorio_consolidado["total_processos_encontrados"] += relatorio["processos_encontrados"]
            relatorio_consolidado["total_processos_processados"] += relatorio["processos_processados"]
            relatorio_consolidado["total_downloads_solicitados"] += relatorio["downloads_solicitados"]
            relatorio_consolidado["total_downloads_concluidos"] += relatorio["downloads_concluidos"]
            relatorio_consolidado["total_erros"] += len(relatorio["erros"])
            
            self._delay(3, 5)
        
        relatorio_consolidado["data_fim"] = datetime.now().isoformat()
        
        nome_arquivo = f"relatorio_multiplas_tarefas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self._save_json(relatorio_consolidado, nome_arquivo)
        
        return relatorio_consolidado
    
    def close(self):
        """Fecha a sessao."""
        self.session.close()
        self._log("Sessao encerrada")


def main():
    """Funcao principal de exemplo."""
    
    pje = PJEAutomacaoTarefas(
        download_dir="./downloads",
        log_dir="./.logs",
        session_dir="./.session"
    )
    
    try:
        # Login
        if not pje.login():
            print("Falha no login")
            return
        
        # Listar todas as tarefas
        print("\n" + "=" * 60)
        print("TAREFAS DISPONIVEIS")
        print("=" * 60)
        
        tarefas_favoritas = pje.listar_tarefas_favoritas()
        print(f"\nTarefas Favoritas (Minhas Tarefas): {len(tarefas_favoritas)}")
        for t in tarefas_favoritas:
            print(f"  - {t.nome}: {t.quantidade_pendente} processos")
        
        tarefas = pje.listar_tarefas()
        print(f"\nTodas as Tarefas: {len(tarefas)}")
        for t in tarefas:
            print(f"  - {t.nome}: {t.quantidade_pendente} processos")
        
        # Exemplo: Processar uma tarefa especifica
        # Descomente para executar
        
        # relatorio = pje.processar_tarefa(
        #     nome_tarefa="Minutar ato de julgamento",
        #     nome_perfil="V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL",
        #     tipo_documento="Selecione",
        #     aguardar_download=True,
        #     tempo_espera=30,
        #     limite_processos=5  # Limita a 5 processos para teste
        # )
        
        relatorio = pje.processar_tarefa(
            nome_tarefa="Minutar sentença homologatória",
            nome_perfil="V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL / Assessoria / Assessor",
            tipo_documento="Selecione",
            aguardar_download=True,
            tempo_espera=30
        )
        
        
    finally:
        pje.close()


if __name__ == "__main__":
    main()