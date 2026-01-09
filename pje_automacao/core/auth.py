"""
Servico de autenticacao no PJE via SSO Keycloak.
"""

import os
import re
import json
import requests
from typing import Optional

from ..config import BASE_URL, SSO_URL, API_BASE, DEFAULT_HEADERS, DEFAULT_TIMEOUT
from ..models import Usuario
from ..utils import Logger, delay
from .session import SessionManager


class AuthService:
    """
    Gerencia autenticacao no sistema PJE.
    Suporta login via SSO Keycloak e persistencia de sessao.
    """
    
    def __init__(
        self,
        session_dir: str = ".session",
        timeout: int = DEFAULT_TIMEOUT,
        debug: bool = False
    ):
        self.timeout = timeout
        self.logger = Logger(debug)
        self.session_manager = SessionManager(session_dir)
        
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        
        self.usuario: Optional[Usuario] = None
    
    def _get_api_headers(self) -> dict:
        """Retorna headers para requisicoes a API REST do PJe."""
        headers = {
            "Content-Type": "application/json",
            "X-pje-legacy-app": "pje-tjba-1g",
        }
        
        # Monta X-pje-cookies
        cookies_str = "; ".join(f"{c.name}={c.value}" for c in self.session.cookies)
        if cookies_str:
            headers["X-pje-cookies"] = cookies_str
        
        # Adiciona localizacao do usuario
        if self.usuario and self.usuario.id_usuario_localizacao:
            headers["X-pje-usuario-localizacao"] = str(self.usuario.id_usuario_localizacao)
        
        return headers
    
    def verificar_sessao(self) -> bool:
        """Verifica se ha uma sessao ativa no servidor."""
        try:
            self.logger.debug("Verificando sessao ativa...")
            
            resp = self.session.get(
                f"{API_BASE}/usuario/currentUser",
                timeout=self.timeout,
                headers=self._get_api_headers()
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self.logger.debug(f"Usuario: {json.dumps(data, ensure_ascii=False)}")
                self.usuario = Usuario.from_dict(data)
                return True
        except Exception as e:
            self.logger.debug(f"Erro ao verificar sessao: {e}")
        
        return False
    
    def restaurar_sessao(self) -> bool:
        """Tenta restaurar sessao salva anteriormente."""
        if not self.session_manager.is_valid():
            self.logger.info("Sessao salva expirada ou inexistente")
            return False
        
        if not self.session_manager.load(self.session):
            return False
        
        if self.verificar_sessao():
            self.logger.info(f"Sessao restaurada. Usuario: {self.usuario.nome}")
            return True
        
        return False
    
    def login(self, username: str = None, password: str = None, force: bool = False) -> bool:
        """
        Realiza login no PJE.
        
        Args:
            username: CPF do usuario (sem pontos)
            password: Senha
            force: Se True, ignora sessao existente
        """
        username = username or os.getenv("USER")
        password = password or os.getenv("PASSWORD")
        
        if not username or not password:
            self.logger.error("Credenciais nao fornecidas")
            return False
        
        # Tenta sessao existente
        if not force:
            if self.verificar_sessao():
                self.logger.info(f"Ja logado: {self.usuario.nome}")
                return True
            
            if self.restaurar_sessao():
                return True
        else:
            self.session_manager.clear()
        
        self.logger.info(f"Iniciando login para {username}...")
        
        try:
            # Obtem pagina de login
            resp = self.session.get(
                f"{BASE_URL}/pje/login.seam",
                allow_redirects=True,
                timeout=self.timeout
            )
            
            if "sso.cloud.pje.jus.br" not in resp.url:
                self.logger.error("Nao redirecionou para SSO")
                return False
            
            # Extrai URL de autenticacao
            action_match = re.search(r'action="([^"]*authenticate[^"]*)"', resp.text)
            if not action_match:
                self.logger.error("URL de autenticacao nao encontrada")
                return False
            
            auth_url = action_match.group(1).replace("&amp;", "&")
            if not auth_url.startswith("http"):
                auth_url = f"{SSO_URL}{auth_url}"
            
            delay()
            
            # Envia credenciais
            login_data = {
                "username": username,
                "password": password,
                "pjeoffice-code": "",
                "phrase": ""
            }
            
            self.session.post(
                auth_url,
                data=login_data,
                allow_redirects=True,
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": SSO_URL,
                }
            )
            
            delay()
            
            # Verifica se login funcionou
            if self.verificar_sessao():
                self.logger.info(f"Login bem-sucedido! Usuario: {self.usuario.nome}")
                self.session_manager.save(self.session)
                return True
            
            self.logger.error("Falha ao verificar usuario apos login")
            return False
            
        except Exception as e:
            self.logger.error(f"Erro durante login: {e}")
            return False
    
    def ensure_logged_in(self) -> bool:
        """Verifica se esta logado, faz login se necessario."""
        if self.verificar_sessao():
            return True
        return self.login()
    
    def limpar_sessao(self):
        """Limpa sessao salva e cookies."""
        self.logger.info("Limpando sessao...")
        self.session_manager.clear()
        self.session.cookies.clear()
