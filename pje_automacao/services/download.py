"""
Servico de download de processos do PJE.
"""

import re
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from ..config import BASE_URL, API_BASE, TIPO_DOCUMENTO
from ..models import DownloadDisponivel, DiagnosticoDownload
from ..utils import Logger, delay, extrair_viewstate
from ..core.auth import AuthService


class DownloadService:
    """
    Gerencia downloads de processos do PJE.
    Suporta download direto (poucos documentos) e via area de download.
    """
    
    def __init__(self, auth: AuthService, debug: bool = False):
        self.auth = auth
        self.logger = Logger(debug)
        self.diagnosticos: List[DiagnosticoDownload] = []
        self.downloads_solicitados: Set[str] = set()
    
    def limpar(self):
        """Limpa diagnosticos e downloads solicitados."""
        self.diagnosticos.clear()
        self.downloads_solicitados.clear()
    
    def _adicionar_diagnostico(
        self,
        numero_processo: str,
        id_processo: int,
        etapa: str,
        sucesso: bool,
        mensagem: str,
        detalhes: Dict = None
    ):
        """Adiciona registro de diagnostico."""
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
        
        status = "[OK]" if sucesso else "[ERRO]"
        self.logger.info(f"  {status} {etapa}: {mensagem}")
    
    def gerar_chave_acesso(self, id_processo: int) -> Optional[str]:
        """Gera chave de acesso para um processo."""
        try:
            resp = self.auth.session.get(
                f"{API_BASE}/painelUsuario/gerarChaveAcessoProcesso/{id_processo}",
                timeout=self.auth.timeout
            )
            
            if resp.status_code == 200:
                return resp.text.strip().strip('"')
                
        except Exception as e:
            self.logger.error(f"Erro ao gerar chave de acesso: {e}")
        
        return None
    
    def abrir_processo(self, id_processo: int, ca: str = None) -> Optional[str]:
        """Abre pagina de autos digitais e retorna HTML."""
        if not ca:
            ca = self.gerar_chave_acesso(id_processo)
            if not ca:
                return None
        
        try:
            resp = self.auth.session.get(
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam",
                params={"idProcesso": id_processo, "ca": ca},
                timeout=self.auth.timeout
            )
            
            if resp.status_code == 200:
                return resp.text
                
        except Exception as e:
            self.logger.error(f"Erro ao abrir processo: {e}")
        
        return None
    
    def _identificar_botao_download(self, html: str) -> Optional[str]:
        """Identifica ID do botao de download no HTML."""
        patterns = [
            # Botao com onclick e value
            r'<input[^>]*id="(navbar:j_id\d+)"[^>]*'
            r'onclick="iniciarTemporizadorDownload\(\)[^"]*"[^>]*value="Download"[^>]*>',
            # Ordem diferente
            r'<input[^>]*value="Download"[^>]*'
            r'id="(navbar:j_id\d+)"[^>]*onclick="iniciarTemporizadorDownload[^"]*"[^>]*>',
            # Dentro do div botoesDownload
            r'id="navbar:botoesDownload"[^>]*>.*?'
            r'<input[^>]*id="(navbar:j_id\d+)"[^>]*value="Download"',
            # Generico
            r'<input[^>]*id="(navbar:j_id\d+)"[^>]*'
            r'onclick="[^"]*iniciarTemporizadorDownload[^"]*"[^>]*>',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
            if matches:
                self.logger.debug(f"Botao encontrado: {matches[0]}")
                return matches[0]
        
        # Fallback: IDs conhecidos
        for id_botao in ['navbar:j_id280', 'navbar:j_id278', 'navbar:j_id271', 'navbar:j_id267']:
            if id_botao in html:
                self.logger.debug(f"Usando ID conhecido: {id_botao}")
                return id_botao
        
        return None
    
    def _extrair_url_download_direto(self, html: str) -> Optional[str]:
        """Extrai URL de download direto (S3) da resposta."""
        pattern = r'(https://[^"\'<>\s]*\.s3\.[^"\'<>\s]*\.amazonaws\.com/[^"\'<>\s]*-processo\.pdf[^"\'<>\s]*)'
        matches = re.findall(pattern, html)
        
        if matches:
            return matches[0].replace('&amp;', '&')
        
        return None
    
    def _baixar_arquivo_direto(
        self,
        url: str,
        numero_processo: str,
        diretorio: Path
    ) -> Optional[Path]:
        """Baixa arquivo diretamente de URL presigned do S3."""
        try:
            match = re.search(r'/([^/]+-processo\.pdf)', url)
            nome_arquivo = match.group(1) if match else f"{numero_processo}-processo.pdf"
            
            resp = requests.get(url, stream=True, timeout=120)
            
            if resp.status_code == 200:
                diretorio.mkdir(parents=True, exist_ok=True)
                filepath = diretorio / nome_arquivo
                
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                self.logger.info(f"Baixado: {filepath} ({filepath.stat().st_size} bytes)")
                return filepath
                
        except Exception as e:
            self.logger.error(f"Erro ao baixar: {e}")
        
        return None
    
    def solicitar_download(
        self,
        id_processo: int,
        numero_processo: str,
        tipo_documento: str = "Selecione",
        diretorio: Path = None
    ) -> Tuple[bool, Dict]:
        """
        Solicita download de um processo.
        
        Returns:
            Tupla (sucesso, detalhes)
        """
        detalhes = {
            "id_processo": id_processo,
            "numero_processo": numero_processo,
        }
        
        self.logger.info(f"\nSolicitando: {numero_processo} (ID: {id_processo})")
        
        # Etapa 1: Chave de acesso
        ca = self.gerar_chave_acesso(id_processo)
        if not ca:
            self._adicionar_diagnostico(
                numero_processo, id_processo, "chave_acesso",
                False, "Falha ao gerar chave"
            )
            return False, detalhes
        
        self._adicionar_diagnostico(
            numero_processo, id_processo, "chave_acesso",
            True, f"Chave obtida"
        )
        
        # Etapa 2: Abrir processo
        delay()
        html = self.abrir_processo(id_processo, ca)
        
        if not html:
            self._adicionar_diagnostico(
                numero_processo, id_processo, "abrir_processo",
                False, "Falha ao abrir"
            )
            return False, detalhes
        
        self._adicionar_diagnostico(
            numero_processo, id_processo, "abrir_processo",
            True, f"Pagina carregada ({len(html)} bytes)"
        )
        
        # Etapa 3: ViewState
        viewstate = extrair_viewstate(html)
        if not viewstate:
            self._adicionar_diagnostico(
                numero_processo, id_processo, "viewstate",
                False, "ViewState nao encontrado"
            )
            return False, detalhes
        
        # Etapa 4: Botao de download
        botao_id = self._identificar_botao_download(html)
        if not botao_id:
            self._adicionar_diagnostico(
                numero_processo, id_processo, "botao",
                False, "Botao nao encontrado"
            )
            return False, detalhes
        
        self._adicionar_diagnostico(
            numero_processo, id_processo, "botao",
            True, f"Botao: {botao_id}"
        )
        
        # Etapa 5: Enviar formulario
        delay()
        
        tipo_value = TIPO_DOCUMENTO.get(tipo_documento, "0")
        
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
            "": "on",
            "navbar": "navbar",
            "autoScroll": "",
            "javax.faces.ViewState": viewstate,
            botao_id: botao_id,
            "AJAX:EVENTS_COUNT": "1",
        }
        
        try:
            resp = self.auth.session.post(
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam",
                data=form_data,
                timeout=self.auth.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "*/*",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam?idProcesso={id_processo}&ca={ca}"
                }
            )
            
            if resp.status_code != 200:
                self._adicionar_diagnostico(
                    numero_processo, id_processo, "solicitar",
                    False, f"HTTP {resp.status_code}"
                )
                return False, detalhes
            
            texto = resp.text
            
            # Verifica tipo de download
            download_direto = "está sendo gerado" in texto.lower() and "aguarde" in texto.lower()
            area_download = "será disponibilizado" in texto.lower() or "área de download" in texto.lower()
            
            if download_direto:
                url = self._extrair_url_download_direto(texto)
                
                if url and diretorio:
                    arquivo = self._baixar_arquivo_direto(url, numero_processo, diretorio)
                    if arquivo:
                        detalhes["tipo_download"] = "direto"
                        detalhes["arquivo"] = str(arquivo)
                        self._adicionar_diagnostico(
                            numero_processo, id_processo, "solicitar",
                            True, f"Download direto: {arquivo.name}"
                        )
                        self.downloads_solicitados.add(numero_processo)
                        return True, detalhes
            
            if area_download or download_direto:
                detalhes["tipo_download"] = "area_download"
                self._adicionar_diagnostico(
                    numero_processo, id_processo, "solicitar",
                    True, "Enviado para area de download"
                )
                self.downloads_solicitados.add(numero_processo)
                return True, detalhes
            
            self._adicionar_diagnostico(
                numero_processo, id_processo, "solicitar",
                False, "Resposta inesperada"
            )
            return False, detalhes
            
        except Exception as e:
            self._adicionar_diagnostico(
                numero_processo, id_processo, "solicitar",
                False, f"Erro: {e}"
            )
            return False, detalhes
    
    def listar_disponiveis(self) -> List[DownloadDisponivel]:
        """Lista downloads disponiveis na area de downloads."""
        if not self.auth.usuario:
            self.auth.verificar_sessao()
        
        try:
            resp = self.auth.session.get(
                f"{API_BASE}/pjedocs-api/v1/downloadService/recuperarDownloadsDisponiveis",
                params={
                    "idUsuario": self.auth.usuario.id_usuario,
                    "sistemaOrigem": "PRIMEIRA_INSTANCIA"
                },
                timeout=self.auth.timeout
            )
            
            if resp.status_code == 200:
                data = resp.json()
                downloads = [
                    DownloadDisponivel.from_dict(d)
                    for d in data.get("downloadsDisponiveis", [])
                ]
                self.logger.info(f"Downloads disponiveis: {len(downloads)}")
                return downloads
                
        except Exception as e:
            self.logger.error(f"Erro ao listar downloads: {e}")
        
        return []
    
    def obter_url_download(self, hash_download: str) -> Optional[str]:
        """Obtem URL do S3 para download."""
        try:
            resp = self.auth.session.get(
                f"{API_BASE}/pjedocs-api/v2/repositorio/gerar-url-download",
                params={"hashDownload": hash_download},
                timeout=self.auth.timeout
            )
            
            if resp.status_code == 200:
                return resp.text.strip().strip('"')
                
        except Exception as e:
            self.logger.error(f"Erro ao obter URL: {e}")
        
        return None
    
    def baixar_arquivo(
        self,
        download: DownloadDisponivel,
        diretorio: Path
    ) -> Optional[Path]:
        """Baixa arquivo da area de downloads."""
        self.logger.info(f"Baixando: {download.nome_arquivo}")
        
        url = self.obter_url_download(download.hash_download)
        if not url:
            return None
        
        try:
            resp = requests.get(url, stream=True, timeout=120)
            
            if resp.status_code == 200:
                diretorio.mkdir(parents=True, exist_ok=True)
                filepath = diretorio / download.nome_arquivo
                
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                self.logger.info(f"[OK] {filepath} ({filepath.stat().st_size} bytes)")
                return filepath
                
        except Exception as e:
            self.logger.error(f"Erro ao baixar: {e}")
        
        return None
    
    def aguardar_downloads(
        self,
        processos: List[str],
        tempo_maximo: int = 300,
        intervalo: int = 15
    ) -> List[DownloadDisponivel]:
        """Aguarda downloads ficarem disponiveis."""
        self.logger.info(f"Aguardando {len(processos)} downloads...")
        
        time.sleep(15)
        
        inicio = time.time()
        encontrados: Set[str] = set()
        downloads: List[DownloadDisponivel] = []
        
        while (time.time() - inicio) < tempo_maximo:
            disponiveis = self.listar_disponiveis()
            
            for download in disponiveis:
                for proc in download.get_numeros_processos():
                    if proc in processos and proc not in encontrados:
                        encontrados.add(proc)
                        if download not in downloads:
                            downloads.append(download)
            
            elapsed = int(time.time() - inicio)
            self.logger.info(f"[{elapsed}s] {len(encontrados)}/{len(processos)}")
            
            if len(encontrados) >= len(processos):
                self.logger.info("[OK] Todos disponiveis!")
                return downloads
            
            time.sleep(intervalo)
        
        self.logger.warn("Timeout!")
        return downloads
