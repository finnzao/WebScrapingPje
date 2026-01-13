"""
Serviço de download de processos.
"""

import re
import time
import requests
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple, Any

from ..config import BASE_URL, TIPO_DOCUMENTO_VALUES
from ..core import PJEHttpClient
from ..models import DownloadDisponivel, DiagnosticoDownload
from ..utils import delay, extrair_viewstate, current_month_year, get_logger


class DownloadService:
    """Serviço para download de processos."""
    
    def __init__(self, http_client: PJEHttpClient, download_dir: Optional[Path] = None):
        self.client = http_client
        self.logger = get_logger()
        self.download_dir = download_dir or Path.home() / "Downloads" / "pje_downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.diagnosticos: List[DiagnosticoDownload] = []
        self.downloads_solicitados: Set[str] = set()
    
    def limpar_diagnosticos(self):
        self.diagnosticos.clear()
        self.downloads_solicitados.clear()
    
    def gerar_chave_acesso(self, id_processo: int) -> Optional[str]:
        """Gera chave de acesso para processo."""
        try:
            resp = self.client.api_get(f"painelUsuario/gerarChaveAcessoProcesso/{id_processo}")
            if resp.status_code == 200:
                return resp.text.strip().strip('"')
        except Exception as e:
            self.logger.error(f"Erro ao gerar chave: {e}")
        return None
    
    def abrir_processo(self, id_processo: int, ca: str = None) -> Optional[str]:
        """Abre página de autos digitais."""
        if not ca:
            ca = self.gerar_chave_acesso(id_processo)
            if not ca:
                return None
        try:
            resp = self.client.get(
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam",
                params={"idProcesso": id_processo, "ca": ca}
            )
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            self.logger.error(f"Erro ao abrir processo: {e}")
        return None
    
    def _identificar_botao_download(self, html: str) -> Optional[str]:
        """Identifica ID do botão de download dinamicamente."""
        patterns = [
            re.compile(r'<input[^>]*id="(navbar:j_id\d+)"[^>]*onclick="iniciarTemporizadorDownload\(\)[^"]*"[^>]*value="Download"[^>]*>', re.IGNORECASE | re.DOTALL),
            re.compile(r'<input[^>]*value="Download"[^>]*id="(navbar:j_id\d+)"[^>]*onclick="iniciarTemporizadorDownload\(\)[^"]*"[^>]*>', re.IGNORECASE | re.DOTALL),
            re.compile(r'id="navbar:botoesDownload"[^>]*>.*?<input[^>]*id="(navbar:j_id\d+)"[^>]*value="Download"', re.IGNORECASE | re.DOTALL),
        ]
        
        for pattern in patterns:
            matches = pattern.findall(html)
            if matches:
                return matches[0]
        
        # Fallback
        for id_botao in ['navbar:j_id280', 'navbar:j_id278', 'navbar:j_id271', 'navbar:j_id270', 'navbar:j_id267']:
            if id_botao in html:
                return id_botao
        return None
    
    def _extrair_url_download_direto(self, html: str) -> Optional[str]:
        """Extrai URL de download direto do S3."""
        pattern = r'(https://[^"\'<>\s]*\.s3\.[^"\'<>\s]*\.amazonaws\.com/[^"\'<>\s]*-processo\.pdf[^"\'<>\s]*)'
        matches = re.findall(pattern, html)
        return matches[0].replace('&amp;', '&') if matches else None
    
    def _baixar_arquivo_direto(self, url: str, numero_processo: str, diretorio: Path) -> Optional[Path]:
        """Baixa arquivo direto do S3."""
        try:
            match = re.search(r'/([^/]+-processo\.pdf)', url)
            nome = match.group(1) if match else f"{numero_processo}-processo.pdf"
            
            resp = requests.get(url, stream=True, timeout=120)
            if resp.status_code == 200:
                diretorio.mkdir(parents=True, exist_ok=True)
                filepath = diretorio / nome
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                self.logger.success(f"Baixado: {filepath}")
                return filepath
        except Exception as e:
            self.logger.error(f"Erro download direto: {e}")
        return None
    
    def solicitar_download(
        self, id_processo: int, numero_processo: str,
        tipo_documento: str = "Selecione", html_processo: str = None,
        diretorio_download: Path = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Solicita download de processo."""
        detalhes: Dict[str, Any] = {"id_processo": id_processo, "numero_processo": numero_processo}
        
        # Chave de acesso
        ca = self.gerar_chave_acesso(id_processo)
        if not ca:
            return False, detalhes
        
        # Abrir processo
        if not html_processo:
            delay()
            html_processo = self.abrir_processo(id_processo, ca)
            if not html_processo:
                return False, detalhes
        
        # ViewState
        viewstate = extrair_viewstate(html_processo)
        if not viewstate:
            return False, detalhes
        
        # Botão
        botao_id = self._identificar_botao_download(html_processo)
        if not botao_id:
            return False, detalhes
        
        delay()
        
        # Formulário
        form_data = {
            "AJAXREQUEST": "_viewRoot",
            "navbar:cbTipoDocumento": TIPO_DOCUMENTO_VALUES.get(tipo_documento, "0"),
            "navbar:idDe": "", "navbar:idAte": "",
            "navbar:dtInicioInputDate": "", "navbar:dtInicioInputCurrentDate": current_month_year(),
            "navbar:dtFimInputDate": "", "navbar:dtFimInputCurrentDate": current_month_year(),
            "navbar:cbCronologia": "DESC", "": "on", "navbar": "navbar",
            "autoScroll": "", "javax.faces.ViewState": viewstate,
            botao_id: botao_id, "AJAX:EVENTS_COUNT": "1",
        }
        
        try:
            resp = self.client.session.post(
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam",
                data=form_data, timeout=self.client.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest", "Accept": "*/*",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam?idProcesso={id_processo}&ca={ca}"
                }
            )
            
            if resp.status_code != 200:
                return False, detalhes
            
            texto = resp.text
            
            # Download direto (poucas peças)
            if "está sendo gerado" in texto.lower() or "aguarde" in texto.lower():
                url_direta = self._extrair_url_download_direto(texto)
                if url_direta and diretorio_download:
                    arquivo = self._baixar_arquivo_direto(url_direta, numero_processo, diretorio_download)
                    if arquivo:
                        detalhes["tipo_download"] = "direto"
                        detalhes["arquivo_baixado"] = str(arquivo)
                        self.downloads_solicitados.add(numero_processo)
                        return True, detalhes
            
            # Área de download (muitas peças)
            if "será disponibilizado" in texto.lower() or "área de download" in texto.lower():
                detalhes["tipo_download"] = "area_download"
                self.downloads_solicitados.add(numero_processo)
                return True, detalhes
            
            # Outros padrões de sucesso
            if any(p in texto.lower() for p in ["download", "documento solicitado"]):
                detalhes["tipo_download"] = "area_download"
                self.downloads_solicitados.add(numero_processo)
                return True, detalhes
            
            return False, detalhes
            
        except Exception as e:
            self.logger.error(f"Erro ao solicitar: {e}")
            return False, detalhes
    
    # ÁREA DE DOWNLOADS 
    
    def listar_downloads_disponiveis(self) -> List[DownloadDisponivel]:
        """Lista downloads na área de downloads."""
        if not self.client.usuario:
            return []
        try:
            resp = self.client.api_get(
                "pjedocs-api/v1/downloadService/recuperarDownloadsDisponiveis",
                params={"idUsuario": self.client.usuario.id_usuario, "sistemaOrigem": "PRIMEIRA_INSTANCIA"}
            )
            if resp.status_code == 200:
                return [DownloadDisponivel.from_dict(d) for d in resp.json().get("downloadsDisponiveis", [])]
        except Exception as e:
            self.logger.error(f"Erro ao listar downloads: {e}")
        return []
    
    def obter_url_download(self, hash_download: str) -> Optional[str]:
        """Obtém URL do S3."""
        try:
            resp = self.client.api_get("pjedocs-api/v2/repositorio/gerar-url-download", params={"hashDownload": hash_download})
            if resp.status_code == 200:
                return resp.text.strip().strip('"')
        except Exception:
            pass
        return None
    
    def baixar_arquivo(self, download: DownloadDisponivel, diretorio: Path = None) -> Optional[Path]:
        """Baixa arquivo da área de downloads."""
        diretorio = diretorio or self.download_dir
        diretorio.mkdir(parents=True, exist_ok=True)
        
        url = self.obter_url_download(download.hash_download)
        if not url:
            return None
        
        try:
            resp = requests.get(url, stream=True, timeout=120)
            if resp.status_code == 200:
                filepath = diretorio / download.nome_arquivo
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                self.logger.success(f"Baixado: {filepath}")
                return filepath
        except Exception as e:
            self.logger.error(f"Erro ao baixar: {e}")
        return None
    
    def aguardar_downloads(self, processos: List[str], tempo_maximo: int = 300, intervalo: int = 15) -> List[DownloadDisponivel]:
        """Aguarda downloads ficarem disponíveis."""
        self.logger.info(f"Aguardando {len(processos)} downloads...")
        time.sleep(15)
        
        inicio = time.time()
        encontrados: Set[str] = set()
        downloads_encontrados: List[DownloadDisponivel] = []
        
        while (time.time() - inicio) < tempo_maximo:
            downloads = self.listar_downloads_disponiveis()
            
            for download in downloads:
                for proc in download.get_numeros_processos():
                    if proc in processos and proc not in encontrados:
                        encontrados.add(proc)
                        if download not in downloads_encontrados:
                            downloads_encontrados.append(download)
            
            self.logger.info(f"Encontrados: {len(encontrados)}/{len(processos)}")
            
            if len(encontrados) >= len(processos):
                return downloads_encontrados
            
            time.sleep(intervalo)
        
        return downloads_encontrados
