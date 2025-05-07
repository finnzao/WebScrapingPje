#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automação PJe – download em massa de documentos
-----------------------------------------------
• Login, perfil, navegação por etiqueta
• Busca por processos, download dos autos
• Dentro do processo, pesquisa por termo na timeline
  e download de cada documento correspondente
"""

import os, re, time, json
from functools import wraps
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, StaleElementReferenceException,
    ElementClickInterceptedException, NoSuchElementException,
)

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
                    print(f"[WARN] {func.__name__}: tentativa {attempt} falhou → {e}")
        return wrapper
    return decorator

def initialize_driver():
    global driver, wait
    chrome_options = webdriver.ChromeOptions()
    dl_dir = os.path.join(os.path.expanduser("~"), "Downloads", "processosBaixadosEtiqueta")
    os.makedirs(dl_dir, exist_ok=True)
    chrome_options.add_experimental_option("prefs", {
        "plugins.always_open_pdf_externally": True,
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
    wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(username)
    wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
    wait.until(EC.element_to_be_clickable((By.ID, "kc-login"))).click()
    driver.switch_to.default_content()
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "dropdown-toggle")))
    print("[OK] Login efetuado")

@retry()
def select_profile(profile_text: str):
    dropdown = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "dropdown-toggle")))
    dropdown.click()
    opt = wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[contains(text(),'{profile_text}')]")))
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
        raise ValueError("Informe ao menos um seletor: xpath, element_id ou css_selector.")

    def _try_click(by: By, selector: str, desc: str) -> bool:
        """Espera o elemento ficar clicável e tenta clique normal + JavaScript."""
        try:
            print(f"[click_element] Tentando clicar via {desc}: {selector}")
            element = wait.until(EC.element_to_be_clickable((by, selector)))
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            try:
                element.click()
                print(f"Elemento clicado com sucesso ({desc}): {selector}")
                return True
            except (ElementClickInterceptedException, Exception) as e:
                print(f"Erro ao clicar normalmente via {desc}: {e}. Tentando JavaScript...")
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
            print(f"[click_element] Tentando CSS SELECTOR (JS) via: {css_selector}")
            # Se quiser esperar ficar 'clicável' pela API do Selenium:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector)))
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
            print(f"Elemento clicado com sucesso (CSS SELECTOR + JS): {css_selector}")
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


def switch_to_new_window(original_handles, timeout=20):
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
            raise TimeoutException("Nova janela não foi encontrada dentro do tempo especificado.")
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
        print(f"Erro ao retornar para a janela original. Captura de tela salva. Erro: {e}")
        raise e


def input_tag(search_text):
    search_input = wait.until(EC.element_to_be_clickable((By.ID, "itPesquisarEtiquetas")))
    search_input.clear()
    search_input.send_keys(search_text)
    click_element(xpath="/html/body/app-root/selector/div/div/div[2]/right-panel/div/etiquetas/div[1]/div/div[1]/div[2]/div[1]/span/button[1]")
    time.sleep(1)
    print(f"Pesquisa realizada com o texto: {search_text}")
    click_element(xpath="/html/body/app-root/selector/div/div/div[2]/right-panel/div/etiquetas/div[1]/div/div[2]/ul/p-datalist/div/div/ul/li/div/li/div[2]/span/span")



from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

@retry(max_retries=2)
def baixar_documentos_timeline(busca: str,
                               frame_id: str = "timelineFrame",
                               xpath_campo: str = '//*[@id="divTimeLine:txtPesquisa"]',
                               xpath_botao: str = '//*[@id="divTimeLine:btnPesquisar"]',
                               xpath_container_links: str = '//*[@id="divTimeLine:eventosTimeLineElement"]/div[4]/div[2]',
                               xpath_botao_download: str = '//*[@id="detalheDocumento:downloadPJeDocs"]') -> int:
    """
    Faz uma pesquisa na timeline e baixa todos os documentos retornados.
    
    Parâmetros
    ----------
    busca : str
        Termo a ser digitado no campo de pesquisa da timeline.
    frame_id : str
        ID do iframe da timeline (padrão 'timelineFrame').
    Demais parâmetros
        XPaths dos elementos essenciais, expostos para fácil ajuste se o TJBA alterar a página.
    
    Retorno
    -------
    int
        Quantidade de documentos baixados.
    """
    baixados = 0

    # 1. Entrar no frame da timeline
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, frame_id)))

    # 2. Preencher campo de pesquisa e acionar busca
    campo = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_campo)))
    campo.clear()
    campo.send_keys(busca)
    wait.until(EC.element_to_be_clickable((By.XPATH, xpath_botao))).click()

    # 3. Aguardar lista de links (<a>) e coletá‑los
    container = wait.until(EC.presence_of_element_located((By.XPATH, xpath_container_links)))
    links = container.find_elements(By.TAG_NAME, "a")
    print(f"[TL] {len(links)} link(s) encontrados para '{busca}'")

    # 4. Percorrer links na ordem, clicando e baixando
    for idx, link in enumerate(links, 1):
        try:
            driver.execute_script("arguments[0].scrollIntoView(true);", link)
            driver.execute_script("arguments[0].click();", link)

            # Botão de download dentro do detalhe do documento
            botao_dl = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_botao_download)))
            driver.execute_script("arguments[0].click();", botao_dl)
            baixados += 1
            print(f"    └─ Documento {idx} baixado com sucesso")
            time.sleep(2)  # pequena pausa para não sobrecarregar o servidor
        except (TimeoutException, ElementClickInterceptedException) as e:
            print(f"    └─ Falha ao baixar o documento {idx}: {e}")
            save_screenshot(f"falha_doc_timeline_{idx}")

    # 5. Voltar ao conteúdo principal para a chamada que invocou esta função
    driver.switch_to.default_content()
    return baixados


def click_on_process(process_element):
    """
    Clica no elemento do processo e alterna para a nova janela.
    """
    try:
        original_handles = set(driver.window_handles)
        driver.execute_script("arguments[0].scrollIntoView(true);", process_element)
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
        processes = wait.until(EC.presence_of_all_elements_located((By.XPATH, process_xpath)))
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
    click_element(xpath="/html/body/app-root/selector/div/div/div[1]/side-bar/nav/ul/li[5]/a")
    input_tag(tag)

def processos_em_lista() -> list:
    error_processes = []
    process_numbers = []
    original_window = driver.current_window_handle

    driver.switch_to.default_content()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    print("Dentro do frame 'ngFrame'.")

    total_processes = len(get_process_list())
    for index in range(1, total_processes + 1):
        raw_process_number = "NÃO IDENTIFICADO"
      
        print(f"\nIniciando o download para o processo {index} de {total_processes}")
        process_xpath = f"(//processo-datalist-card)[{index}]//a/div/span[2]"
        process_element = wait.until(EC.element_to_be_clickable((By.XPATH, process_xpath)))
        raw_process_number = process_element.text.strip()
        # Ajuste do número do processo no formato XXXXXX-XX.XXXX.X.XX.XXXX
        just_digits = re.sub(r'\D', '', raw_process_number)
        if len(just_digits) >= 17:
            process_number = (
                f"{just_digits[:7]}-{just_digits[7:9]}."
                f"{just_digits[9:13]}.{just_digits[13]}."
                f"{just_digits[14:16]}.{just_digits[16:]}"
            )
        else:
            process_number = raw_process_number
        print(f"Número do processo: {process_number}")
        process_numbers.append(process_number)
        click_on_process(process_element)
        driver.switch_to.default_content()
        print("Saiu do frame 'ngFrame'.")
        
        baixar_documentos_timeline(busca="Petição inicial")

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
    click_css = lambda sel: driver.execute_script("arguments[0].click()", wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))))
    click_css('a.btn-menu-abas.dropdown-toggle[title="Download autos do processo"]')
    Select(wait.until(EC.element_to_be_clickable((By.ID, "navbar:cbTipoDocumento"))))\
        .select_by_visible_text(document_type)
    click_css("#navbar\\:botoesDownload .btn-primary")
    print(f"[DL] Autos – {document_type}")
    time.sleep(3)

# ----------------------------------------------------------------------
# NOVA FUNÇÃO: downloadRequestedFileOnProcesses
# ----------------------------------------------------------------------
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
            driver.get("https://pje.tjba.jus.br/pje/AreaDeDownload/listView.seam")
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ngFrame")))
            # Procurar linha do processo
            linha = wait.until(EC.presence_of_element_located(
                (By.XPATH, f"//tr[td[1][contains(.,'{num}')]]")))
            btn = linha.find_element(By.XPATH, ".//button")
            driver.execute_script("arguments[0].click();", btn)
            print("[OK] Download de autos disparado")
            resultados["ProcessosBaixados"].append(num)

            # -- Agora pesquisa na timeline do processo --
            driver.get(f"https://pje.tjba.jus.br/pje/Processo/consultaProcessoConsultasResumo.seam?processoNumero={num}")
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "timelineFrame")))
            campo = wait.until(EC.element_to_be_clickable((By.ID, "divTimeLine:txtPesquisa")))
            campo.clear()
            campo.send_keys(search_term)
            wait.until(EC.element_to_be_clickable((By.ID, "divTimeLine:btnPesquisar"))).click()

            container = wait.until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="divTimeLine:eventosTimeLineElement"]/div[4]/div[2]')))
            links = container.find_elements(By.TAG_NAME, "a")
            print(f"[INFO] {len(links)} links encontrados na timeline")

            falhas_doc = []
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
        open_tag_page("Repetidos")
        cards = processos_em_lista()
        numeros = []
        for card in cards:
            raw = card.text.strip()
            num = re.sub(r"\D", "", raw)
            num = f"{num[:7]}-{num[7:9]}.{num[9:13]}.{num[13]}.{num[14:16]}.{num[16:]}"
            numeros.append(num)
        resultados = downloadRequestedFileOnProcesses(
            process_numbers=numeros,
            etiqueta="Repetidos",
            search_term="Petição Inicial"
        )
        print(json.dumps(resultados, indent=2, ensure_ascii=False))
        time.sleep(5)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
