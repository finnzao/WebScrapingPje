# downloadProcessByTag.py
import re
import json
import time
import os
from datetime import datetime
from typing import Literal, Dict, List
from functools import wraps
from dotenv import load_dotenv

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)

from utils.pje_automation import PjeConsultaAutomator

# ----------------------------------------------------------------------
# VARIÁVEIS GLOBAIS
# ----------------------------------------------------------------------
driver = None
wait = None

# ----------------------------------------------------------------------
# CONFIGURAÇÃO DE LOG
# ----------------------------------------------------------------------
LOG_PATH = ".logs/logs_execucao/execucao_log.txt"
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

def registrar_log(mensagem: str, console: bool = True):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{timestamp}] {mensagem}"
    if console:
        print(linha)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(linha + "\n")

# ----------------------------------------------------------------------
# CONSTANTES
# ----------------------------------------------------------------------
DocumentoNome = Literal[
    "Sentença", "Decisão", "Despacho (63)", "Despacho (94)", "Certidão",
    "Petição Inicial", "Intimação", "Ofício", "Relatório", "Acórdão", "Denúncia",
    "Outros documentos", "Parecer do Ministerio Público", "Laudo Pericial",
    "Mandado", "Procuração", "TERMO DE AUDIÊNCIA", "Ato Ordinatório"
]

TIPO_DOCUMENTOS: Dict[DocumentoNome, str] = {
    "Sentença": "62", "Decisão": "64", "Despacho (63)": "63", "Despacho (94)": "94",
    "Certidão": "57", "Petição Inicial": "12", "Intimação": "60", "Ofício": "34",
    "Relatório": "73", "Acórdão": "74", "Denúncia": "15", "Outros documentos": "93",
    "Parecer do Ministerio Público": "166", "Laudo Pericial": "31", "Mandado": "103",
    "Procuração": "161", "TERMO DE AUDIÊNCIA": "150", "Ato Ordinatório": "67"
}

# ----------------------------------------------------------------------
# UTILITÁRIOS
# ----------------------------------------------------------------------
def retry(max_retries=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (TimeoutException, StaleElementReferenceException) as e:
                    registrar_log(f"[RETRY] Tentativa {attempt} falhou: {e}")
                    if attempt == max_retries:
                        raise
        return wrapper
    return decorator

def save_exception_screenshot(filename):
    path = os.path.join(".logs", "exception", filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    driver.save_screenshot(path)
    registrar_log(f"[ERRO] Screenshot salvo: {path}")

@retry()
def click_element(xpath: str = None, element_id: str = None,
                  css_selector: str = None, js_path: str = None) -> None:
    registrar_log(f"Tentando clicar no elemento...")
    def _try_click(by, value):
        try:
            el = wait.until(EC.element_to_be_clickable((by, value)))
            driver.execute_script("arguments[0].scrollIntoView(true);", el)
            el.click()
            return True
        except Exception as e:
            registrar_log(f"[FALHA] Click normal falhou: {e}")
            return False
    if xpath and _try_click(By.XPATH, xpath): return
    if element_id and _try_click(By.ID, element_id): return
    if css_selector and _try_click(By.CSS_SELECTOR, css_selector): return
    if js_path:
        js_code = f"""
        const el = document.querySelector("{js_path}");
        if (el) {{
            el.scrollIntoView();
            el.click();
        }} else {{
            throw new Error("Elemento não encontrado via JS PATH");
        }}
        """
        driver.execute_script(js_code)
        return
    save_exception_screenshot("click_element_exception.png")
    raise NoSuchElementException("Não foi possível clicar no elemento.")

# ----------------------------------------------------------------------
# FUNÇÕES DE NEGÓCIO
# ----------------------------------------------------------------------
def select_tipo_documento_por_nome(nome_documento: DocumentoNome) -> bool:
    try:
        select_element = wait.until(EC.presence_of_element_located((By.ID, 'navbar:cbTipoDocumento')))
        combo = Select(select_element)
        tipo_value = TIPO_DOCUMENTOS.get(nome_documento)
        if not tipo_value:
            return False
        combo.select_by_value(tipo_value)
        return True
    except:
        return False

def input_tag(search_text):
    search_input = wait.until(EC.element_to_be_clickable((By.ID, "itPesquisarEtiquetas")))
    search_input.clear()
    search_input.send_keys(search_text)
    click_element(xpath="/html/body/app-root/selector/div/div/div[2]/right-panel/div/etiquetas/div[1]/div/div[1]/div[2]/div[1]/span/button[1]")
    time.sleep(1)
    print(f"Pesquisa realizada com o texto: {search_text}")
    click_element(xpath="/html/body/app-root/selector/div/div/div[2]/right-panel/div/etiquetas/div[1]/div/div[2]/ul/p-datalist/div/div/ul/li/div/li/div[2]/span/span")

@retry()
def search_on_tag(search):
    """
    Exemplo de ação principal que pesquisa os processos via etiqueta.
    """
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    original_handles = set(driver.window_handles)
    print(f"Handles originais das janelas: {original_handles}")
    click_element(xpath="/html/body/app-root/selector/div/div/div[1]/side-bar/nav/ul/li[5]/a")
    input_tag(search)


@retry()
def get_process_list():
    return wait.until(EC.presence_of_all_elements_located((By.XPATH, "//processo-datalist-card")))

def click_on_process(process_element):
    original_handles = set(driver.window_handles)
    driver.execute_script("arguments[0].scrollIntoView(true);", process_element)
    driver.execute_script("arguments[0].click();", process_element)
    WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > len(original_handles))
    new_window = list(set(driver.window_handles) - original_handles)[0]
    driver.switch_to.window(new_window)

def downloadProcessOnTagSearch(typeDocument: DocumentoNome) -> dict:
    registrar_log(f"Iniciando busca e download de processos com documento '{typeDocument}'...")
    resultados = {
        "TodosProcessosEncontrados": [],
        "ProcessosComDownloadDireto": [],
        "ProcessosSemDocumento": [],
        "ProcessosComErro": []
    }

    driver.switch_to.default_content()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))

    processos = get_process_list()
    registrar_log(f"{len(processos)} processos encontrados.")
    original_window = driver.current_window_handle

    for idx, card in enumerate(processos, 1):
        try:
            raw_text = card.text.splitlines()[0]
            digits = re.sub(r'\D', '', raw_text)
            proc_num = (
                f"{digits[:7]}-{digits[7:9]}.{digits[9:13]}.{digits[13]}."
                f"{digits[14:16]}.{digits[16:]}"
            ) if len(digits) >= 17 else raw_text

            registrar_log(f"[{idx}] Acessando processo: {proc_num}")
            resultados["TodosProcessosEncontrados"].append(proc_num)

            click_on_process(card)
            driver.switch_to.default_content()

            click_element(css_selector='a.btn-menu-abas.dropdown-toggle')
            time.sleep(1)

            if select_tipo_documento_por_nome(typeDocument):
                try:
                    click_element(xpath="/html/body/div/div[1]/div/form/span/ul[2]/li[5]/div/div[5]/input")
                    resultados["ProcessosComDownloadDireto"].append(proc_num)
                    registrar_log(f"[OK] Download direto: {proc_num}")
                    time.sleep(3)
                except:
                    resultados["ProcessosSemDocumento"].append(proc_num)
                    registrar_log(f"[FALHA] Botão de download não clicável: {proc_num}")
            else:
                resultados["ProcessosSemDocumento"].append(proc_num)
                registrar_log(f"[FALHA] Documento não disponível: {proc_num}")

            driver.close()
            driver.switch_to.window(original_window)
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))

        except Exception as e:
            registrar_log(f"[ERRO] Falha ao processar {raw_text}: {e}")
            resultados["ProcessosComErro"].append(raw_text)
            try:
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(original_window)
                    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
            except: pass

    return resultados

