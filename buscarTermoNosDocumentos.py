"""
Etapa 3 — busca de termos nos documentos capturados (PDF e HTML).

Lê os arquivos dos processos com status 'capturado' na fila (fila.py),
extrai o texto (PDF nativo via PyMuPDF; HTML via parser da stdlib; OCR
opcional para PDF escaneado) e procura os termos pedidos — sem diferenciar
acento nem maiúsculas ("conciliação" == "CONCILIACAO").

Caso de uso original: verificar em quais processos algum advogado juntou
petição pedindo conciliação na janela capturada.

PDF escaneado (sem camada de texto) passa por OCR automaticamente, se o
Tesseract estiver instalado. HTML sempre tem seu texto — mesmo um documento
de uma palavra ("ciente.") é analisado, nunca marcado como ilegível.

Uso:
  python buscarTermoNosDocumentos.py                        # termo padrão: conciliação
  python buscarTermoNosDocumentos.py --termo conciliação --termo audiência
  python buscarTermoNosDocumentos.py --sem-ocr              # desliga o OCR (mais rápido)
  python buscarTermoNosDocumentos.py --refazer              # inclui os já extraídos

Saída: relatório no terminal + resultado_busca_AAAAMMDD_HHMM.csv
(processo; arquivo; termo; ocorrências; trechos com contexto).
"""

import argparse
import csv
import re
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import fila

CONTEXTO = 60          # caracteres de contexto de cada lado do termo
MAX_TRECHOS = 3        # trechos por arquivo/termo no relatório


def normalizar(texto: str) -> str:
    """minúsculas + sem acento, PRESERVANDO o comprimento (1 char -> 1 char),
    para que os índices dos achados apontem para o texto original."""
    return "".join(unicodedata.normalize("NFD", ch)[0].lower() for ch in texto)


class _ExtratorHtml(HTMLParser):
    """Extrai texto visível de HTML (ignora script/style)."""
    def __init__(self):
        super().__init__()
        self.partes, self._ignorar = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._ignorar += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._ignorar:
            self._ignorar -= 1

    def handle_data(self, data):
        if not self._ignorar:
            self.partes.append(data)


def texto_de_html(caminho: Path) -> str:
    p = _ExtratorHtml()
    p.feed(caminho.read_text(encoding="utf-8", errors="replace"))
    return " ".join(p.partes)


