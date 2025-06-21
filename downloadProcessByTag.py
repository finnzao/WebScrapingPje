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
    "Selecione"
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
    "Selecione":"0"
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

def check_for_area_download_message():
    """
    Verifica se apareceu a mensagem de que o arquivo foi enviado para a área de download.
    Retorna True se a mensagem foi encontrada, False caso contrário.
    """
    try:
        # Verifica se existe o painel de alerta de download
        alert_panel = driver.find_element(By.ID, "panelAlertDownloadMessagesContentTable")
        
        # Verifica se a mensagem específica está presente
        message_xpath = "//span[contains(text(), 'será disponibilizado no menu principal em: Download')]"
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, message_xpath))
        )
        print("Mensagem de área de download detectada - arquivo grande será processado em segundo plano")
        return True
    except (NoSuchElementException, TimeoutException):
        return False

def click_download_button_and_wait(typeDocument: DocumentoNome, process_number: str) -> str:
    """
    1) Seleciona o tipo de documento;
    2) Clica no botão de download;
    3) Verifica se o download foi direto ou foi para área de download
    4) Retorna o status do download: 'direto', 'area_download', 'erro' ou 'sem_documento'
    """
    try:
        if not select_tipo_documento_por_nome(typeDocument):
            print(f"O processo {process_number} não possui o tipo de documento '{typeDocument}'.")
            return 'sem_documento'
        
        time.sleep(1)

        # Tenta clicar no botão de download
        try:
            print("Tentando clique no botão Download")
            click_element(
                element_id="navbar:j_id304",
                css_selector="#navbar\\:j_id304",
                xpath="//input[@type='button' and @value='Download']"
            )
            print(f"Botão de download clicado para '{typeDocument}'.")
            
            # Aguarda um pouco para verificar o tipo de resposta
            time.sleep(3)
            
            # Verifica se apareceu a mensagem de área de download
            if check_for_area_download_message():
                return 'area_download'
            else:
                # Se não apareceu a mensagem, assume que foi download direto
                print(f"Download direto realizado para o processo {process_number}")
                return 'direto'
                
        except Exception as e:
            print(f"Erro ao clicar no botão de download: {e}")
            return 'erro'
            
    except Exception as e:
        print(f"Erro inesperado no processo de download: {e}")
        return 'erro'

@retry()
def skip_token():
    proceed_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Prosseguir sem o Token')]"))
    )
    proceed_button.click()
    