def download_requested_processes(resultados: dict, etiqueta: str) -> dict:
    registrar_log("Iniciando etapa de download via Área de Download...")
    final = {
        "nomeEtiqueta": etiqueta,
        "ProcessosComDownloadDireto": resultados["ProcessosComDownloadDireto"],
        "ProcessosBaixadosNaFila": [],
        "ProcessosSemDownloadCompleto": resultados["ProcessosSemDocumento"][:],
        "ProcessosComErro": resultados["ProcessosComErro"]
    }
    driver.get('https://pje.tjba.jus.br/pje/AreaDeDownload/listView.seam')
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    rows = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//table//tbody//tr")))
    registrar_log(f"{len(rows)} linhas carregadas na área de download.")

    for row in rows:
        proc_num = row.find_element(By.XPATH, "./td[1]").text.strip()
        if proc_num in resultados["TodosProcessosEncontrados"] and proc_num not in final["ProcessosComDownloadDireto"]:
            try:
                btn = row.find_element(By.XPATH, "./td[last()]//button")
                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                btn.click()
                final["ProcessosBaixadosNaFila"].append(proc_num)
                if proc_num in final["ProcessosSemDownloadCompleto"]:
                    final["ProcessosSemDownloadCompleto"].remove(proc_num)
                registrar_log(f"[OK] Download via fila: {proc_num}")
                time.sleep(2)
            except:
                registrar_log(f"[FALHA] Download na fila falhou: {proc_num}")

    # JSON detalhado
    path = f".logs/processos_download_{etiqueta}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=4, ensure_ascii=False)

    return final

def salvar_resumo_automacao(etiqueta, tipo_documento, relatorio_final, inicio, fim):
    resumo = {
        "etiqueta": etiqueta,
        "documento": tipo_documento,
        "tempo_total_segundos": round(fim - inicio, 2),
        "processos_total": len(relatorio_final.get("ProcessosComDownloadDireto", [])) +
                           len(relatorio_final.get("ProcessosBaixadosNaFila", [])) +
                           len(relatorio_final.get("ProcessosSemDownloadCompleto", [])),
        "baixados_direto": len(relatorio_final.get("ProcessosComDownloadDireto", [])),
        "baixados_na_fila": len(relatorio_final.get("ProcessosBaixadosNaFila", [])),
        "nao_baixados": len(relatorio_final.get("ProcessosSemDownloadCompleto", [])),
        "com_erro": len(relatorio_final.get("ProcessosComErro", [])),
        "data_execucao": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    path = f".logs/automacao_resumo_{etiqueta}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(resumo, f, indent=4, ensure_ascii=False)
    registrar_log(f"Resumo salvo: {path}")
    return path

# ----------------------------------------------------------------------
# BOOTSTRAP
# ----------------------------------------------------------------------
def iniciar_automacao():
    load_dotenv()
    global driver, wait
    automator = PjeConsultaAutomator()
    driver = automator.driver
    wait = automator.wait
    automator.login(os.getenv("USER"), os.getenv("PASSWORD"))
    automator.select_profile(profile=os.getenv("PROFILE"))
    return automator

def main():
    etiqueta = "saneamento"
    tipo_documento = "Sentença"
    inicio = time.time()

    automator = iniciar_automacao()
    try:
        search_tag = etiqueta
        search_on_tag(search_tag)
        resultado = downloadProcessOnTagSearch(tipo_documento)
        relatorio = download_requested_processes(resultado, etiqueta)
        fim = time.time()
        salvar_resumo_automacao(etiqueta, tipo_documento, relatorio, inicio, fim)
    finally:
        automator.close()

if __name__ == "__main__":
    main()
