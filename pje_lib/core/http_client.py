"""
Cliente HTTP base para comunicação com o PJE.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Optional

from ..config import API_BASE, DEFAULT_HEADERS, DEFAULT_TIMEOUT
from ..models import Usuario


def sessao_caiu(resp: requests.Response) -> bool:
    """True se a resposta final aterrissou na tela de login (sessão expirou).

    O PJE responde HTTP 200 com o HTML do Keycloak nesses casos, então
    status_code não serve — a URL final é o sinal confiável.
    """
    return "sso.cloud.pje.jus.br" in resp.url or "/login.seam" in resp.url


class PJEHttpClient:
    """Cliente HTTP configurado para o PJE."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        # Backoff exponencial para instabilidade transiente (429 comprovado
        # empiricamente na infra PJe/CNJ). Respeita Retry-After.
        # POST idempotente aqui: re-solicitar um download só regenera o mesmo PDF.
        retry = Retry(
            total=5,
            backoff_factor=2,  # 2s, 4s, 8s, 16s, 32s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.usuario: Optional[Usuario] = None
    
    def get_api_headers(self) -> Dict[str, str]:
        """Headers para API REST do PJE."""
        headers = {
            "Content-Type": "application/json",
            "X-pje-legacy-app": "pje-tjba-1g",
        }
        
        cookies_str = "; ".join([f"{c.name}={c.value}" for c in self.session.cookies])
        if cookies_str:
            headers["X-pje-cookies"] = cookies_str
        
        if self.usuario and self.usuario.id_usuario_localizacao:
            headers["X-pje-usuario-localizacao"] = str(self.usuario.id_usuario_localizacao)
        
        return headers
    
    def get(self, url: str, params: Optional[Dict] = None, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.get(url, params=params, **kwargs)
    
    def post(self, url: str, data: Optional[Dict] = None, 
             json: Optional[Dict] = None, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.post(url, data=data, json=json, **kwargs)
    
    def api_get(self, endpoint: str, params: Optional[Dict] = None) -> requests.Response:
        return self.get(f"{API_BASE}/{endpoint}", params=params, headers=self.get_api_headers())
    
    def api_post(self, endpoint: str, json_data: Optional[Dict] = None) -> requests.Response:
        return self.post(f"{API_BASE}/{endpoint}", json=json_data, headers=self.get_api_headers())
    
    def close(self):
        self.session.close()
