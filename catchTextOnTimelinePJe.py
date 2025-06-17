"""
Automação PJe – download em massa de documentos
-----------------------------------------------
• Login, perfil, navegação por etiqueta
• Busca por processos, download dos autos
• Dentro do processo, pesquisa por termo na timeline
  e download de cada documento correspondente
"""

import requests
import fitz
import os
import urllib.parse
import re
import time
import json
import unicodedata
from functools import wraps
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, StaleElementReferenceException,
    ElementClickInterceptedException, NoSuchElementException, NoAlertPresentException
)
from selenium.webdriver.remote.webelement import WebElement


# ----------------------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# ----------------------------------------------------------------------
driver, wait = None, None


def retry(max_retries=2):
    """Decorador para reexecutar função em caso de Timeout/Stale."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kw):
            for attempt in range(1, max_retries+1):
                try:
                    return func(*args, **kw)
                except (TimeoutException, StaleElementReferenceException) as e:
                    if attempt == max_retries:
                        raise
                    print(
                        f"[WARN] {func.__name__}: tentativa {attempt} falhou → {e}")
        return wrapper
    return decorator


def initialize_driver():
    global driver, wait
    chrome_options = webdriver.ChromeOptions()
    dl_dir = os.path.join(os.path.expanduser("~"), "Downloads", "processosBaixadosEtiqueta")
    os.makedirs(dl_dir, exist_ok=True)

    chrome_options.add_experimental_option("prefs", {
        "plugins.always_open_pdf_externally": False,  # Permitir visualização de PDFs no navegador
        "download.default_directory": dl_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    })

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 40)
    print(f"[INIT] Chrome iniciado – downloads em: {dl_dir}")


def save_screenshot(label):
    path_dir = ".logs/screenshots"
    os.makedirs(path_dir, exist_ok=True)
    fp = os.path.join(path_dir, f"{label}.png")
    driver.save_screenshot(fp)
    print(f"[SNAP] {fp}")

# ----------------------------------------------------------------------
# FLUXO DE LOGIN E PERFIL
# ----------------------------------------------------------------------


@retry()
def login(username: str, password: str):
    driver.get("https://pje.tjba.jus.br/pje/login.seam")
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ssoFrame")))
    wait.until(EC.presence_of_element_located(
        (By.ID, "username"))).send_keys(username)
    wait.until(EC.presence_of_element_located(
        (By.ID, "password"))).send_keys(password)
    wait.until(EC.element_to_be_clickable((By.ID, "kc-login"))).click()
    driver.switch_to.default_content()
    wait.until(EC.presence_of_element_located(
        (By.CLASS_NAME, "dropdown-toggle")))
    print("[OK] Login efetuado")


@retry()
def select_profile(profile_text: str):
    dropdown = wait.until(EC.element_to_be_clickable(
        (By.CLASS_NAME, "dropdown-toggle")))
    dropdown.click()
    opt = wait.until(EC.element_to_be_clickable(
        (By.XPATH, f"//a[contains(text(),'{profile_text}')]")))
    driver.execute_script("arguments[0].click();", opt)
    print(f"[OK] Perfil '{profile_text}' selecionado")


def save_exception_screenshot(filename):
    """
    Salva um screenshot atual do driver na pasta '.logs/exception'.
    """
    directory = ".logs/exception"
    if not os.path.exists(directory):
        os.makedirs(directory)
    filepath = os.path.join(directory, filename)
    driver.save_screenshot(filepath)
    print(f"Screenshot salvo em: {filepath}")
# ----------------------------------------------------------------------
# NAVEGAÇÃO POR ETIQUETA E LISTA DE PROCESSOS
# ----------------------------------------------------------------------


def click(xpath):
    el = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    driver.execute_script("arguments[0].scrollIntoView(true);", el)
    driver.execute_script("arguments[0].click();", el)


def click_element(
    xpath: str = None,
    element_id: str = None,
    css_selector: str = None
) -> None:

    if not xpath and not element_id and not css_selector:
        raise ValueError(
            "Informe ao menos um seletor: xpath, element_id ou css_selector.")

    def _try_click(by: By, selector: str, desc: str) -> bool:
        """Espera o elemento ficar clicável e tenta clique normal + JavaScript."""
        try:
            print(f"[click_element] Tentando clicar via {desc}: {selector}")
            element = wait.until(EC.element_to_be_clickable((by, selector)))
            driver.execute_script(
                "arguments[0].scrollIntoView(true);", element)
            try:
                element.click()
                print(f"Elemento clicado com sucesso ({desc}): {selector}")
                return True
            except (ElementClickInterceptedException, Exception) as e:
                print(
                    f"Erro ao clicar normalmente via {desc}: {e}. Tentando JavaScript...")
                driver.execute_script("arguments[0].click();", element)
                print(f"Elemento clicado com JavaScript ({desc}): {selector}")
                return True
        except Exception as ex:
            print(f"Falha ao tentar clicar via {desc}: {ex}")
            return False

    # 1) Se xpath foi fornecido, tenta
    if xpath:
        if _try_click(By.XPATH, xpath, "XPATH"):
            return

    # 2) Se ID foi fornecido, tenta
    if element_id:
        if _try_click(By.ID, element_id, "ID"):
            return

    # 3) Se css_selector foi fornecido, tenta JavaScript com querySelector
    if css_selector:
        try:
            print(
                f"[click_element] Tentando CSS SELECTOR (JS) via: {css_selector}")
            # Se quiser esperar ficar 'clicável' pela API do Selenium:
            wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, css_selector)))
            # Agora clique usando o querySelector
            js_code = f"""
                const el = document.querySelector('{css_selector}');
                if(el) {{
                    el.scrollIntoView();
                    el.click();
                }} else {{
                    throw new Error("Elemento não encontrado via querySelector('{css_selector}')");
                }}
            """
            driver.execute_script(js_code)
            print(
                f"Elemento clicado com sucesso (CSS SELECTOR + JS): {css_selector}")
            return
        except Exception as ex:
            print(f"Falha ao tentar clicar via CSS SELECTOR + JS: {ex}")

    # Se chegou aqui, falhou em tudo
    save_exception_screenshot("click_element_exception.png")
    msg = (
        "Não foi possível clicar no elemento usando XPATH='{xpath}', ID='{element_id}' ou "
        f"CSS SELECTOR='{css_selector}'."
    )
    print(msg)
    raise NoSuchElementException(msg)


def confirmar_popup_download(timeout_alert=5, timeout_modal=10) -> bool:
    try:
        WebDriverWait(driver, timeout_alert).until(EC.alert_is_present())
        driver.switch_to.alert.accept()
        print("[POPUP] alerta JS aceito")
        return True
    except (TimeoutException, NoAlertPresentException):
        pass
    for xp in ["//button[contains(.,'Confirmar')]",
               "//button[contains(.,'OK')]",
               "//button[contains(@class,'btn-primary')]"]:
        try:
            btn = WebDriverWait(driver, timeout_modal).until(
                EC.element_to_be_clickable((By.XPATH, xp)))
            driver.execute_script("arguments[0].click();", btn)
            print("[POPUP] modal confirmado")
            return True
        except TimeoutException:
            continue
    return False


def switch_to_new_window(original_handles, timeout=10):
    """
    Alterna para a nova janela que foi aberta após a execução de uma ação.
    """
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.window_handles) > len(original_handles)
        )
        new_handles = set(driver.window_handles) - original_handles
        if new_handles:
            new_window = new_handles.pop()
            driver.switch_to.window(new_window)
            print(f"Alternado para a nova janela: {new_window}")
            return new_window
        else:
            raise TimeoutException(
                "Nova janela não foi encontrada dentro do tempo especificado.")
    except TimeoutException as e:
        save_exception_screenshot("switch_to_new_window_timeout.png")
        print("TimeoutException: Não foi possível encontrar a nova janela. Captura de tela salva.")
        raise e


def switch_to_original_window(original_handle):
    """
    Alterna de volta para a janela original.
    """
    try:
        driver.switch_to.window(original_handle)
        print(f"Retornado para a janela original: {original_handle}")
    except Exception as e:
        save_exception_screenshot("switch_to_original_window_exception.png")
        print(
            f"Erro ao retornar para a janela original. Captura de tela salva. Erro: {e}")
        raise e


def input_tag(search_text):
    search_input = wait.until(EC.element_to_be_clickable(
        (By.ID, "itPesquisarEtiquetas")))
    search_input.clear()
    search_input.send_keys(search_text)
    click_element(
        xpath="/html/body/app-root/selector/div/div/div[2]/right-panel/div/etiquetas/div[1]/div/div[1]/div[2]/div[1]/span/button[1]")
    time.sleep(2)
    print(f"Pesquisa realizada com o texto: {search_text}")
    click_element(
        xpath="/html/body/app-root/selector/div/div/div[2]/right-panel/div/etiquetas/div[1]/div/div[2]/ul/p-datalist/div/div/ul/li/div/li/div[2]/span/span")


def _norm(txt: str) -> str:
    """minúsculas + sem acento + espaços comprimidos"""
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(ch for ch in txt if unicodedata.category(ch) != "Mn")
    return " ".join(txt.lower().split())


def extrair_metadados_documento(driver):
    """
    Extrai o ID e a descrição do documento atual aberto na visualização do PJe.
    """
    try:
        titulo = driver.find_element(By.ID, "detalheDocumento:tituloDocumento")
        span = titulo.find_element(By.TAG_NAME, "span")
        texto = span.get_attribute("title")  # Ex: "485404219 - Petição (...)"
        match = re.match(r"(\d+)\s*-\s*(.*)", texto)
        if match:
            return {
                "documento_id": match.group(1),
                "descricao": match.group(2).strip()
            }
        return {"documento_id": None, "descricao": texto.strip()}
    except Exception as e:
        print(f"[WARN] Falha ao extrair metadados: {e}")
        return {"documento_id": None, "descricao": "desconhecido"}


def baixar_pdf_binario(driver):
    """
    Acessa o iframe interno com o PDF renderizado e extrai seu conteúdo como bytes.
    """
    try:
        iframe = driver.find_element(By.ID, "frameBinario")
        src = iframe.get_attribute("src")

        session = requests.Session()
        for cookie in driver.get_cookies():
            session.cookies.set(cookie["name"], cookie["value"])

        headers = {
            "User-Agent": driver.execute_script("return navigator.userAgent;"),
            "Referer": "https://pje.tjba.jus.br/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam",
        }

        url = "https://pje.tjba.jus.br" + src
        response = session.get(url, headers=headers)
        if response.status_code == 200 and response.content.startswith(b"%PDF"):
            return response.content
        else:
            raise Exception(f"Resposta inválida: {response.status_code}")
    except Exception as e:
        print(f"[ERRO] Falha ao baixar PDF do iframe: {e}")
        return None


def salvar_pdf_local(pdf_bytes, processo_numero, metadados):
    """
    Salva o PDF extraído com um nome baseado no número do processo e tipo de documento.
    """
    nome_base = f"{processo_numero}__{metadados['documento_id']}__{_norm(metadados['descricao']).replace(' ', '_')}.pdf"
    os.makedirs("pdfs_extraidos", exist_ok=True)
    caminho = os.path.join("pdfs_extraidos", nome_base)
    with open(caminho, "wb") as f:
        f.write(pdf_bytes)
    print(f"[SALVO] {caminho}")
    return caminho


def fluxo_extrair_pdf_documento(driver, processo_numero):
    """
    Integra extração de metadados + leitura do PDF renderizado + salvamento estruturado.
    """
    metadados = extrair_metadados_documento(driver)
    pdf_bytes = baixar_pdf_binario(driver)

    if pdf_bytes:
        caminho = salvar_pdf_local(pdf_bytes, processo_numero, metadados)
        return {"ok": True, "arquivo": caminho, "metadados": metadados}
    else:
        return {"ok": False, "erro": "Não foi possível obter os bytes do PDF"}





@retry(max_retries=2)
def capturar_documento_timeline_filtrado(
    driver,
    numero_processo: str,
    busca_pesquisa: str,
    filtro_titulo: str = "peticao inicial",
    id_campo: str = "divTimeLine:txtPesquisa",
    xpath_botao: str = '//*[@id="divTimeLine:btnPesquisar"]',
    id_container: str = 'divTimeLine:eventosTimeLineElement'
) -> int:
    """
    Pesquisa documentos na timeline, abre cada um, baixa o PDF via iframe
    e extrai o texto com PyMuPDF. Se o download falhar, faz fallback para
    leitura da camada textLayer (PDF.js).
    """
    baixados = 0
    alvo_norm = _norm(filtro_titulo)

    # --- pesquisa na timeline -------------------------------------------------
    campo = wait.until(EC.element_to_be_clickable((By.ID, id_campo)))
    campo.clear(); campo.send_keys(busca_pesquisa)
    wait.until(EC.element_to_be_clickable((By.XPATH, xpath_botao))).click()
    time.sleep(1.5)

    container = wait.until(EC.presence_of_element_located((By.ID, id_container)))
    links_filtrados: list[WebElement] = [
        a for a in container.find_elements(By.TAG_NAME, "a")
        if alvo_norm in _norm(a.text)
    ]
    print(f"[TL] {len(links_filtrados)} documento(s) encontrados para captura")

    for idx, link in enumerate(links_filtrados, 1):
        try:
            driver.execute_script("arguments[0].click();", link)
            time.sleep(1)
            print(f"link n {idx} foi clicado: {link}")
            # --- iframe com PDF -------------------------------------------------
            iframe = wait.until(EC.presence_of_element_located((By.ID, "frameBinario")))
            raw_src = iframe.get_attribute("src")  # pode ser absoluto ou relativo

            # Monta URL completa apenas se necessário
            if raw_src.startswith("http"):
                full_url = raw_src
            else:
                base = urllib.parse.urlparse(driver.current_url)
                full_url = urllib.parse.urljoin(f"{base.scheme}://{base.netloc}", raw_src)

            texto_pdf = ""

            # 1) Tenta baixar diretamente o PDF ---------------------------------
            try:
                sess = requests.Session()
                for c in driver.get_cookies():
                    sess.cookies.set(c["name"], c["value"])
                resp = sess.get(full_url, timeout=30)
                if resp.status_code == 200 and resp.content.startswith(b"%PDF"):
                    doc = fitz.open(stream=resp.content, filetype="pdf")
                    texto_pdf = "\n".join(page.get_text() for page in doc)
                    doc.close()
                    print(f"   └─ ({idx}) PDF baixado via requests ({len(texto_pdf)} chars)")
                else:
                    print(f"   └─ ({idx}) Falha download PDF (status {resp.status_code})")
            except Exception as e_dl:
                print(f"   └─ ({idx}) Erro download PDF: {e_dl}")

            # 2) Fallback: capturar textLayer ------------------------------------
            if not texto_pdf.strip():
                driver.switch_to.frame(iframe)
                try:
                    text_layer = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "textLayer"))
                    )
                    spans = text_layer.find_elements(By.TAG_NAME, "span")
                    texto_pdf = "\n".join(
                        s.text.strip() for s in spans if s.text.strip()
                    )
                    print(f"   └─ ({idx}) Fallback textLayer ({len(texto_pdf)} chars)")
                finally:
                    driver.switch_to.default_content()

            # 3) Salva texto se existir -----------------------------------------
            if texto_pdf.strip():
                out_dir = os.path.join("documentos_capturados", numero_processo)
                os.makedirs(out_dir, exist_ok=True)
                fp = os.path.join(out_dir, f"captura_timeline_{idx}.txt")
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(texto_pdf)
                print(f"       ✔ Texto salvo em {fp}")
                baixados += 1
            else:
                print(f"       ⚠ Nenhum texto extraído do documento {idx}")

        except Exception as e:
            print(f"   └─ ({idx}) ERRO: {e}")
            save_screenshot(f"erro_timeline_{numero_processo}_{idx}")
            try:
                driver.switch_to.default_content()
            except:
                pass

    driver.switch_to.default_content()
    return baixados


def click_on_process(process_element):
    """
    Clica no elemento do processo e alterna para a nova janela.
    """
    try:
        original_handles = set(driver.window_handles)
        driver.execute_script(
            "arguments[0].scrollIntoView(true);", process_element)
        driver.execute_script("arguments[0].click();", process_element)
        print("Processo clicado com sucesso!")
        switch_to_new_window(original_handles)
    except Exception as e:
        save_exception_screenshot("click_on_process_exception.png")
        print(f"Erro ao clicar no processo. Erro: {e}")
        raise e


def get_process_list():
    """
    Retorna uma lista de elementos representando os processos encontrados.
    """
    try:
        process_xpath = "//processo-datalist-card"
        processes = wait.until(
            EC.presence_of_all_elements_located((By.XPATH, process_xpath)))
        print(f"Número de processos encontrados: {len(processes)}")
        return processes
    except Exception as e:
        save_exception_screenshot("get_process_list_exception.png")
        print(f"Erro ao obter a lista de processos. Erro: {e}")
        raise e


@retry()
def open_tag_page(tag: str):
    """
    Exemplo de ação principal que pesquisa os processos via etiqueta.
    """
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    original_handles = set(driver.window_handles)
    print(f"Handles originais das janelas: {original_handles}")
    click_element(
        xpath="/html/body/app-root/selector/div/div/div[1]/side-bar/nav/ul/li[5]/a")
    input_tag(tag)


def abrir_processos_na_etiqueta() -> list[tuple[str, WebElement]]:
    """
    Acessa o frame 'ngFrame', coleta todos os elementos de processo
    dentro da etiqueta atual e retorna uma lista de tuplas com:
    (número_formatado, elemento WebElement clicável do processo)
    """
    resultados = []

    driver.switch_to.default_content()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    print("Dentro do frame 'ngFrame'.")

    total_processos = len(get_process_list())
    for index in range(1, total_processos + 1):
        numero_formatado = "NÃO IDENTIFICADO"
        try:
            print(
                f"\nIniciando coleta do processo {index} de {total_processos}")
            process_xpath = f"(//processo-datalist-card)[{index}]//a/div/span[2]"
            process_element = wait.until(
                EC.element_to_be_clickable((By.XPATH, process_xpath)))
            numero_raw = process_element.text.strip()

            digits = re.sub(r'\D', '', numero_raw)
            match = re.match(
                r"(\d{7})(\d{2})(\d{4})(\d)(\d{2})(\d{4})", digits)
            if match:
                numero_formatado = f"{match.group(1)}-{match.group(2)}.{match.group(3)}.{match.group(4)}.{match.group(5)}.{match.group(6)}"
            else:
                numero_formatado = numero_raw

            print(f"Número do processo: {numero_formatado}")
            resultados.append((numero_formatado, process_element))

        except Exception as e:
            print(f"[ERRO] Falha ao processar índice {index}: {e}")
            save_screenshot(f"falha_coleta_proc_{index}")

    return resultados


def processos_em_lista(busca_pesq: str, filtro: str) -> tuple[list, list, list]:
    """
    Percorre todos os cards. Retorna:
      cards_ok, numeros_ok, numeros_falhos
    """
    cards_ok, nums_ok, nums_fail = [], [], []
    original_window = driver.current_window_handle

    processos = abrir_processos_na_etiqueta()
    total_processos = len(processos)

    for index, (numero_formatado, process_element) in enumerate(processos, start=1):
        try:
            print(f"\n[PROCESSO] {index}/{total_processos} → {numero_formatado}")

            # Abre processo em nova aba
            click_on_process(process_element)
            driver.switch_to.default_content()
            print("Saiu do frame 'ngFrame'")

            # Captura os documentos
            baixados = capturar_documento_timeline_filtrado(
                driver, numero_formatado, busca_pesq, filtro
            )
            print(f"[PROC] {numero_formatado} – capturas: {baixados}")

            # Fecha a aba e retorna para a principal
            driver.close()
            driver.switch_to.window(original_window)
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))

            cards_ok.append(numero_formatado)
            nums_ok.append(numero_formatado)

        except Exception as e:
            print(f"[FAIL] {numero_formatado}: {e}")
            save_screenshot(f"proc_fail_{numero_formatado}")
            nums_fail.append(numero_formatado)

            try:
                driver.close()
            except Exception:
                pass
            driver.switch_to.window(original_window)
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))

    driver.switch_to.default_content()
    return cards_ok, nums_ok, nums_fail



def abrir_processo(card):
    original = driver.current_window_handle
    driver.execute_script("arguments[0].click();", card)
    WebDriverWait(driver, 20).until(lambda d: len(d.window_handles) > 1)
    new = (set(driver.window_handles) - {original}).pop()
    driver.switch_to.window(new)
    print("[OK] Processo aberto em nova aba")
    return original

# ----------------------------------------------------------------------
# DOWNLOAD DE AUTO COMPLETO
# ----------------------------------------------------------------------


def baixar_autos(document_type: str):
    def click_css(sel): return driver.execute_script("arguments[0].click()", wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))))
    click_css(
        'a.btn-menu-abas.dropdown-toggle[title="Download autos do processo"]')
    Select(wait.until(EC.element_to_be_clickable((By.ID, "navbar:cbTipoDocumento"))))\
        .select_by_visible_text(document_type)
    click_css("#navbar\\:botoesDownload .btn-primary")
    print(f"[DL] Autos – {document_type}")
    time.sleep(3)

# ----------------------------------------------------------------------
# NOVA FUNÇÃO: downloadRequestedFileOnProcesses
# ----------------------------------------------------------------------


def download_requested_processes(process_numbers, etiqueta):
    resultados = {"nomeEtiqueta": etiqueta,
                  "ProcessosBaixados": [], "ProcessosNãoEncontrados": []}

    try:
        driver.get('https://pje.tjba.jus.br/pje/AreaDeDownload/listView.seam')
        wait.until(EC.frame_to_be_available_and_switch_to_it(
            (By.ID, 'ngFrame')))
        rows = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//table//tbody//tr")))
        baixados = set()

        for row in rows:
            proc = row.find_element(By.XPATH, "./td[1]").text.strip()
            if proc in process_numbers and proc not in baixados:
                try:
                    row.find_element(By.XPATH, "./td[last()]//button").click()
                    baixados.add(proc)
                    resultados["ProcessosBaixados"].append(proc)
                    print(f"[DL] autos de {proc} disparado")
                    time.sleep(2)
                except Exception as e:
                    print(f"[DL] falhou {proc}: {e}")

        faltantes = [p for p in process_numbers if p not in baixados]
        resultados["ProcessosNãoEncontrados"].extend(faltantes)

    except Exception as e:
        save_screenshot("download_area_exception")
        print(f"[ERR] área de download: {e}")

    os.makedirs(".logs", exist_ok=True)
    fn = f".logs/processos_download_{etiqueta}.json"
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"[DONE] resumo salvo em {fn}")
    return resultados


def downloadRequestedFileOnProcesses(process_numbers: list[str],
                                     etiqueta: str,
                                     search_term: str) -> dict:
    """
    Para cada número de processo:
      1. Abre a área de downloads e dispara o download completo.
      2. Dentro do processo, pesquisa na timeline e baixa cada doc
         que aparecer na lista de resultados.
    """
    resultados = {
        "nomeEtiqueta": etiqueta,
        "ProcessosBaixados": [],
        "ProcessosNãoEncontrados": [],
        "DocsFalhaTimeline": {}
    }

    for idx, num in enumerate(process_numbers, 1):
        try:
            print(f"\n[PROC] {idx}/{len(process_numbers)} – {num}")
            # Navega diretamente pela URL da área de download
            driver.get(
                "https://pje.tjba.jus.br/pje/AreaDeDownload/listView.seam")
            wait.until(EC.frame_to_be_available_and_switch_to_it(
                (By.ID, "ngFrame")))
            # Procurar linha do processo
            linha = wait.until(EC.presence_of_element_located(
                (By.XPATH, f"//tr[td[1][contains(.,'{num}')]]")))
            btn = linha.find_element(By.XPATH, ".//button")
            driver.execute_script("arguments[0].click();", btn)
            print("[OK] Download de autos disparado")
            resultados["ProcessosBaixados"].append(num)

            # -- Agora pesquisa na timeline do processo --
            driver.get(
                f"https://pje.tjba.jus.br/pje/Processo/consultaProcessoConsultasResumo.seam?processoNumero={num}")
            wait.until(EC.frame_to_be_available_and_switch_to_it(
                (By.ID, "timelineFrame")))
            campo = wait.until(EC.element_to_be_clickable(
                (By.ID, "divTimeLine:txtPesquisa")))
            campo.clear()
            campo.send_keys(search_term)
            wait.until(EC.element_to_be_clickable(
                (By.ID, "divTimeLine:btnPesquisar"))).click()

            container = wait.until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="divTimeLine:eventosTimeLineElement"]/div[4]/div[2]')))
            links = container.find_elements(By.TAG_NAME, "a")
            print(f"[INFO] {len(links)} links encontrados na timeline")

            falhas_doc = []
            print(links)
            time.sleep(10)
            for i, link in enumerate(links, 1):
                try:
                    driver.execute_script("arguments[0].click();", link)
                    btn_dl = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '//*[@id="detalheDocumento:downloadPJeDocs"]')))
                    driver.execute_script("arguments[0].click();", btn_dl)
                    print(f"   └─ Doc {i} baixado")
                    time.sleep(2)
                except Exception as e:
                    print(f"   └─ Falha ao baixar doc {i}: {e}")
                    falhas_doc.append(i)
            if falhas_doc:
                resultados["DocsFalhaTimeline"][num] = falhas_doc

            driver.switch_to.default_content()

        except TimeoutException:
            print("[ERR] Processo não encontrado na lista de downloads")
            resultados["ProcessosNãoEncontrados"].append(num)
        except Exception as e:
            save_screenshot(f"erro_process_{num}")
            print(f"[ERR] Falha inesperada em {num}: {e}")
            resultados["ProcessosNãoEncontrados"].append(num)

    # Persistência em JSON
    fn = f"processos_download_{etiqueta}.json"
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"[DONE] Resultados salvos em {fn}")
    return resultados

# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------


def main():
    load_dotenv()
    initialize_driver()
    try:
        login(os.getenv("USER"), os.getenv("PASSWORD"))
        select_profile(os.getenv("PROFILE"))
        open_tag_page("teste")

        cards, numeros = processos_em_lista(
            busca_pesq="petição inicial", filtro="petição inicial")
        resultados = download_requested_processes(
            process_numbers=numeros,
            etiqueta="repetidos temporario",
        )
        print(json.dumps(resultados, indent=2, ensure_ascii=False))
        time.sleep(5)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
