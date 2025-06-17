import re
import json
import time
import os
from functools import wraps
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    NoSuchElementException,
)

# Variáveis globais para driver e wait
driver = None
wait = None

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
                        raise TimeoutException(f"Falha ao executar {func.__name__} após {max_retries} tentativas")
        return wrapper
    return decorator

def initialize_driver():
    """
    Inicializa o driver do Chrome com as configurações desejadas, como pasta de download.
    """
    global driver, wait
    chrome_options = webdriver.ChromeOptions()
    user_home = os.path.expanduser("~")
    download_directory = os.path.join(user_home, "Downloads", "processosBaixadosEtiqueta")
    os.makedirs(download_directory, exist_ok=True)
    print(f"Diretório de download configurado para: {download_directory}")

    prefs = {
        "plugins.always_open_pdf_externally": True,
        "download.default_directory": download_directory,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 50)

def save_exception_screenshot(filename):
    directory = ".logs/screenshootErros"
    if not os.path.exists(directory):
        os.makedirs(directory)
    filepath = os.path.join(directory, filename)
    driver.save_screenshot(filepath)
    print(f"Screenshot salvo em: {filepath}")
    
def _detect_redirect_loop():
    time.sleep(1)
    try:
        error_element = driver.find_element(By.ID, 'sub-frame-error-details')
        if "Redirecionamento em excesso" in error_element.text:
            return True
    except:
        pass
    return False


@retry()
def login( user, password):
    login_url = 'https://pje.tjba.jus.br/pje/login.seam'
    driver.get(login_url)
    if _detect_redirect_loop():
        print("Redirecionamento em excesso detectado. Recarregando a página...")
        driver.refresh()
        time.sleep(2)
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ssoFrame')))
    wait.until(EC.presence_of_element_located((By.ID, 'username'))).send_keys(user)
    wait.until(EC.presence_of_element_located((By.ID, 'password'))).send_keys(password)
    wait.until(EC.presence_of_element_located((By.ID, 'kc-login'))).click()
    if _detect_redirect_loop():
        print("Redirecionamento em excesso detectado após login. Recarregando a página...")
        driver.refresh()
        time.sleep(2)
    driver.switch_to.default_content()
    try:
        WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'dropdown-toggle'))
        )
        print("Login efetuado com sucesso.")
    except TimeoutException:
        print("Login falhou. Elemento de perfil não apareceu. Recarregando a página...")
        driver.refresh()
    time.sleep(2)

@retry()
def skip_token():
    proceed_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Prosseguir sem o Token')]"))
    )
    proceed_button.click()

@retry()
def select_profile(profile):
    dropdown = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'dropdown-toggle')))
    dropdown.click()
    button_xpath = f"//a[contains(text(), '{profile}')]"
    desired_button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
    driver.execute_script("arguments[0].scrollIntoView(true);", desired_button)
    driver.execute_script("arguments[0].click();", desired_button)

@retry()
def search_process(classeJudicial='', nomeParte='', numOrgaoJustica='0216', numeroOAB='', estadoOAB=''):
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    icon_search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'li#liConsultaProcessual i.fas')))
    icon_search_button.click()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'frameConsultaProcessual')))
    elemento_num_orgao = wait.until(EC.presence_of_element_located((By.ID, 'fPP:numeroProcesso:NumeroOrgaoJustica')))
    elemento_num_orgao.send_keys(numOrgaoJustica)
   
    # OAB
    if estadoOAB:
        elemento_num_oab = wait.until(EC.presence_of_element_located((By.ID, 'fPP:decorationDados:numeroOAB')))
        elemento_num_oab.send_keys(numeroOAB)
        elemento_estados_oab = wait.until(EC.presence_of_element_located((By.ID, 'fPP:decorationDados:ufOABCombo')))
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
    click_element(pesquisar_xpath)
    print("Formulário preenchido e pesquisa iniciada com sucesso!")
    time.sleep(10)

def input_tag(search_text):
    search_input = wait.until(EC.element_to_be_clickable((By.ID, "itPesquisarEtiquetas")))
    search_input.clear()
    search_input.send_keys(search_text)
    click_element("/html/body/app-root/selector/div/div/div[2]/right-panel/div/etiquetas/div[1]/div/div[1]/div[2]/div[1]/span/button[1]")
    time.sleep(1)
    print(f"Pesquisa realizada com o texto: {search_text}")
    click_element("/html/body/app-root/selector/div/div/div[2]/right-panel/div/etiquetas/div[1]/div/div[2]/ul/p-datalist/div/div/ul/li/div/li/div[2]/span/span")

@retry()
def search_on_tag(search):
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    original_handles = set(driver.window_handles)
    print(f"Handles originais das janelas: {original_handles}")    
    nav_tag()
    input_tag(search)

def nav_tag():
    xpath = "/html/body/app-root/selector/div/div/div[1]/side-bar/nav/ul/li[5]/a"
    click_element(xpath)

@retry()
def skip_token():
    proceed_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Prosseguir sem o Token')]"))
    )
    proceed_button.click()

