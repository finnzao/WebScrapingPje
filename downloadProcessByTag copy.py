import re
import json
import time
import os
from typing import Literal, Dict, List
from functools import wraps
from dotenv import load_dotenv

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, StaleElementReferenceException,
    ElementClickInterceptedException, NoSuchElementException
)

from utils.pje_automation import PjeConsultaAutomator

driver = None
wait = None

DocumentoNome = Literal[
    "ALEGAÇÕES FINAIS", "Acórdão", "Alvará Judicial", "Ato Ordinatório", "Certidão",
    "Certidão de publicação no DJe", "Decisão", "Despacho (63)", "Despacho (94)",
    "Diligência", "Documento de Comprovação", "Edital", "Embargos de Declaração",
    "Ementa", "INFORMAÇÃO", "INTIMAÇÃO", "Informação", "Intimação", "Intimação de Pauta",
    "Laudo Pericial", "Mandado", "Ofício", "Outros documentos", "Parecer do Ministerio Público",
    "Petição", "Petição Inicial", "Procuração", "Relatório", "Sentença", "Substabelecimento",
    "TERMO DE AUDIÊNCIA", "Voto"
]

TIPO_DOCUMENTOS: Dict[DocumentoNome, str] = {
    "ALEGAÇÕES FINAIS": "131", "Acórdão": "74", "Alvará Judicial": "122", "Ato Ordinatório": "67",
    "Certidão": "57", "Certidão de publicação no DJe": "285", "Decisão": "64", "Despacho (63)": "63",
    "Despacho (94)": "94", "Diligência": "59", "Documento de Comprovação": "53", "Edital": "121",
    "Embargos de Declaração": "23", "Ementa": "77", "INFORMAÇÃO": "118", "INTIMAÇÃO": "108",
    "Informação": "171", "Intimação": "60", "Intimação de Pauta": "71", "Laudo Pericial": "31",
    "Mandado": "103", "Ofício": "34", "Outros documentos": "93", "Parecer do Ministerio Público": "166",
    "Petição": "36", "Petição Inicial": "12", "Procuração": "161", "Relatório": "73",
    "Sentença": "62", "Substabelecimento": "51", "TERMO DE AUDIÊNCIA": "150", "Voto": "72"
}
def retry(max_retries=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (TimeoutException, StaleElementReferenceException) as e:
                    retries += 1
                    print(f"[RETRY] Tentativa {retries} para {func.__name__} falhou: {e}")
                    if retries >= max_retries:
                        print(f"[RETRY] Falha definitiva após {max_retries} tentativas.")
                        raise
        return wrapper
    return decorator

def save_exception_screenshot(filename):
    directory = ".logs/exception"
    os.makedirs(directory, exist_ok=True)
    filepath = os.path.join(directory, filename)
    driver.save_screenshot(filepath)
    print(f"[ERRO] Screenshot salvo em: {filepath}")

@retry()
def click_element(xpath: str = None, element_id: str = None, css_selector: str = None) -> None:
    if not xpath and not element_id and not css_selector:
        raise ValueError("Necessário informar ao menos um seletor.")

    def _try_click(by: By, selector: str, origem: str) -> bool:
        try:
            print(f"[CLICK] Tentando clicar via {origem}: {selector}")
            element = wait.until(EC.element_to_be_clickable((by, selector)))
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            try:
                element.click()
            except:
                driver.execute_script("arguments[0].click();", element)
            print(f"[CLICK] Sucesso via {origem}")
            return True
        except Exception as e:
            print(f"[CLICK] Falha via {origem}: {e}")
            return False

    if xpath and _try_click(By.XPATH, xpath, "XPATH"):
        return
    if element_id and _try_click(By.ID, element_id, "ID"):
        return
    if css_selector and _try_click(By.CSS_SELECTOR, css_selector, "CSS"):
        return

    save_exception_screenshot("click_element_falhou.png")
    raise NoSuchElementException("Falha ao clicar no elemento com os seletores informados.")

def switch_to_new_window(original_handles, timeout=20):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.window_handles) > len(original_handles)
        )
        new_handles = set(driver.window_handles) - original_handles
        if new_handles:
            new_window = new_handles.pop()
            driver.switch_to.window(new_window)
            print(f"[SWITCH] Alternado para nova janela: {new_window}")
            return new_window
        raise TimeoutException("Nova janela não foi encontrada.")
    except TimeoutException as e:
        save_exception_screenshot("switch_to_new_window_timeout.png")
        print("[SWITCH] Timeout ao tentar trocar para nova janela.")
        raise

