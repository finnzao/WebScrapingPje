# downloadProcessByTag.py
import re
import json
import time
import os

from typing import Literal, Dict
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
    NoSuchElementException,
)

from utils.pje_automation import PjeConsultaAutomator

driver = None
wait = None

DocumentoNome = Literal[
    "ALEGAÇÕES FINAIS",
    "Acórdão",
    "Alvará Judicial",
    "Ato Ordinatório",
    "Certidão",
    "Certidão de publicação no DJe",
    "Decisão",
    "Despacho (63)",
    "Despacho (94)",
    "Diligência",
    "Documento de Comprovação",
    "Edital",
    "Embargos de Declaração",
    "Ementa",
    "INFORMAÇÃO",
    "INTIMAÇÃO",
    "Informação",
    "Intimação",
    "Intimação de Pauta",
    "Laudo Pericial",
    "Mandado",
    "Ofício",
    "Outros documentos",
    "Parecer do Ministerio Público",
    "Petição",
    "Petição Inicial",
    "Procuração",
    "Relatório",
    "Sentença",
    "Substabelecimento",
    "TERMO DE AUDIÊNCIA",
    "Voto",
]

TIPO_DOCUMENTOS: Dict[DocumentoNome, str] = {
    "ALEGAÇÕES FINAIS": "131",
    "Acórdão": "74",
    "Alvará Judicial": "122",
    "Ato Ordinatório": "67",
    "Certidão": "57",
    "Certidão de publicação no DJe": "285",
    "Decisão": "64",
    "Despacho (63)": "63",
    "Despacho (94)": "94",
    "Diligência": "59",
    "Documento de Comprovação": "53",
    "Edital": "121",
    "Embargos de Declaração": "23",
    "Ementa": "77",
    "INFORMAÇÃO": "118",
    "INTIMAÇÃO": "108",
    "Informação": "171",
    "Intimação": "60",
    "Intimação de Pauta": "71",
    "Laudo Pericial": "31",
    "Mandado": "103",
    "Ofício": "34",
    "Outros documentos": "93",
    "Parecer do Ministerio Público": "166",
    "Petição": "36",
    "Petição Inicial": "12",
    "Procuração": "161",
    "Relatório": "73",
    "Sentença": "62",
    "Substabelecimento": "51",
    "TERMO DE AUDIÊNCIA": "150",
    "Voto": "72",
}


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