def tesseract_disponivel() -> bool:
    """Verifica o Tesseract, tentando os caminhos padrão do Windows se
    não estiver no PATH. Retorna False (com aviso) se não houver binário."""
    import pytesseract
    candidatos = [
        None,  # PATH
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        str(Path.home() / r"AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for cmd in candidatos:
        try:
            if cmd:
                pytesseract.pytesseract.tesseract_cmd = cmd
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            continue
    return False


def texto_de_pdf(caminho: Path, usar_ocr: bool) -> str:
    import fitz
    partes = []
    with fitz.open(caminho) as doc:
        for pagina in doc:
            partes.append(pagina.get_text())
        texto = "\n".join(partes)
        if len(texto.strip()) >= 50 or not usar_ocr:
            return texto
        # PDF sem camada de texto (escaneado): OCR página a página
        try:
            import io
            import pytesseract
            from PIL import Image
            ocr = []
            for pagina in doc:
                img = Image.open(io.BytesIO(pagina.get_pixmap(dpi=200).tobytes("png")))
                try:
                    ocr.append(pytesseract.image_to_string(img, lang="por"))
                except pytesseract.TesseractError:
                    ocr.append(pytesseract.image_to_string(img))  # sem pacote 'por'
            return "\n".join(ocr)
        except Exception as e:
            print(f"    [OCR falhou] {caminho.name}: {e}")
            return texto


def extrair_texto(caminho: Path, usar_ocr: bool) -> str:
    if caminho.suffix.lower() in (".html", ".htm"):
        return texto_de_html(caminho)
    return texto_de_pdf(caminho, usar_ocr)


def buscar_termos(texto: str, termos_norm: list) -> dict:
    """{termo: [(posicao, trecho_original), ...]} — busca no texto normalizado,
    trecho recortado do original (mesmos índices, comprimento preservado)."""
    norm = normalizar(texto)
    achados = {}
    for termo in termos_norm:
        posicoes = [m.start() for m in re.finditer(re.escape(termo), norm)]
        trechos = []
        for pos in posicoes:
            ini, fim = max(0, pos - CONTEXTO), pos + len(termo) + CONTEXTO
            trechos.append((pos, " ".join(texto[ini:fim].split())))
        if trechos:
            achados[termo] = trechos
    return achados


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--termo", action="append", metavar="PALAVRA",
                   help="termo a procurar (repetível; padrão: conciliação)")
    p.add_argument("--sem-ocr", action="store_true",
                   help="desliga o OCR automático de PDF escaneado (mais rápido)")
    p.add_argument("--refazer", action="store_true",
                   help="reanalisa também processos já marcados como extraídos")
    args = p.parse_args()

    termos = args.termo or ["conciliação"]
    termos_norm = [normalizar(t) for t in termos]

    usar_ocr = not args.sem_ocr and tesseract_disponivel()
    if not args.sem_ocr and not usar_ocr:
        print("[aviso] Tesseract não encontrado — PDFs escaneados ficarão sem análise.\n"
              "        Instale com: winget install UB-Mannheim.TesseractOCR\n"
              "        (marque o idioma Portuguese na instalação)\n")

    con = fila.conectar()
    status = "('capturado','extraido')" if args.refazer else "('capturado')"
    linhas = con.execute(
        f"""SELECT npu, arquivo FROM fila
            WHERE status IN {status} AND arquivo IS NOT NULL ORDER BY npu""").fetchall()
    if not linhas:
        print("Nada a analisar: nenhum processo capturado com arquivo na fila "
              "(use --refazer para reanalisar os já extraídos).")
        return

    print(f"Analisando {len(linhas)} processo(s), termos: {', '.join(termos)}\n")
    resultados = []       # (npu, arquivo, termo, ocorrencias, trechos)
    com_termo = {}        # npu -> total de ocorrências
    sem_texto = []

    for npu, arquivos in linhas:
        for arq in arquivos.split(";"):
            caminho = Path(arq)
            if not caminho.exists():
                print(f"  [ausente] {npu}: {caminho.name}")
                continue
            try:
                texto = extrair_texto(caminho, usar_ocr)
            except Exception as e:
                print(f"  [ilegível] {npu}: {caminho.name} — {e}")
                continue
            # só PDF pode ser "sem texto" (escaneado sem OCR); HTML sempre
            # tem seu conteúdo, por menor que seja ("ciente.")
            if caminho.suffix.lower() == ".pdf" and len(texto.strip()) < 50:
                sem_texto.append((npu, caminho.name))
                continue
            achados = buscar_termos(texto, termos_norm)
            for termo, trechos in achados.items():
                com_termo[npu] = com_termo.get(npu, 0) + len(trechos)
                resultados.append((npu, caminho.name, termo, len(trechos),
                                   " | ".join(t for _, t in trechos[:MAX_TRECHOS])))
        fila.marcar_extraido(con, npu)

    # ---------------- relatório ----------------
    print("=" * 62)
    print(f"RESULTADO DA BUSCA — {', '.join(termos)}")
    print("=" * 62)
    print(f"Processos analisados: {len(linhas)}")
    print(f"Processos COM o termo: {len(com_termo)}\n")
    for npu, arq, termo, n, trecho in resultados:
        print(f"  {npu}  [{arq}]")
        print(f"    '{termo}' x{n}: ...{trecho[:200]}...")
    if not resultados:
        print("  Nenhuma ocorrência encontrada.")
    if sem_texto:
        causa = ("OCR indisponível — instale o Tesseract e rode de novo"
                 if not usar_ocr else "nem o OCR extraiu texto legível")
        print(f"\nPDF escaneado sem texto ({len(sem_texto)} arquivo(s) — {causa}):")
        for npu, nome in sem_texto:
            print(f"  {npu}  [{nome}]")

    saida = Path.cwd() / f"resultado_busca_{datetime.now():%Y%m%d_%H%M}.csv"
    with open(saida, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["numeroProcesso", "arquivo", "termo", "ocorrencias", "trechos"])
        w.writerows(resultados)
        for npu, nome in sem_texto:
            w.writerow([npu, nome, "", 0, "PDF ESCANEADO SEM TEXTO (requer OCR/Tesseract)"])
    print(f"\nCSV: {saida}")


if __name__ == "__main__":
    main()