def switch_to_original_window(original_handle):
    try:
        driver.switch_to.window(original_handle)
        print(f"[SWITCH] Retornado à janela original: {original_handle}")
    except Exception as e:
        save_exception_screenshot("switch_to_original_window_erro.png")
        print(f"[SWITCH] Falha ao retornar à janela original: {e}")
        raise

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

def input_tag(search_text):
    search_input = wait.until(EC.element_to_be_clickable((By.ID, "itPesquisarEtiquetas")))
    search_input.clear()
    search_input.send_keys(search_text)
    click_element(xpath="/html/body/app-root/selector/div/div/div[2]/right-panel/div/etiquetas/div[1]/div/div[1]/div[2]/div[1]/span/button[1]")
    time.sleep(1)
    print(f"Pesquisa realizada com o texto: {search_text}")
    click_element(xpath="/html/body/app-root/selector/div/div/div[2]/right-panel/div/etiquetas/div[1]/div/div[2]/ul/p-datalist/div/div/ul/li/div/li/div[2]/span/span")


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

def select_tipo_documento_por_nome(nome_documento: DocumentoNome) -> None:
    try:
        select_element = wait.until(
            EC.presence_of_element_located((By.ID, 'navbar:cbTipoDocumento'))
        )
        combo = Select(select_element)

        # Obtém o value do <option> usando o dicionário tipado
        tipo_value = TIPO_DOCUMENTOS.get(nome_documento)
        if not tipo_value:
            raise ValueError(
                f"Não existe mapeamento para o nome de documento '{nome_documento}' "
                f"no dicionário TIPO_DOCUMENTOS."
            )

        # Seleciona pelo atributo value (mais confiável do que texto visível)
        combo.select_by_value(tipo_value)
        print(f"Tipo de documento '{nome_documento}' (value={tipo_value}) selecionado com sucesso.")
        return True
    except:
        return False

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


def downloadProcessOnTagSearch(typeDocument: DocumentoNome) -> dict:
    relatorio = {
        "TodosOsProcessosBaixados": [],
        "ProcessosBaixadosDiretamente": [],
        "ProcessosBaixadosPaginaDeDownload": [],
        "ProcessosNãoEncontrados": []
    }

    driver.switch_to.default_content()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    processos = get_process_list()
    original_window = driver.current_window_handle

    for idx, proc_element in enumerate(processos, start=1):
        numero_raw = "NÃO IDENTIFICADO"
        try:
            numero_raw = proc_element.text.strip()
            digits = re.sub(r'\D', '', numero_raw)
            numero_formatado = (
                f"{digits[:7]}-{digits[7:9]}.{digits[9:13]}.{digits[13]}."
                f"{digits[14:16]}.{digits[16:]}"
            ) if len(digits) >= 17 else numero_raw

            print(f"\n[PROCESSO] {idx}/{len(processos)} → {numero_formatado}")
            relatorio["TodosOsProcessosBaixados"].append(numero_formatado)

            click_on_process(proc_element)
            driver.switch_to.default_content()
            click_element(css_selector='a.btn-menu-abas.dropdown-toggle')
            time.sleep(2)

            if select_tipo_documento_por_nome(typeDocument):
                try:
                    click_element(xpath="/html/body/div/div[1]/div/form/span/ul[2]/li[5]/div/div[5]/input")
                    time.sleep(5)
                    print(f"[DOWNLOAD DIRETO] Sucesso para: {numero_formatado}")
                    relatorio["ProcessosBaixadosDiretamente"].append(numero_formatado)
                except Exception as e:
                    print(f"[FILA DE DOWNLOAD] Documento grande ou erro. Será tratado na próxima etapa. {e}")
            else:
                print(f"[AVISO] Tipo de documento '{typeDocument}' não encontrado para: {numero_formatado}")
                relatorio["ProcessosNãoEncontrados"].append(numero_formatado)

            driver.close()
            driver.switch_to.window(original_window)
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
        except Exception as e:
            print(f"[ERRO] Falha ao processar o processo '{numero_raw}': {e}")
            relatorio["ProcessosNãoEncontrados"].append(numero_raw)
            try:
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(original_window)
                    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
            except:
                pass

    return relatorio

