"""
Serviço de autenticação do PJE.
"""

import os
import re
from typing import Optional, List

from ..config import BASE_URL, SSO_URL, API_BASE
from ..core import SessionManager, PJEHttpClient
from ..models import Usuario, Perfil
from ..utils import delay, get_logger, buscar_texto_similar


class AuthService:
    """Serviço de autenticação e gerenciamento de perfil."""
    
    def __init__(self, http_client: PJEHttpClient, session_manager: SessionManager):
        self.client = http_client
        self.session_manager = session_manager
        self.logger = get_logger()
        self.perfis_disponiveis: List[Perfil] = []
    
    @property
    def usuario(self) -> Optional[Usuario]:
        return self.client.usuario
    
    @usuario.setter
    def usuario(self, value: Usuario):
        self.client.usuario = value
    
    def verificar_sessao_ativa(self) -> bool:
        """Verifica se há sessão ativa no servidor."""
        try:
            resp = self.client.session.get(
                f"{API_BASE}/usuario/currentUser",
                timeout=self.client.timeout
            )
            if resp.status_code == 200:
                self.usuario = Usuario.from_dict(resp.json())
                return True
        except Exception:
            pass
        return False
    
    def restaurar_sessao(self) -> bool:
        """Tenta restaurar sessão salva."""
        if not self.session_manager.is_session_valid():
            return False
        if not self.session_manager.load_session(self.client.session):
            return False
        if self.verificar_sessao_ativa():
            self.logger.info(f"Sessão restaurada: {self.usuario.nome}")
            return True
        return False
    
    def read_env(self) -> tuple:
        username = None
        password = None
        
        from pathlib import Path
        env_path = Path.cwd() / ".env"
        
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if key in ('USER', 'PJE_USER') and not username:
                            username = value
                        elif key in ('PASSWORD', 'PJE_PASSWORD') and not password:
                            password = value
        
        return username, password
    
    def login(self, username: str = None, password: str = None, force: bool = False) -> bool:
        """Realiza login no PJE via SSO."""
        if not username or not password:
            env_user = os.getenv("PJE_USER") or os.getenv("USER")
            env_pass = os.getenv("PJE_PASSWORD") or os.getenv("PASSWORD")
            
            if not env_user or not env_pass:
                env_user, env_pass = self.read_env()
            
            username = username or env_user
            password = password or env_pass
        
        if not username or not password:
            self.logger.error("Credenciais não fornecidas")
            return False
        
        if not force:
            if self.verificar_sessao_ativa():
                self.logger.info(f"Já logado: {self.usuario.nome}")
                return True
            if self.restaurar_sessao():
                return True
        else:
            self.session_manager.clear_session()
        
        self.logger.info(f"Iniciando login: {username}...")
        
        try:
            # Limpa sessão antiga
            self.client.session.cookies.clear()
            
            resp = self.client.session.get(
                f"{BASE_URL}/pje/login.seam",
                allow_redirects=True,
                timeout=self.client.timeout
            )
            
            if "sso.cloud.pje.jus.br" not in resp.url:
                self.logger.error("Não redirecionou para SSO")
                return False
            
            action_match = re.search(r'action="([^"]*)"', resp.text)
            if not action_match:
                self.logger.error("URL de autenticação não encontrada")
                return False
            
            auth_url = action_match.group(1).replace("&amp;", "&")
            if not auth_url.startswith("http"):
                auth_url = f"{SSO_URL}{auth_url}"
            
            delay(0.5, 1)
            
            resp = self.client.session.post(
                auth_url,
                data={
                    "username": username,
                    "password": password,
                    "credentialId": "",
                },
                allow_redirects=True,
                timeout=self.client.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": SSO_URL,
                    "Referer": auth_url,
                }
            )
            
            delay(0.5, 1)
            
            if self.verificar_sessao_ativa():
                self.logger.success(f"Login OK: {self.usuario.nome}")
                self.session_manager.save_session(self.client.session)
                return True
            else:
                self.logger.error("Falha na verificação pós-login")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro no login: {e}")
            return False
    
    def ensure_logged_in(self) -> bool:
        """Garante que está logado."""
        if self.verificar_sessao_ativa():
            return True
        return self.login()
    
    def limpar_sessao(self):
        """Limpa sessão salva."""
        self.session_manager.clear_session()
        self.client.session.cookies.clear()
    
    # PERFIL
    def _extrair_perfis_da_pagina(self, html: str) -> List[Perfil]:
        """Extrai perfis do HTML."""
        perfis = []
        pattern = r'dtPerfil:(\d+):j_id70[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.IGNORECASE)
        
        if not matches:
            pattern = r'<a[^>]*onclick="[^"]*dtPerfil:(\d+)[^"]*"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html, re.IGNORECASE)
        
        for index_str, nome in matches:
            partes = nome.strip().split(" / ")
            perfis.append(Perfil(
                index=int(index_str),
                nome=partes[0] if partes else nome.strip(),
                orgao=partes[1] if len(partes) > 1 else "",
                cargo=partes[2] if len(partes) > 2 else ""
            ))
        return perfis
    
    def listar_perfis(self) -> List[Perfil]:
        """Lista perfis disponíveis."""
        if not self.ensure_logged_in():
            return []
        try:
            resp = self.client.session.get(f"{BASE_URL}/pje/ng2/dev.seam", timeout=self.client.timeout)
            if resp.status_code == 200:
                self.perfis_disponiveis = self._extrair_perfis_da_pagina(resp.text)
                self.logger.info(f"Encontrados {len(self.perfis_disponiveis)} perfis")
                return self.perfis_disponiveis
        except Exception as e:
            self.logger.error(f"Erro ao listar perfis: {e}")
        return []
    
    def select_profile_by_index(self, profile_index: int) -> bool:
        """Seleciona perfil pelo índice."""
        if not self.ensure_logged_in():
            return False
        try:
            resp = self.client.session.get(f"{BASE_URL}/pje/ng2/dev.seam", timeout=self.client.timeout)
            
            viewstate_match = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]*)"', resp.text)
            viewstate = viewstate_match.group(1) if viewstate_match else "j_id1"
            
            delay()
            
            form_data = {
                "papeisUsuarioForm": "papeisUsuarioForm",
                "papeisUsuarioForm:j_id60": "",
                "papeisUsuarioForm:j_id72": "papeisUsuarioForm:j_id72",
                "javax.faces.ViewState": viewstate,
                f"papeisUsuarioForm:dtPerfil:{profile_index}:j_id70": f"papeisUsuarioForm:dtPerfil:{profile_index}:j_id70"
            }
            
            self.client.session.post(
                f"{BASE_URL}/pje/ng2/dev.seam",
                data=form_data,
                allow_redirects=True,
                timeout=self.client.timeout,
                headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": BASE_URL}
            )
            
            delay()
            
            if self.verificar_sessao_ativa():
                self.logger.success(f"Perfil selecionado: {self.usuario.nome}")
                self.session_manager.save_session(self.client.session)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Erro ao selecionar perfil: {e}")
            return False
    
    def select_profile(self, nome_perfil: str) -> bool:
        """Seleciona perfil pelo nome."""
        if not self.perfis_disponiveis:
            self.listar_perfis()
        
        nomes = [p.nome_completo for p in self.perfis_disponiveis]
        idx = buscar_texto_similar(nome_perfil, nomes, threshold=0.4)
        
        if idx is not None:
            perfil = self.perfis_disponiveis[idx]
            self.logger.info(f"Perfil encontrado: {perfil.nome_completo}")
            return self.select_profile_by_index(perfil.index)
        
        self.logger.error(f"Perfil '{nome_perfil}' não encontrado")
        return False
