"""
Servico de gerenciamento de perfis do usuario.
"""

import re
from typing import List, Optional

from ..config import BASE_URL
from ..models import Perfil
from ..utils import Logger, delay, extrair_viewstate
from ..core.auth import AuthService


class ProfileService:
    """
    Gerencia selecao de perfis/papeis do usuario no PJE.
    """
    
    def __init__(self, auth: AuthService, debug: bool = False):
        self.auth = auth
        self.logger = Logger(debug)
        self.perfis: List[Perfil] = []
    
    def _extrair_perfis_html(self, html: str) -> List[Perfil]:
        """Extrai lista de perfis do HTML da pagina."""
        perfis = []
        
        # Tenta diferentes padroes de regex
        patterns = [
            r'dtPerfil:(\d+):j_id70[^>]*>([^<]+)</a>',
            r'<a[^>]*onclick="[^"]*dtPerfil:(\d+)[^"]*"[^>]*>([^<]+)</a>'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                break
        
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
    
    def listar(self) -> List[Perfil]:
        """Lista perfis disponiveis para o usuario."""
        if not self.auth.ensure_logged_in():
            return []
        
        try:
            resp = self.auth.session.get(
                f"{BASE_URL}/pje/ng2/dev.seam",
                timeout=self.auth.timeout
            )
            
            if resp.status_code == 200:
                self.perfis = self._extrair_perfis_html(resp.text)
                self.logger.info(f"Encontrados {len(self.perfis)} perfis")
                return self.perfis
                
        except Exception as e:
            self.logger.error(f"Erro ao listar perfis: {e}")
        
        return []
    
    def selecionar_por_indice(self, index: int) -> bool:
        """Seleciona um perfil pelo indice."""
        if not self.auth.ensure_logged_in():
            return False
        
        try:
            resp = self.auth.session.get(
                f"{BASE_URL}/pje/ng2/dev.seam",
                timeout=self.auth.timeout
            )
            
            viewstate = extrair_viewstate(resp.text) or "j_id1"
            
            delay()
            
            form_data = {
                "papeisUsuarioForm": "papeisUsuarioForm",
                "papeisUsuarioForm:j_id60": "",
                "papeisUsuarioForm:j_id72": "papeisUsuarioForm:j_id72",
                "javax.faces.ViewState": viewstate,
                f"papeisUsuarioForm:dtPerfil:{index}:j_id70": f"papeisUsuarioForm:dtPerfil:{index}:j_id70"
            }
            
            self.auth.session.post(
                f"{BASE_URL}/pje/ng2/dev.seam",
                data=form_data,
                allow_redirects=True,
                timeout=self.auth.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": BASE_URL,
                }
            )
            
            delay()
            
            if self.auth.verificar_sessao():
                self.logger.info(f"Perfil selecionado: {self.auth.usuario.nome}")
                self.logger.info(f"Localizacao: {self.auth.usuario.id_usuario_localizacao}")
                self.auth.session_manager.save(self.auth.session)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Erro ao selecionar perfil: {e}")
            return False
    
    def selecionar_por_nome(self, nome: str) -> bool:
        """Seleciona um perfil pelo nome (busca parcial)."""
        if not self.perfis:
            self.listar()
        
        nome_lower = nome.lower()
        
        for perfil in self.perfis:
            if nome_lower in perfil.nome_completo.lower():
                self.logger.info(f"Perfil encontrado: {perfil.nome_completo}")
                return self.selecionar_por_indice(perfil.index)
        
        self.logger.error(f"Perfil '{nome}' nao encontrado")
        return False