def retry(max_retries=2):
    """
    Decorador para tentar novamente a execução de uma função em caso de exceção.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (TimeoutException, StaleElementReferenceException) as e:
                    retries += 1
                    print(f"Tentativa {retries} falhou com erro: {e}. Tentando novamente...")
                    if retries >= max_retries:
                        raise TimeoutException(
                            f"Falha ao executar {func.__name__} após {max_retries} tentativas"
                        )
        return wrapper
    return decorator

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


@retry()
def click_element(
    xpath: str = None,
    element_id: str = None,
    css_selector: str = None,
    js_path: str = None
) -> None:
    if not xpath and not element_id and not css_selector and not js_path:
        raise ValueError("Informe ao menos um seletor: xpath, element_id, css_selector ou js_path.")

    def _try_click(by: By, selector: str, desc: str) -> bool:
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

    if xpath and _try_click(By.XPATH, xpath, "XPATH"):
        return

    if element_id and _try_click(By.ID, element_id, "ID"):
        return

    if css_selector and _try_click(By.CSS_SELECTOR, css_selector, "CSS SELECTOR"):
        return

    if js_path:
        try:
            print(f"[click_element] Tentando clicar via JS PATH: {js_path}")
            js_code = f"""
                const el = document.querySelector("{js_path}");
                if (el) {{
                    el.scrollIntoView();
                    el.click();
                }} else {{
                    throw new Error("Elemento não encontrado via JS PATH: {js_path}");
                }}
            """
            driver.execute_script(js_code)
            print(f"Elemento clicado com sucesso (JS PATH): {js_path}")
            return
        except Exception as ex:
            print(f"Falha ao tentar clicar via JS PATH: {ex}")

    # Se falhou em todos os métodos
    save_exception_screenshot("click_element_exception.png")
    msg = (
        f"Não foi possível clicar no elemento usando XPATH='{xpath}', "
        f"ID='{element_id}', CSS SELECTOR='{css_selector}', ou JS PATH='{js_path}'."
    )
    print(msg)
    raise NoSuchElementException(msg)



@retry()
def search_process(classeJudicial='', nomeParte='', numOrgaoJustica='0216', numeroOAB='', estadoOAB=''):
    """
    Exemplo de função especializada para pesquisar processo dentro do PJe
    (não está no pje_automation, portanto fica aqui).
    """
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    icon_search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'li#liConsultaProcessual i.fas')))
    icon_search_button.click()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'frameConsultaProcessual')))
    elemento_num_orgao = wait.until(
        EC.presence_of_element_located((By.ID, 'fPP:numeroProcesso:NumeroOrgaoJustica'))
    )
    elemento_num_orgao.send_keys(numOrgaoJustica)

    # OAB
    if estadoOAB:
        elemento_num_oab = wait.until(EC.presence_of_element_located((By.ID, 'fPP:decorationDados:numeroOAB')))
        elemento_num_oab.send_keys(numeroOAB)
        elemento_estados_oab = wait.until(
            EC.presence_of_element_located((By.ID, 'fPP:decorationDados:ufOABCombo'))
        )
        lista_estados_oab = Select(elemento_estados_oab)
        lista_estados_oab.select_by_value(estadoOAB)

    consulta_classe = wait.until(EC.presence_of_element_located((By.ID, 'fPP:j_id245:classeJudicial')))
    consulta_classe.send_keys(classeJudicial)

    elemento_nome_parte = wait.until(EC.presence_of_element_located((By.ID, 'fPP:j_id150:nomeParte')))
    elemento_nome_parte.send_keys(nomeParte)

    btn_procurar = wait.until(EC.presence_of_element_located((By.ID, 'fPP:searchProcessos')))
    btn_procurar.click()


@retry()
def preencher_formulario(numProcesso=None, Comp=None, Etiqueta=None):
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.CLASS_NAME, 'ng-frame')))
    if numProcesso:
        num_processo_input = wait.until(EC.presence_of_element_located((By.ID, "itNrProcesso")))
        driver.execute_script("arguments[0].scrollIntoView(true);", num_processo_input)
        num_processo_input.clear()
        num_processo_input.send_keys(numProcesso)
    if Comp:
        competencia_input = wait.until(EC.presence_of_element_located((By.ID, "itCompetencia")))
        driver.execute_script("arguments[0].scrollIntoView(true);", competencia_input)
        competencia_input.clear()
        competencia_input.send_keys(Comp)
    if Etiqueta:
        etiqueta_input = wait.until(EC.presence_of_element_located((By.ID, "itEtiqueta")))
        driver.execute_script("arguments[0].scrollIntoView(true);", etiqueta_input)
        etiqueta_input.clear()
        etiqueta_input.send_keys(Etiqueta)

    pesquisar_xpath = "//button[text()='Pesquisar']"
    click_element(xpath=pesquisar_xpath)
    print("Formulário preenchido e pesquisa iniciada com sucesso!")
    time.sleep(10)

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

@retry()
def select_tipo_documento(tipoDocumento):
    """
    Seleciona o tipo de documento no dropdown com base no valor informado.
    """
    try:
        select_element = wait.until(EC.presence_of_element_located((By.ID, 'navbar:cbTipoDocumento')))
        combo = Select(select_element)
        combo.select_by_visible_text(tipoDocumento)
        print(f"Tipo de documento '{tipoDocumento}' selecionado com sucesso.")
    except Exception as e:
        save_exception_screenshot("select_tipo_documento_exception.png")
        print(f"Erro ao selecionar o tipo de documento. Captura de tela salva. Erro: {e}")
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

def wait_for_download_screen(timeout=30):
    """
    Aguarda até que a tela de carregamento apareça e depois suma, sinalizando
    que o download foi concluído.
    Se não aparecer ou não sumir dentro do 'timeout', lança TimeoutException.
    """
    download_spinner_xpath = "//*[@id='_viewRoot:status.start']/div/div[2]/div/div"
    try:
        # 1) Tenta aguardar a tela de carregamento ficar visível.
        #    Se ela não aparece rapidamente, podemos ignorar essa etapa.
        wait.until(
            EC.visibility_of_element_located((By.XPATH, download_spinner_xpath)),
            message="Tela de carregamento não apareceu",
            timeout=5  # pode ser menor, já que às vezes não aparece
        )
    except TimeoutException:
        # Caso não apareça em 5s, pode não ter spinner neste processo
        print("A tela de carregamento não apareceu. Prosseguindo assim mesmo...")

    # 2) Aguarda a tela de carregamento sumir (ficar invisível)
    wait.until(
        EC.invisibility_of_element_located((By.XPATH, download_spinner_xpath)),
        message="Tela de carregamento não sumiu dentro do tempo esperado",
        timeout=timeout
    )
    print("Tela de carregamento sumiu. Download presumidamente concluído.")

def click_download_button_and_wait(typeDocument: DocumentoNome, process_number: str) -> None:
    """
    1) Seleciona o tipo de documento;
    2) Clica no botão de download;
    3) Aguarda a tela de carregamento sumir,
       indicando que o download terminou.
    4) Caso o tipo de documento não exista, dispara NoSuchElementException.
    """
    try:
        select_tipo_documento_por_nome(typeDocument)
        time.sleep(1)

        # Aqui chamamos a função de clique. Ajuste se quiser ID, CSS etc.
        click_element(xpath="/html/body/div/div[1]/div/form/span/ul[2]/li[5]/div/div[5]/input")
        print(f"Botão de download clicado com sucesso para '{typeDocument}'.")

        # Aguarda a tela de carregamento de download sumir
        wait_for_download_screen()
    except NoSuchElementException:
        print(f"O processo {process_number} não possui o tipo de documento '{typeDocument}'. Pulando download...")

@retry()
def skip_token():
    proceed_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Prosseguir sem o Token')]"))
    )
    proceed_button.click()
    
def downloadProcessOnTagSearch(typeDocument):
    error_processes = []
    process_numbers = []
    original_window = driver.current_window_handle

    driver.switch_to.default_content()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    print("Dentro do frame 'ngFrame'.")

    total_processes = len(get_process_list())
    for index in range(1, total_processes + 1):
        raw_process_number = "NÃO IDENTIFICADO"
        try:
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

            # Acessa aba de documentos
            click_element(css_selector='a.btn-menu-abas.dropdown-toggle')
            time.sleep(1)
            try:
                tipo_documento_foi_selecionado = select_tipo_documento_por_nome(typeDocument)
                if tipo_documento_foi_selecionado:
                    try:
                        click_element(xpath="/html/body/div/div[1]/div/form/span/ul[2]/li[5]/div/div[5]/input")
                        # Se quiser esperar pela tela de carregamento, chame: wait_for_download_screen()
                        time.sleep(5)
                        print(f"Botão de download clicado com sucesso para '{typeDocument}'.")
                    except Exception as e:
                        print(f"O processo {process_number} não foi possível clicar no botão de download. Pulando download...")
                        print(f"Erro: {e}")
                else:
                    print(f"O processo {process_number} não possui o tipo de documento '{typeDocument}'. Pulando download...")
            except Exception as e:
                print(f"Erro inesperado ao selecionar ou clicar no tipo de documento '{typeDocument}': {e}")



            # Fecha a janela do processo (com ou sem download) e retorna para a original
            driver.close()
            print("Janela atual fechada com sucesso.")
            driver.switch_to.window(original_window)
            print("Retornado para a janela original.")
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
            print("Alternado para o frame 'ngFrame'.")

        except Exception as e:
            print(f"Erro no processo {raw_process_number}: {e}")
            error_processes.append(raw_process_number)
            try:
                if len(driver.window_handles) > 1:
                    driver.close()
                    print("Janela atual fechada após erro.")
                    driver.switch_to.window(original_window)
                    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
            except Exception as inner_e:
                print(f"Erro ao fechar janela após erro no processo {raw_process_number}: {inner_e}")
            continue

    # Salva somente os processos que deram exceção inesperada
    if error_processes:
        with open("processos_com_erro.json", "w", encoding="utf-8") as f:
            json.dump(error_processes, f, ensure_ascii=False, indent=4)
        print("Processos com erro foram salvos em 'processos_com_erro.json'.")

    print("Processamento concluído.")
    return process_numbers

def download_requested_processes(process_numbers, etiqueta):
    """
    Acessa a página de requisição de downloads e baixa os processos listados,
    registrando em um arquivo JSON os processos baixados e os não encontrados.
    """
    resultados = {
        "nomeEtiqueta": etiqueta,
        "ProcessosBaixados": [],
        "ProcessosNãoEncontrados": []
    }

    try:
        driver.get('https://pje.tjba.jus.br/pje/AreaDeDownload/listView.seam')
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
        print("Dentro do iframe 'ngFrame'.")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'table')))
        print("Tabela carregada.")
        rows = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//table//tbody//tr")))
        print(f"Número total de processos na lista de downloads: {len(rows)}")
        downloaded_process_numbers = set()

        for row in rows:
            process_number_td = row.find_element(By.XPATH, "./td[1]")
            process_number = process_number_td.text.strip()
            print(f"Verificando o processo: {process_number}")

            if (process_number in process_numbers
                    and process_number not in downloaded_process_numbers):
                print(f"Processo {process_number} encontrado e ainda não baixado. Iniciando download...")
                download_button = row.find_element(By.XPATH, "./td[last()]//button")
                driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
                download_button.click()
                downloaded_process_numbers.add(process_number)
                resultados["ProcessosBaixados"].append(process_number)
                time.sleep(5)

        # Identificar processos que não foram encontrados na lista de downloads
        processos_nao_encontrados = [
            proc for proc in process_numbers
            if proc not in downloaded_process_numbers
        ]
        resultados["ProcessosNãoEncontrados"].extend(processos_nao_encontrados)

        driver.switch_to.default_content()
        print("Voltando para o conteúdo principal.")

    except Exception as e:
        save_exception_screenshot("download_requested_processes_exception.png")
        print(f"Erro em 'download_requested_processes'. Captura de tela salva. Erro: {e}")

    # Salvar os resultados no JSON
    json_filename = f".logs\\processos_download_{etiqueta}.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=4)
    print(f"Resultados salvos em {json_filename}.")

    return resultados

def iniciar_automacao():

    load_dotenv()

    global driver, wait
    # Instancia a classe de automação
    automator = PjeConsultaAutomator()
    # Pegamos o driver e o wait inicializados lá dentro
    driver = automator.driver
    wait = automator.wait

    # Pegamos usuário/senha/perfil do .env (ou do pje_automation)
    user = os.getenv("USER")
    password = os.getenv("PASSWORD")
    profile = os.getenv("PROFILE")

    # Chamamos as funções do pje_automation
    automator.login(user, password)
    # automator.skip_token()
    automator.select_profile(profile="V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL / Direção de Secretaria / Diretor de Secretaria")

    print("Automação inicializada com sucesso!")
    return automator

def main():
    automator = iniciar_automacao()
    try:
        # Exemplo de uso
        search_on_tag("meta 10")
        processos_encontrados = downloadProcessOnTagSearch(typeDocument="Denúncia")
        download_requested_processes(processos_encontrados, etiqueta="meta 10")
        time.sleep(5)
        
    finally:
        automator.close()

if __name__ == "__main__":
    main()