def downloadProcessOnTagSearch(typeDocument):
    """
    Realiza o download dos documentos e retorna um relatório detalhado
    """
    relatorio_detalhado = {
        "tipoDocumento": typeDocument,
        "dataHoraInicio": time.strftime("%Y-%m-%d %H:%M:%S"),
        "processosAnalisados": [],
        "resumo": {
            "totalProcessos": 0,
            "downloadsDiretos": 0,
            "enviadosAreaDownload": 0,
            "semDocumento": 0,
            "erros": 0
        }
    }
    
    original_window = driver.current_window_handle

    driver.switch_to.default_content()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    print("Dentro do frame 'ngFrame'.")

    total_processes = len(get_process_list())
    relatorio_detalhado["resumo"]["totalProcessos"] = total_processes
    
    for index in range(1, total_processes + 1):
        info_processo = {
            "numero": "NÃO IDENTIFICADO",
            "statusDownload": "erro",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "observacoes": ""
        }
        
        try:
            print(f"\nIniciando análise do processo {index} de {total_processes}")
            process_xpath = f"(//processo-datalist-card)[{index}]//a/div/span[2]"
            process_element = wait.until(EC.element_to_be_clickable((By.XPATH, process_xpath)))
            raw_process_number = process_element.text.strip()

            # Ajuste do número do processo
            just_digits = re.sub(r'\D', '', raw_process_number)
            if len(just_digits) >= 17:
                process_number = (
                    f"{just_digits[:7]}-{just_digits[7:9]}."
                    f"{just_digits[9:13]}.{just_digits[13]}."
                    f"{just_digits[14:16]}.{just_digits[16:]}"
                )
            else:
                process_number = raw_process_number

            info_processo["numero"] = process_number
            print(f"Número do processo: {process_number}")

            click_on_process(process_element)
            driver.switch_to.default_content()
            print("Saiu do frame 'ngFrame'.")

            # Acessa aba de documentos
            click_element(css_selector='a.btn-menu-abas.dropdown-toggle')
            time.sleep(2)

            # Tenta realizar o download e captura o status
            status_download = click_download_button_and_wait(typeDocument, process_number)
            info_processo["statusDownload"] = status_download
            
            # Atualiza contadores do resumo
            if status_download == 'direto':
                relatorio_detalhado["resumo"]["downloadsDiretos"] += 1
                info_processo["observacoes"] = "Download realizado diretamente"
            elif status_download == 'area_download':
                relatorio_detalhado["resumo"]["enviadosAreaDownload"] += 1
                info_processo["observacoes"] = "Arquivo grande - enviado para área de download"
            elif status_download == 'sem_documento':
                relatorio_detalhado["resumo"]["semDocumento"] += 1
                info_processo["observacoes"] = f"Processo não possui documento do tipo '{typeDocument}'"
            else:
                relatorio_detalhado["resumo"]["erros"] += 1
                info_processo["observacoes"] = "Erro durante tentativa de download"

            # Fecha a janela do processo e retorna
            driver.close()
            print("Janela atual fechada com sucesso.")
            driver.switch_to.window(original_window)
            print("Retornado para a janela original.")
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
            print("Alternado para o frame 'ngFrame'.")

        except Exception as e:
            print(f"Erro no processo {info_processo['numero']}: {e}")
            info_processo["statusDownload"] = "erro"
            info_processo["observacoes"] = f"Erro: {str(e)}"
            relatorio_detalhado["resumo"]["erros"] += 1
            
            try:
                if len(driver.window_handles) > 1:
                    driver.close()
                    print("Janela atual fechada após erro.")
                    driver.switch_to.window(original_window)
                    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
            except Exception as inner_e:
                print(f"Erro ao fechar janela após erro: {inner_e}")
        
        finally:
            relatorio_detalhado["processosAnalisados"].append(info_processo)

    relatorio_detalhado["dataHoraFim"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Salva relatório parcial
    with open(".logs/relatorio_downloads_parcial.json", "w", encoding="utf-8") as f:
        json.dump(relatorio_detalhado, f, ensure_ascii=False, indent=4)
    
    print("Processamento da primeira etapa concluído.")
    return relatorio_detalhado

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
    #automator.select_profile(profile="V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL / Diretor de Secretaria")

    print("Automação inicializada com sucesso!")
    return automator

def main():
    automator = iniciar_automacao()
    try:
        # Cria diretório de logs se não existir
        if not os.path.exists(".logs"):
            os.makedirs(".logs")
        
        # Define a etiqueta a ser pesquisada
        etiqueta = "Felipe"
        
        # Busca processos pela etiqueta
        search_on_tag(etiqueta)
        
        # Executa o download dos processos
        relatorio_parcial = downloadProcessOnTagSearch(typeDocument="Petição Inicial")
        
        # MODIFICAÇÃO: Pega TODOS os processos da etiqueta para verificar na área de download
        processos_da_etiqueta = [
            proc["numero"] for proc in relatorio_parcial["processosAnalisados"]
            if proc["numero"] != "NÃO IDENTIFICADO"
        ]
        
        print(f"\nTotal de processos da etiqueta '{etiqueta}' para verificar na área de download: {len(processos_da_etiqueta)}")
        
        # Aguarda um tempo para que os arquivos grandes sejam processados
        if processos_da_etiqueta:
            print(f"\nAguardando 30 segundos para processamento dos arquivos grandes...")
            time.sleep(30)
            
            # Chama a função modificada que verifica apenas processos da etiqueta
            resultados_finais = automator.download_files_from_download_area(
                process_numbers=processos_da_etiqueta,
                tag_name=etiqueta,
                partial_report=relatorio_parcial,
                save_report=True
            )
            
            # Exibe resumo final completo
            print("\n========== RESUMO FINAL COMPLETO ==========")
            print(f"Etiqueta: {etiqueta}")
            print(f"Total de processos analisados: {resultados_finais['resumoFinal']['totalProcessosAnalisados']}")
            print(f"Downloads diretos: {resultados_finais['resumoFinal']['downloadsDiretos']}")
            print(f"Verificados na área de download: {resultados_finais['resumoFinal']['verificadosAreaDownload']}")
            print(f"Baixados da área de download: {resultados_finais['resumoFinal']['baixadosAreaDownload']}")
            print(f"Não encontrados na área de download: {resultados_finais['resumoFinal']['naoEncontradosAreaDownload']}")
            print(f"Sem documento solicitado: {resultados_finais['resumoFinal']['semDocumento']}")
            print(f"Erros: {resultados_finais['resumoFinal']['erros']}")
            print(f"TOTAL DE SUCESSOS: {resultados_finais['resumoFinal']['sucessoTotal']}")
            print("===========================================")
        else:
            # Se não houver processos, apenas exibe resumo básico
            print("\n========== RESUMO FINAL ==========")
            print(f"Total de processos analisados: {relatorio_parcial['resumo']['totalProcessos']}")
            print(f"Downloads diretos: {relatorio_parcial['resumo']['downloadsDiretos']}")
            print(f"Sem documento solicitado: {relatorio_parcial['resumo']['semDocumento']}")
            print(f"Erros: {relatorio_parcial['resumo']['erros']}")
            print("==================================")
        
    finally:
        automator.close()

if __name__ == "__main__":
    main()