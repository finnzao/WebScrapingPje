"""
Serviço de download de processos.
"""

import re
import time
import requests
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple, Any

from ..config import BASE_URL, TIPO_DOCUMENTO_VALUES
from ..core import PJEHttpClient, sessao_caiu
from ..exceptions import (
    SessaoExpirada, AcessoNegado, ProcessoNaoEncontrado,
    PdfInvalido, RespostaDesconhecida,
)
from ..models import DownloadDisponivel, DiagnosticoDownload
from ..utils import delay, extrair_viewstate, current_month_year, get_logger


class DownloadService:
    """Serviço para download de processos."""

    def __init__(self, http_client: PJEHttpClient, download_dir: Optional[Path] = None):
        self.client = http_client
        self.logger = get_logger()
        self.download_dir = download_dir or Path.home() / "Downloads" / "pje_downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.debug_dir = self.download_dir / "_debug"
        self.diagnosticos: List[DiagnosticoDownload] = []
        self.downloads_solicitados: Set[str] = set()

    def limpar_diagnosticos(self):
        self.diagnosticos.clear()
        self.downloads_solicitados.clear()

    def _salvar_debug(self, nome: str, conteudo: str):
        """Salva payload inesperado para análise posterior."""
        try:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            fp = self.debug_dir / f"{re.sub(r'[^0-9A-Za-z_.-]', '_', nome)}.html"
            fp.write_text(conteudo, encoding="utf-8")
            self.logger.warning(f"Resposta inesperada salva em {fp}")
        except Exception:
            pass

    # ==================== TIMELINE (autos digitais) ====================
    # O HTML de listAutosDigitais.seam traz a timeline renderizada:
    # cabeçalhos <span class="data-interna">06 ago 2026</span> seguidos dos
    # documentos <span>573407589 - Petição</span>. O download individual é
    # GET documento/download/{id} (endpoint que o próprio viewer da página usa).

    _MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
              "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
    _RE_TIMELINE = re.compile(
        r'data-interna">([^<]+)<'               # cabeçalho de data ("06 ago 2026")
        r'|>(\d{5,})\s*-\s*([^<]+)</span></a>'  # documento ("573407589 - Petição")
    )

    def _parse_data_interna(self, texto: str):
        """'06 ago 2026' -> datetime.date, ou None se não reconhecer."""
        m = re.match(r'(\d{1,2})\s+([a-zç]{3})\.?\s+(\d{4})', texto.strip().lower())
        if not m or m.group(2) not in self._MESES:
            return None
        from datetime import date
        return date(int(m.group(3)), self._MESES[m.group(2)], int(m.group(1)))

    # gatilho da paginação infinita: script novaPagina() no HTML da timeline
    _RE_GATILHO_PAGINACAO = re.compile(
        r"novaPagina=function\(\)\{A4J\.AJAX\.Submit\('divTimeLine'.*?'ajaxSingle':'([^']+)'",
        re.DOTALL)

    def listar_documentos_timeline(self, html_processo: str,
                                   data_inicial=None) -> List[Dict[str, Any]]:
        """Extrai da timeline: [{'id_documento', 'tipo', 'data'}, ...].

        'data' é a data de juntada (do cabeçalho do dia na timeline);
        data_inicial semeia a data corrente para páginas de continuação,
        cujo primeiro bloco pode vir sem cabeçalho de dia.
        """
        import html as htmllib
        docs = []
        data_atual = data_inicial
        for m in self._RE_TIMELINE.finditer(html_processo):
            if m.group(1) is not None:
                data_atual = self._parse_data_interna(htmllib.unescape(m.group(1))) or data_atual
            else:
                docs.append({
                    "id_documento": int(m.group(2)),
                    "tipo": htmllib.unescape(m.group(3)).strip(),
                    "data": data_atual,
                })
        return docs

    def listar_timeline_completa(self, html_inicial: str,
                                 parar_antes_de=None,
                                 max_paginas: int = 60) -> List[Dict[str, Any]]:
        """Timeline completa, seguindo a paginação infinita (rolagem AJAX).

        Repete o POST do gatilho novaPagina() até não virem documentos novos
        (dedupe por id — funciona tanto para resposta incremental quanto
        cumulativa) ou até as datas ficarem mais antigas que parar_antes_de
        (a timeline vem em ordem decrescente, então dá para parar cedo).
        """
        docs = self.listar_documentos_timeline(html_inicial)
        vistos = {d["id_documento"] for d in docs}

        viewstate = extrair_viewstate(html_inicial)
        gatilho_m = self._RE_GATILHO_PAGINACAO.search(html_inicial)
        if not viewstate or not gatilho_m:
            return docs  # sem paginação nesta página (processo pequeno)
        gatilho = gatilho_m.group(1)

        def data_mais_antiga():
            datas = [d["data"] for d in docs if d["data"]]
            return min(datas) if datas else None

        for _ in range(max_paginas):
            antiga = data_mais_antiga()
            if parar_antes_de and antiga and antiga < parar_antes_de:
                break
            delay(0.3, 0.8)
            resp = self.client.session.post(
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam",
                data={
                    "AJAXREQUEST": "_viewRoot",
                    "divTimeLine:chkExibirDocumentos": "on",
                    "divTimeLine:chkExibirMovimentos": "on",
                    "divTimeLine": "divTimeLine",
                    "javax.faces.ViewState": viewstate,
                    "ajaxSingle": gatilho,
                    gatilho: gatilho,
                    "AJAX:EVENTS_COUNT": "1",
                },
                timeout=self.client.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest", "Accept": "*/*",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam",
                },
            )
            if sessao_caiu(resp):
                raise SessaoExpirada("sessão caiu ao paginar a timeline")
            if resp.status_code != 200:
                break
            pagina = self.listar_documentos_timeline(resp.text, data_inicial=antiga)
            novos = [d for d in pagina if d["id_documento"] not in vistos]
            if not novos:
                break
            docs.extend(novos)
            vistos.update(d["id_documento"] for d in novos)
        return docs

    def baixar_documento(self, id_documento: int, filepath: Path) -> Path:
        """Baixa um documento individual pelo endpoint REST do viewer."""
        resp = self.client.get(
            f"{BASE_URL}/pje/seam/resource/rest/pje-legacy/documento/download/{id_documento}",
            stream=True,
        )
        if sessao_caiu(resp):
            raise SessaoExpirada(f"sessão caiu ao baixar documento {id_documento}")
        if resp.status_code in (401, 403):
            raise AcessoNegado(f"HTTP {resp.status_code} no documento {id_documento}")
        if resp.status_code != 200:
            raise PdfInvalido(f"HTTP {resp.status_code} no documento {id_documento}",
                              erro_tipo="http_erro")
        return self._gravar_arquivo_validado(resp, filepath)

    def capturar_por_timeline(
        self, id_processo: int, numero_processo: str,
        tipo_documento: str = "Peticao",
        data_inicio: str = "", data_fim: str = "",
        diretorio: Path = None,
    ) -> Dict[str, Any]:
        """Captura documentos de um processo via timeline dos autos digitais.

        Filtra por tipo (trecho do nome, sem acento) e janela de juntada
        (dd/mm/aaaa) usando os metadados da própria timeline, e baixa cada
        PDF individualmente — sem gerar autos completos no servidor.
        """
        from datetime import datetime
        from .task_service import normalizar_texto

        detalhes: Dict[str, Any] = {"id_processo": id_processo,
                                    "numero_processo": numero_processo}
        dt_ini = datetime.strptime(data_inicio, "%d/%m/%Y").date() if data_inicio else None
        dt_fim = datetime.strptime(data_fim, "%d/%m/%Y").date() if data_fim else None

        html = self.abrir_processo(id_processo)
        if not html:
            detalhes.update(sucesso=False, erro_tipo="abrir_processo")
            return detalhes

        # timeline completa (paginação infinita), parando cedo ao passar do
        # início da janela — a timeline vem em ordem decrescente
        docs = self.listar_timeline_completa(html, parar_antes_de=dt_ini)
        detalhes["documentos_timeline"] = len(docs)
        if not docs:
            # processo sem nenhum documento reconhecido na timeline: salva
            # para inspeção — pode ser marcação diferente ou processo sigiloso
            self._salvar_debug(f"timeline_vazia_{numero_processo}", html[:30000])
            detalhes.update(sucesso=False, erro_tipo="timeline_vazia")
            return detalhes

        alvo = normalizar_texto(tipo_documento)

        def na_janela(d):
            if d["data"] is None:
                return True  # sem data na timeline: não descarta às cegas
            return (not dt_ini or d["data"] >= dt_ini) and (not dt_fim or d["data"] <= dt_fim)

        achados = [d for d in docs
                   if alvo in normalizar_texto(d["tipo"]) and na_janela(d)]
        detalhes["documentos_no_filtro"] = [
            {"id": d["id_documento"], "tipo": d["tipo"],
             "data": d["data"].isoformat() if d["data"] else None}
            for d in achados
        ]
        if not achados:
            detalhes.update(sucesso=False, erro_tipo="sem_documentos")
            return detalhes

        diretorio = diretorio or self.download_dir
        arquivos, falhas = [], []
        for d in achados:
            nome = (f"{numero_processo}_{d['id_documento']}_"
                    f"{re.sub(r'[^0-9A-Za-z_-]', '_', normalizar_texto(d['tipo']))[:40]}.pdf")
            try:
                arquivos.append(str(self.baixar_documento(d["id_documento"], diretorio / nome)))
            except (AcessoNegado, PdfInvalido) as e:
                self.logger.warning(f"Doc {d['id_documento']} de {numero_processo}: {e}")
                falhas.append({"id": d["id_documento"], "erro": str(e)})
        detalhes["arquivos"] = arquivos
        if falhas:
            detalhes["falhas"] = falhas
            detalhes["erro_msg"] = "; ".join(
                f"doc {f['id']}: {f['erro']}" for f in falhas)
        if arquivos:
            detalhes.update(sucesso=True, tipo_download="documento_individual",
                            arquivo_baixado=";".join(arquivos))
        else:
            detalhes.update(sucesso=False, erro_tipo="download_documento_falhou")
        return detalhes

    def gerar_chave_acesso(self, id_processo: int) -> Optional[str]:
        """Gera chave de acesso para processo."""
        resp = self.client.api_get(f"painelUsuario/gerarChaveAcessoProcesso/{id_processo}")
        if sessao_caiu(resp):
            raise SessaoExpirada(f"sessão caiu ao gerar chave do processo {id_processo}")
        if resp.status_code in (401, 403):
            raise AcessoNegado(f"HTTP {resp.status_code} ao gerar chave do processo {id_processo}")
        if resp.status_code == 200:
            return resp.text.strip().strip('"')
        self.logger.error(f"Erro ao gerar chave: HTTP {resp.status_code}")
        return None

    def abrir_processo(self, id_processo: int, ca: str = None) -> Optional[str]:
        """Abre página de autos digitais."""
        if not ca:
            ca = self.gerar_chave_acesso(id_processo)
            if not ca:
                return None
        resp = self.client.get(
            f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam",
            params={"idProcesso": id_processo, "ca": ca}
        )
        if sessao_caiu(resp):
            raise SessaoExpirada(f"sessão caiu ao abrir processo {id_processo}")
        if resp.status_code == 200:
            return resp.text
        self.logger.error(f"Erro ao abrir processo: HTTP {resp.status_code}")
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
    
    # HTML que é página do sistema (erro/login), não conteúdo de documento
    _MARCAS_PAGINA_SISTEMA = ("login.seam", "kc-login", "acesso negado",
                              "ocorreu um erro", "errorpage", "j_id1190")

    def _gravar_arquivo_validado(self, resp: requests.Response, filepath: Path) -> Path:
        """Grava resposta em disco de forma atômica e valida o conteúdo.

        Escreve em .part e renomeia conforme o conteúdo real:
        - %PDF / PK  -> mantém o nome pedido (.pdf/.zip)
        - HTML de documento (peça produzida no editor do PJE) -> .html;
          o endpoint documento/download devolve o próprio conteúdo nesses
          casos, então salvar a resposta É a cópia do documento
        - HTML de página do sistema (erro/login) ou outro lixo -> rejeita,
          salvando o payload em _debug para diagnóstico
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        tmp = filepath.with_suffix(filepath.suffix + ".part")
        try:
            with open(tmp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            with open(tmp, "rb") as f:
                inicio = f.read(4096)

            if inicio.startswith(b"%PDF") or inicio.startswith(b"PK"):
                tmp.replace(filepath)
                return filepath

            texto = inicio.decode("utf-8", errors="replace")
            eh_html = texto.lstrip()[:1] == "<" or "html" in resp.headers.get("Content-Type", "")
            eh_pagina_sistema = (
                any(m in texto.lower() for m in self._MARCAS_PAGINA_SISTEMA)
                or texto.lstrip().lower().startswith("<?xml")  # erro XML do S3
            )
            if eh_html and not eh_pagina_sistema:
                destino = filepath.with_suffix(".html")
                tmp.replace(destino)
                return destino

            ctype = resp.headers.get("Content-Type", "?")
            self._salvar_debug(f"doc_invalido_{filepath.stem}", texto)
            raise PdfInvalido(
                f"conteúdo não é PDF/ZIP nem documento HTML "
                f"(content-type={ctype}, inicio={inicio[:40]!r}): {filepath.name}")
        finally:
            tmp.unlink(missing_ok=True)

    def _baixar_arquivo_direto(self, url: str, numero_processo: str, diretorio: Path) -> Optional[Path]:
        """Baixa arquivo direto do S3."""
        match = re.search(r'/([^/]+-processo\.pdf)', url)
        nome = match.group(1) if match else f"{numero_processo}-processo.pdf"

        resp = requests.get(url, stream=True, timeout=120)
        if resp.status_code == 200:
            filepath = self._gravar_arquivo_validado(resp, diretorio / nome)
            self.logger.success(f"Baixado: {filepath}")
            return filepath
        self.logger.error(f"Erro download direto: HTTP {resp.status_code}")
        return None
    
    # Mensagens do PJE que indicam "consulta OK, mas nenhum documento casa
    # com o filtro" — para a fila isso é 'sem_juntada', não erro.
    _PADROES_SEM_DOCUMENTO = [
        "não existem documentos", "nao existem documentos",
        "nenhum documento", "não foram encontrados documentos",
        "nao foram encontrados documentos",
    ]

    def solicitar_download(
        self, id_processo: int, numero_processo: str,
        tipo_documento: str = "Selecione", html_processo: str = None,
        diretorio_download: Path = None,
        data_inicio: str = "", data_fim: str = ""
    ) -> Tuple[bool, Dict[str, Any]]:
        """Solicita download de processo.

        data_inicio/data_fim (dd/mm/aaaa) filtram os documentos pela data de
        juntada — mesmo filtro da tela de autos digitais. Combinado com
        tipo_documento, responde "quais documentos do tipo X foram juntados
        na janela Y" sem baixar os autos inteiros.

        Em falha, detalhes["erro_tipo"] categoriza o motivo para a fila.
        """
        detalhes: Dict[str, Any] = {"id_processo": id_processo, "numero_processo": numero_processo}

        # Chave de acesso
        ca = self.gerar_chave_acesso(id_processo)
        if not ca:
            detalhes["erro_tipo"] = "chave_acesso"
            return False, detalhes

        # Abrir processo
        if not html_processo:
            delay()
            html_processo = self.abrir_processo(id_processo, ca)
            if not html_processo:
                detalhes["erro_tipo"] = "abrir_processo"
                return False, detalhes

        # ViewState
        viewstate = extrair_viewstate(html_processo)
        if not viewstate:
            detalhes["erro_tipo"] = "viewstate"
            return False, detalhes

        # Botão
        botao_id = self._identificar_botao_download(html_processo)
        if not botao_id:
            detalhes["erro_tipo"] = "botao_download"
            self._salvar_debug(f"sem_botao_{numero_processo}", html_processo[:20000])
            return False, detalhes

        delay()

        # O calendário JSF espera o mês/ano corrente coerente com a data digitada
        mes_ano_inicio = data_inicio[3:] if data_inicio else current_month_year()
        mes_ano_fim = data_fim[3:] if data_fim else current_month_year()

        # Formulário
        form_data = {
            "AJAXREQUEST": "_viewRoot",
            "navbar:cbTipoDocumento": TIPO_DOCUMENTO_VALUES.get(tipo_documento, "0"),
            "navbar:idDe": "", "navbar:idAte": "",
            "navbar:dtInicioInputDate": data_inicio, "navbar:dtInicioInputCurrentDate": mes_ano_inicio,
            "navbar:dtFimInputDate": data_fim, "navbar:dtFimInputCurrentDate": mes_ano_fim,
            "navbar:cbCronologia": "DESC", "": "on", "navbar": "navbar",
            "autoScroll": "", "javax.faces.ViewState": viewstate,
            botao_id: botao_id, "AJAX:EVENTS_COUNT": "1",
        }

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

        if sessao_caiu(resp):
            raise SessaoExpirada(f"sessão caiu ao solicitar download de {numero_processo}")

        if resp.status_code != 200:
            detalhes["erro_tipo"] = "http_erro"
            detalhes["status_code"] = resp.status_code
            return False, detalhes

        texto = resp.text
        texto_lower = texto.lower()

        # Download direto (poucas peças)
        if "está sendo gerado" in texto_lower or "aguarde" in texto_lower:
            url_direta = self._extrair_url_download_direto(texto)
            if url_direta and diretorio_download:
                arquivo = self._baixar_arquivo_direto(url_direta, numero_processo, diretorio_download)
                if arquivo:
                    detalhes["tipo_download"] = "direto"
                    detalhes["arquivo_baixado"] = str(arquivo)
                    self.downloads_solicitados.add(numero_processo)
                    return True, detalhes
                detalhes["erro_tipo"] = "download_direto_falhou"
                return False, detalhes

        # Área de download (muitas peças)
        if "será disponibilizado" in texto_lower or "área de download" in texto_lower:
            detalhes["tipo_download"] = "area_download"
            self.downloads_solicitados.add(numero_processo)
            return True, detalhes

        # Nenhum documento casa com o filtro tipo/data — resultado válido
        if any(p in texto_lower for p in self._PADROES_SEM_DOCUMENTO):
            detalhes["erro_tipo"] = "sem_documentos"
            return False, detalhes

        # Resposta desconhecida NUNCA é sucesso: salva payload e categoriza.
        # (O padrão antigo `"download" in texto` marcava falha como sucesso,
        # porque a palavra aparece em rótulos de botão da própria página.)
        self._salvar_debug(f"resposta_{numero_processo}", texto[:20000])
        detalhes["erro_tipo"] = "resposta_desconhecida"
        mensagens = re.findall(r'rich-messages-label[^>]*>([^<]+)<', texto)
        if mensagens:
            detalhes["mensagens"] = mensagens
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
                filepath = self._gravar_arquivo_validado(resp, diretorio / download.nome_arquivo)
                self.logger.success(f"Baixado: {filepath}")
                return filepath
            self.logger.error(f"Erro ao baixar: HTTP {resp.status_code}")
        except PdfInvalido:
            raise
        except Exception as e:
            self.logger.error(f"Erro ao baixar: {e}")
        return None

    def aguardar_downloads(self, processos: List[str], tempo_maximo: int = 300, intervalo: int = 15) -> List[DownloadDisponivel]:
        """Aguarda downloads ficarem disponíveis.

        Desiste cedo (timeout parcial) se nenhum download novo aparecer por
        90s — evita esperar tempo_maximo inteiro por um processo que nunca
        vai chegar (ex.: solicitação aceita mas geração falhou no servidor).
        """
        self.logger.info(f"Aguardando {len(processos)} downloads...")
        time.sleep(15)

        inicio = time.time()
        encontrados: Set[str] = set()
        downloads_encontrados: List[DownloadDisponivel] = []
        tempo_sem_novos = 0

        while (time.time() - inicio) < tempo_maximo:
            downloads = self.listar_downloads_disponiveis()

            novos = False
            for download in downloads:
                for proc in download.get_numeros_processos():
                    if proc in processos and proc not in encontrados:
                        encontrados.add(proc)
                        novos = True
                        if download not in downloads_encontrados:
                            downloads_encontrados.append(download)

            self.logger.info(f"Encontrados: {len(encontrados)}/{len(processos)}")

            if len(encontrados) >= len(processos):
                return downloads_encontrados

            tempo_sem_novos = 0 if novos else tempo_sem_novos + intervalo
            if tempo_sem_novos >= 90 and encontrados:
                self.logger.warning(
                    f"Timeout parcial: seguindo com {len(encontrados)}/{len(processos)}")
                return downloads_encontrados

            time.sleep(intervalo)

        return downloads_encontrados