def get_process_list():
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
def click_element(xpath):
    try:
        element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        try:
            element.click()
            print(f"Elemento clicado com sucesso: {xpath}")
        except (ElementClickInterceptedException, Exception) as e:
            print(f"Erro ao clicar normalmente: {e}. Tentando JavaScript...")
            driver.execute_script("arguments[0].click();", element)
            print(f"Elemento clicado com JavaScript: {xpath}")
    except Exception as e:
        save_exception_screenshot("click_element_exception.png")
        print(f"Erro ao clicar no elemento. Captura de tela salva. Erro: {e}")
        raise e
    
@retry()
def click_by_css(css_selector):

    try:
        element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector)))
        
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        
        try:
            element.click()
            print("Elemento clicado com sucesso (método padrão).")
        except ElementClickInterceptedException as e:
            print(f"Erro de interceptação ao clicar: {e}. Tentando via JavaScript...")
            driver.execute_script("arguments[0].click();", element)
            print("Elemento clicado com sucesso (via JavaScript).")
    
    except Exception as e:
        print(f"Erro ao clicar no elemento via CSS selector '{css_selector}': {e}")
        raise e
    
@retry()
def select_tipo_documento(tipoDocumento):
    try:
        select_element = wait.until(EC.presence_of_element_located((By.ID, 'navbar:cbTipoDocumento')))
        select = Select(select_element)
        select.select_by_visible_text(tipoDocumento)
        print(f"Tipo de documento '{tipoDocumento}' selecionado com sucesso.")
    except Exception as e:
        save_exception_screenshot("select_tipo_documento_exception.png")
        print(f"Erro ao selecionar o tipo de documento. Captura de tela salva. Erro: {e}")
        raise e

def downloadProcessOnTagSearch(typeDocument):
    error_processes = []
    process_numbers = []
    original_window = driver.current_window_handle

    driver.switch_to.default_content()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    print("Dentro do frame 'ngFrame'.")

    total_processes = len(get_process_list())
    for index in range(1, total_processes + 1):
        try:
            print(f"\nIniciando o download para o processo {index} de {total_processes}")
            process_xpath = f"(//processo-datalist-card)[{index}]//a/div/span[2]"
            print(f"XPath gerado: {process_xpath}")
            process_element = wait.until(EC.element_to_be_clickable((By.XPATH, process_xpath)))
            raw_process_number = process_element.text.strip()
            process_number = re.sub(r'\D', '', raw_process_number)
            if len(process_number) >= 17:
                process_number = f"{process_number[:7]}-{process_number[7:9]}.{process_number[9:13]}.{process_number[13]}.{process_number[14:16]}.{process_number[16:]}"
            else:
                process_number = raw_process_number
            print(f"Número do processo: {process_number}")
            process_numbers.append(process_number)
            
            click_on_process(process_element)
            driver.switch_to.default_content()
            print("Saiu do frame 'ngFrame'.")
            
            #Abrir downloads
            click_by_css('a.btn-menu-abas.dropdown-toggle[title="Download autos do processo"]')
            
            select_tipo_documento(typeDocument)
            time.sleep(2)
            click_by_css('#navbar\\:botoesDownload .btn-primary')
            time.sleep(3)
            
            driver.close()
            print("Janela atual fechada com sucesso.")
            driver.switch_to.window(original_window)
            print("Retornado para a janela original.")
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
            print("Alternado para o frame 'ngFrame'.")
        except Exception as e:
            print(f"Erro no processo {process_number}: {e}")
            error_processes.append(process_number)
            try:
                if len(driver.window_handles) > 1:
                    driver.close()
                    print("Janela atual fechada após erro.")
                    driver.switch_to.window(original_window)
                    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
            except Exception as inner_e:
                print(f"Erro ao fechar janela após erro no processo {process_number}: {inner_e}")
            continue

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
            
            if process_number in process_numbers and process_number not in downloaded_process_numbers:
                print(f"Processo {process_number} encontrado e ainda não baixado. Iniciando download...")
                download_button = row.find_element(By.XPATH, "./td[last()]//button")
                driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
                download_button.click()
                downloaded_process_numbers.add(process_number)
                resultados["ProcessosBaixados"].append(process_number)
                time.sleep(5)
            
        # Identificar processos que não foram encontrados na lista de downloads
        processos_nao_encontrados = [proc for proc in process_numbers if proc not in downloaded_process_numbers]
        resultados["ProcessosNãoEncontrados"].extend(processos_nao_encontrados)
        
        driver.switch_to.default_content()
        print("Voltando para o conteúdo principal.")
        
    except Exception as e:
        save_exception_screenshot("download_requested_processes_exception.png")
        print(f"Erro em 'download_requested_processes'. Captura de tela salva. Erro: {e}")
    
    # Salvar os resultados no JSON
    json_filename = f"processos_download_{etiqueta}.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=4)
    print(f"Resultados salvos em {json_filename}.")
    
    return resultados

def main():
    load_dotenv()
    initialize_driver()
    try:
        user, password = os.getenv("USER"), os.getenv("PASSWORD")
        login(user, password)
        #skip_token()
        profile = os.getenv("PROFILE")
        select_profile(profile)
        search_on_tag("teste")
        process_numbers = downloadProcessOnTagSearch("Selecione")
        download_requested_processes(process_numbers,etiqueta="CDEP")
        time.sleep(10)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()