def download_requested_processes(relatorio_inicial: dict, etiqueta: str) -> dict:
    """
    Acessa a Área de Download e tenta baixar documentos que não foram baixados diretamente.
    Atualiza o relatório final com sucesso ou erro dos downloads pendentes.
    """
    print("\n[AÇÃO] Acessando página de download para concluir documentos pendentes...")
    try:
        driver.get('https://pje.tjba.jus.br/pje/AreaDeDownload/listView.seam')
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'table')))
        rows = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//table//tbody//tr")))
        print(f"[INFO] {len(rows)} registros encontrados na fila de download.")

        for row in rows:
            try:
                proc_num = row.find_element(By.XPATH, "./td[1]").text.strip()
                if proc_num in relatorio_inicial["TodosOsProcessosBaixados"] and \
                   proc_num not in relatorio_inicial["ProcessosBaixadosDiretamente"] and \
                   proc_num not in relatorio_inicial["ProcessosBaixadosPaginaDeDownload"]:
                    try:
                        download_button = row.find_element(By.XPATH, "./td[last()]//button")
                        driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
                        download_button.click()
                        time.sleep(3)
                        relatorio_inicial["ProcessosBaixadosPaginaDeDownload"].append(proc_num)
                        if proc_num in relatorio_inicial["ProcessosNãoEncontrados"]:
                            relatorio_inicial["ProcessosNãoEncontrados"].remove(proc_num)
                        print(f"[DOWNLOAD FILA] Concluído: {proc_num}")
                    except Exception as e:
                        print(f"[ERRO DOWNLOAD FILA] Falha ao baixar {proc_num}: {e}")
            except Exception as e:
                print(f"[ERRO] Linha da tabela inválida: {e}")

        driver.switch_to.default_content()

    except Exception as e:
        save_exception_screenshot("download_requested_processes_exception.png")
        print(f"[FALHA] Não foi possível concluir downloads da fila. Erro: {e}")

    # Grava o relatório final
    os.makedirs(".logs", exist_ok=True)
    json_filename = f".logs/processos_download_{etiqueta}.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(relatorio_inicial, f, ensure_ascii=False, indent=4)
    print(f"\n✅ Relatório final salvo em: {json_filename}")

    return relatorio_inicial
def iniciar_automacao():
    """
    Carrega variáveis de ambiente, inicializa Selenium via PjeConsultaAutomator
    e realiza login + seleção de perfil.
    """
    print("\n[INICIANDO] Carregando variáveis e inicializando automação...")
    load_dotenv()
    global driver, wait

    automator = PjeConsultaAutomator()
    driver = automator.driver
    wait = automator.wait

    user = os.getenv("USER")
    password = os.getenv("PASSWORD")
    profile = os.getenv("PROFILE")

    automator.login(user, password)
    automator.select_profile(profile=profile)

    print("[INICIADO] Login realizado com sucesso.")
    return automator


def main():
    etiqueta = "teste"
    tipo_documento = "Sentença"

    automator = iniciar_automacao()
    try:
        search_on_tag(etiqueta)

        # Primeira etapa: Baixa o máximo possível direto da página do processo
        relatorio_inicial = downloadProcessOnTagSearch(tipo_documento)

        # Segunda etapa: Tenta baixar o restante pela área de download
        relatorio_final = download_requested_processes(relatorio_inicial, etiqueta)

        print("\n🔎 Resumo final:")
        print(json.dumps(relatorio_final, indent=2, ensure_ascii=False))

        time.sleep(3)

    finally:
        automator.close()
        print("\n[ENCERRADO] Navegador fechado. Automação finalizada.")

if __name__ == "__main__":
    main()
