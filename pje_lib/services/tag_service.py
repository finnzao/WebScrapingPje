"""
Serviço de gerenciamento de etiquetas.
"""

from typing import List, Optional

from ..core import PJEHttpClient
from ..models import Etiqueta, Processo
from ..utils import delay, get_logger


class TagService:
    """Serviço para etiquetas e processos por etiqueta."""
    
    def __init__(self, http_client: PJEHttpClient):
        self.client = http_client
        self.logger = get_logger()
    
    def buscar_etiquetas(self, busca: str = "", page: int = 0, max_results: int = 30) -> List[Etiqueta]:
        """Busca etiquetas pelo nome."""
        try:
            resp = self.client.api_post(
                "painelUsuario/etiquetas",
                {"page": page, "maxResults": max_results, "tagsString": busca}
            )
            if resp.status_code == 200:
                data = resp.json()
                etiquetas = [Etiqueta.from_dict(e) for e in data.get("entities", [])]
                self.logger.info(f"Encontradas {len(etiquetas)} etiquetas")
                return etiquetas
        except Exception as e:
            self.logger.error(f"Erro ao buscar etiquetas: {e}")
        return []
    
    def buscar_etiqueta_por_nome(self, nome: str) -> Optional[Etiqueta]:
        """Busca etiqueta específica pelo nome."""
        etiquetas = self.buscar_etiquetas(nome)
        for et in etiquetas:
            if et.nome.lower() == nome.lower():
                return et
        return etiquetas[0] if etiquetas else None
    
    def listar_processos_etiqueta(self, id_etiqueta: int, limit: int = 100) -> List[Processo]:
        """Lista processos de uma etiqueta."""
        try:
            # Obtém total
            resp_total = self.client.api_get(f"painelUsuario/etiquetas/{id_etiqueta}/processos/total")
            total = int(resp_total.text) if resp_total.status_code == 200 else 0
            self.logger.info(f"Total de processos: {total}")
            
            delay()
            
            # Obtém processos
            resp = self.client.api_get(
                f"painelUsuario/etiquetas/{id_etiqueta}/processos",
                params={"limit": limit}
            )
            if resp.status_code == 200:
                return [Processo.from_dict(p) for p in resp.json()]
        except Exception as e:
            self.logger.error(f"Erro ao listar processos: {e}")
        return []
