"""
Automação PJe – download em massa de documentos via timeline
----------------------------------------------------------
• Login, perfil, navegação por etiqueta
• Busca por processos, download dos autos
• Dentro do processo, pesquisa por termo na timeline
  e download de cada documento correspondente
• Sistema de relatórios detalhados para evitar falsos positivos
"""

import os
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

from utils.pje_automation import PjeConsultaAutomator

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


def save_screenshot(label):
    path_dir = ".logs/screenshots"
    os.makedirs(path_dir, exist_ok=True)
    fp = os.path.join(path_dir, f"{label}.png")
    driver.save_screenshot(fp)
    print(f"[SNAP] {fp}")


def save_exception_screenshot(filename):
    """Salva um screenshot atual do driver na pasta '.logs/exception'."""
    directory = ".logs/exception"
    if not os.path.exists(directory):
        os.makedirs(directory)
    filepath = os.path.join(directory, filename)
    driver.save_screenshot(filepath)
    print(f"Screenshot salvo em: {filepath}")


def click_element(
    xpath: str = None,
    element_id: str = None,
    css_selector: str = None
) -> None:
    """Função melhorada para clicar em elementos com múltiplas estratégias."""
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

    # Tenta xpath primeiro
    if xpath and _try_click(By.XPATH, xpath, "XPATH"):
        return

    # Tenta ID
    if element_id and _try_click(By.ID, element_id, "ID"):
        return

    # Tenta CSS Selector
    if css_selector:
        try:
            print(
                f"[click_element] Tentando CSS SELECTOR (JS) via: {css_selector}")
            wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, css_selector)))
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
    msg = f"Não foi possível clicar no elemento usando XPATH='{xpath}', ID='{element_id}' ou CSS SELECTOR='{css_selector}'."
    print(msg)
    raise NoSuchElementException(msg)


def confirmar_popup_download(timeout_alert=5, timeout_modal=10) -> bool:
    """
    Tenta confirmar (aceitar) o pop‑up de download, seja ele
    um alerta JS ou um modal HTML. Retorna True se conseguiu.
    """
    # 1) JS alert / confirm
    try:
        WebDriverWait(driver, timeout_alert).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        alert.accept()
        print("[OK] Alerta JavaScript aceito")
        return True
    except (TimeoutException, NoAlertPresentException):
        pass   # não era JS, tenta modal HTML

    # 2) Modal HTML
    try:
        botoes_confirmar = [
            "//button[contains(.,'Confirmar')]",
            "//button[contains(.,'OK')]",
            "//button[contains(@class,'btn-primary')]"
        ]
        for xp in botoes_confirmar:
            try:
                btn = WebDriverWait(driver, timeout_modal).until(
                    EC.element_to_be_clickable((By.XPATH, xp)))
                driver.execute_script("arguments[0].click();", btn)
                print("[OK] Modal HTML confirmado")
                return True
            except TimeoutException:
                continue
    except ElementClickInterceptedException as e:
        print(f"[WARN] Interceptado ao clicar no modal: {e}")

    print("[INFO] Nenhum pop‑up de confirmação encontrado")
    return False


def switch_to_new_window(original_handles, timeout=10):
    """Alterna para a nova janela que foi aberta após a execução de uma ação."""
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
    """Alterna de volta para a janela original."""
    try:
        driver.switch_to.window(original_handle)
        print(f"Retornado para a janela original: {original_handle}")
    except Exception as e:
        save_exception_screenshot("switch_to_original_window_exception.png")
        print(
            f"Erro ao retornar para a janela original. Captura de tela salva. Erro: {e}")
        raise e


def input_tag(search_text):
    """Função para pesquisar etiqueta."""
    search_input = wait.until(EC.element_to_be_clickable(
        (By.ID, "itPesquisarEtiquetas")))
    search_input.clear()
    search_input.send_keys(search_text)
    click_element(
        xpath="/html/body/app-root/selector/div/div/div[2]/right-panel/div/etiquetas/div[1]/div/div[1]/div[2]/div[1]/span/button[1]")
    time.sleep(1)
    print(f"Pesquisa realizada com o texto: {search_text}")
    click_element(
        xpath="/html/body/app-root/selector/div/div/div[2]/right-panel/div/etiquetas/div[1]/div/div[2]/ul/p-datalist/div/div/ul/li/div/li/div[2]/span/span")


def _norm(txt: str) -> str:
    """minúsculas + sem acento + espaços comprimidos"""
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(ch for ch in txt if unicodedata.category(ch) != "Mn")
    return " ".join(txt.lower().split())

# ----------------------------------------------------------------------
# NOVA FUNÇÃO: Download em massa via JavaScript
# ----------------------------------------------------------------------


def executar_download_em_massa_js() -> dict:
    """
    Executa a função JavaScript de download em massa de todos os arquivos
    disponíveis na página atual do PJe.
    Retorna um dicionário com informações sobre o resultado.
    """

    js_download_function = """
    async function downloadAllFilesPJe() {
        // Função para aguardar um elemento aparecer
        function waitForElement(selector, timeout = 10000) {
            return new Promise((resolve, reject) => {
                const startTime = Date.now();
                
                const checkElement = () => {
                    const element = document.querySelector(selector);
                    if (element) {
                        resolve(element);
                    } else if (Date.now() - startTime > timeout) {
                        reject(new Error(`Elemento ${selector} não encontrado após ${timeout}ms`));
                    } else {
                        setTimeout(checkElement, 100);
                    }
                };
                
                checkElement();
            });
        }

        // Função para aguardar o iframe carregar
        function waitForIframeLoad(iframe) {
            return new Promise((resolve) => {
                if (iframe.contentDocument && iframe.contentDocument.readyState === 'complete') {
                    resolve();
                } else {
                    iframe.onload = () => resolve();
                    setTimeout(() => resolve(), 2000);
                }
            });
        }

        try {
            console.log('Iniciando processo de download em massa...');
            
            // Aguarda o iframe
            const iframe = await waitForElement('#ngFrame');
            await waitForIframeLoad(iframe);
            await new Promise(resolve => setTimeout(resolve, 3000));
            
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            
            if (!iframeDoc) {
                throw new Error('Não foi possível acessar o conteúdo do iframe');
            }
            
            // Busca botões de download
            let downloadButtons = Array.from(iframeDoc.querySelectorAll('button')).filter(btn => {
                const hasDownloadIcon = btn.querySelector('span.pi-download') || 
                                       btn.querySelector('.pi-download') ||
                                       btn.querySelector('[class*="download"]');
                const hasDownloadClass = btn.className.includes('download');
                return hasDownloadIcon || hasDownloadClass;
            });
            
            // Se não encontrou, tenta seletores alternativos
            if (downloadButtons.length === 0) {
                const alternativeSelectors = [
                    'button[title*="download" i]',
                    'button[aria-label*="download" i]',
                    'a[href*="download"]',
                    'button.ui-button'
                ];
                
                for (const selector of alternativeSelectors) {
                    const elements = iframeDoc.querySelectorAll(selector);
                    if (elements.length > 0) {
                        downloadButtons = Array.from(elements);
                        break;
                    }
                }
            }
            
            if (downloadButtons.length === 0) {
                return {
                    success: false,
                    message: 'Nenhum botão de download encontrado',
                    totalButtons: 0,
                    downloadedCount: 0
                };
            }
            
            // Executa os downloads
            let successCount = 0;
            for (let i = 0; i < downloadButtons.length; i++) {
                try {
                    const button = downloadButtons[i];
                    button.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    await new Promise(resolve => setTimeout(resolve, 500));
                    button.click();
                    successCount++;
                    await new Promise(resolve => setTimeout(resolve, 1500));
                } catch (error) {
                    console.error(`Erro ao processar download ${i + 1}:`, error);
                }
            }
            
            return {
                success: true,
                message: 'Download em massa concluído',
                totalButtons: downloadButtons.length,
                downloadedCount: successCount
            };
            
        } catch (error) {
            return {
                success: false,
                message: error.message,
                totalButtons: 0,
                downloadedCount: 0
            };
        }
    }
    
    // Executa a função e retorna o resultado
    return await downloadAllFilesPJe();
    """

    try:
        print("[JS DOWNLOAD] Executando função de download em massa...")
        resultado = driver.execute_script(js_download_function)

        print(f"[JS DOWNLOAD] Resultado: {resultado}")
        print(
            f"[JS DOWNLOAD] Total de botões: {resultado.get('totalButtons', 0)}")
        print(
            f"[JS DOWNLOAD] Downloads iniciados: {resultado.get('downloadedCount', 0)}")

        return resultado
    except Exception as e:
        print(f"[JS DOWNLOAD] Erro ao executar download em massa: {e}")
        save_exception_screenshot("js_download_massa_erro.png")
        return {
            "success": False,
            "message": str(e),
            "totalButtons": 0,
            "downloadedCount": 0
        }


@retry(max_retries=2)
def baixar_documentos_timeline_filtrando(busca_pesquisa: str,
                                         filtro_titulo: str = "peticao inicial",
                                         frame_id: str = "timelineFrame",
                                         id_campo: str = "divTimeLine:txtPesquisa",
                                         xpath_botao: str = '//*[@id="divTimeLine:btnPesquisar"]',
                                         xpath_container: str = '//*[@id="divTimeLine:eventosTimeLineElement"]/div[4]/div[2]',
                                         id_container: str = 'divTimeLine:eventosTimeLineElement',
                                         xpath_download: str = '//*[@id="detalheDocumento:downloadPJeDocs"]',
                                         processo_numero: str = "N/A"
                                         ) -> dict:
    """
    1. Digita <busca_pesquisa> no campo de timeline e clica em Pesquisar.
    2. Filtra os links cujo texto contenha <filtro_titulo>.
    3. Clica em cada um desses links e baixa o PDF.
    Retorna um dicionário com informações detalhadas do processo.
    """
    resultado_processo = {
        "numero": processo_numero,
        "busca_termo": busca_pesquisa,
        "filtro_aplicado": filtro_titulo,
        "status": "erro",
        "documentos_encontrados": 0,
        "documentos_baixados": 0,
        "documentos_falharam": 0,
        "detalhes_downloads": [],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "observacoes": ""
    }

    baixados = 0
    alvo_norm = _norm(filtro_titulo)

    try:
        # --- entrar no iframe da timeline ---
        # driver.switch_to.default_content()
        # wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, frame_id)))

        # --- pesquisa ---
        campo = wait.until(EC.element_to_be_clickable((By.ID, id_campo)))
        campo.clear()
        campo.send_keys(busca_pesquisa)
        wait.until(EC.element_to_be_clickable((By.XPATH, xpath_botao))).click()
        time.sleep(2)

        # --- coletar links ---
        container = wait.until(
            EC.presence_of_element_located((By.ID, id_container)))
        todos_links = container.find_elements(By.TAG_NAME, "a")
        links_filtrados = [
            a for a in todos_links if alvo_norm in _norm(a.text)]

        resultado_processo["documentos_encontrados"] = len(links_filtrados)
        print(
            f"[TL] {len(todos_links)} link(s) totais  •  {len(links_filtrados)} após filtro '{filtro_titulo}'")

        if len(links_filtrados) == 0:
            resultado_processo["status"] = "sem_documentos"
            resultado_processo[
                "observacoes"] = f"Nenhum documento encontrado com o filtro '{filtro_titulo}'"
            return resultado_processo

        # --- download apenas dos links filtrados ---
        for idx, link in enumerate(links_filtrados, 1):
            detalhe_download = {
                "sequencia": idx,
                "titulo_documento": link.text.strip(),
                "status": "erro",
                "observacao": ""
            }

            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView(true);", link)
                driver.execute_script("arguments[0].click();", link)

                btn_dl = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, xpath_download)))
                driver.execute_script("arguments[0].click();", btn_dl)

                if confirmar_popup_download():
                    detalhe_download["observacao"] = "Pop-up de confirmação aceito"

                baixados += 1
                detalhe_download["status"] = "sucesso"
                print(f"   └─ ({idx}) download OK — {link.text.strip()}")
                time.sleep(2)

            except (TimeoutException, ElementClickInterceptedException) as e:
                detalhe_download["status"] = "falha"
                detalhe_download["observacao"] = str(e)
                print(f"   └─ ({idx}) falhou: {e}")
                save_screenshot(f"falha_timeline_{processo_numero}_{idx}")
                resultado_processo["documentos_falharam"] += 1

            resultado_processo["detalhes_downloads"].append(detalhe_download)

        resultado_processo["documentos_baixados"] = baixados

        if baixados == len(links_filtrados):
            resultado_processo["status"] = "sucesso_total"
            resultado_processo["observacoes"] = "Todos os documentos foram baixados com sucesso"
        elif baixados > 0:
            resultado_processo["status"] = "sucesso_parcial"
            resultado_processo["observacoes"] = f"{baixados} de {len(links_filtrados)} documentos baixados"
        else:
            resultado_processo["status"] = "falha_total"
            resultado_processo["observacoes"] = "Nenhum documento foi baixado com sucesso"

    except Exception as e:
        resultado_processo["status"] = "erro_timeline"
        resultado_processo["observacoes"] = f"Erro ao acessar timeline: {str(e)}"
        save_exception_screenshot(f"erro_timeline_{processo_numero}.png")
        print(f"[ERRO] Falha na timeline do processo {processo_numero}: {e}")

    finally:
        try:
            driver.switch_to.default_content()
        except:
            pass

    return resultado_processo


def click_on_process(process_element):
    """Clica no elemento do processo e alterna para a nova janela."""
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
    """Retorna uma lista de elementos representando os processos encontrados."""
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
    """Ação principal que pesquisa os processos via etiqueta."""
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    original_handles = set(driver.window_handles)
    print(f"Handles originais das janelas: {original_handles}")
    click_element(
        xpath="/html/body/app-root/selector/div/div/div[1]/side-bar/nav/ul/li[5]/a")
    input_tag(tag)


def processos_em_lista_timeline(busca_pesquisa: str, filtro_titulo: str = "petição inicial") -> dict:
    """
    Processa todos os processos da lista, baixando documentos via timeline.
    Retorna relatório detalhado com informações de cada processo.
    """
    relatorio_detalhado = {
        "busca_termo": busca_pesquisa,
        "filtro_titulo": filtro_titulo,
        "dataHoraInicio": time.strftime("%Y-%m-%d %H:%M:%S"),
        "processosAnalisados": [],
        "resumo": {
            "totalProcessos": 0,
            "sucessoTotal": 0,
            "sucessoParcial": 0,
            "semDocumentos": 0,
            "falhaTotal": 0,
            "erros": 0,
            "totalDocumentosBaixados": 0
        }
    }

    original_window = driver.current_window_handle

    try:
        driver.switch_to.default_content()
        wait.until(EC.frame_to_be_available_and_switch_to_it(
            (By.ID, 'ngFrame')))
        print("Dentro do frame 'ngFrame'.")

        total_processes = len(get_process_list())
        relatorio_detalhado["resumo"]["totalProcessos"] = total_processes

        for index in range(1, total_processes + 1):
            raw_process_number = "NÃO IDENTIFICADO"

            try:
                print(
                    f"\nIniciando o download para o processo {index} de {total_processes}")
                process_xpath = f"(//processo-datalist-card)[{index}]//a/div/span[2]"
                process_element = wait.until(
                    EC.element_to_be_clickable((By.XPATH, process_xpath)))
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

                # Dentro do processo
                click_on_process(process_element)
                driver.switch_to.default_content()
                print("Saiu do frame 'ngFrame'.")

                # Baixa documentos da timeline
                resultado_processo = baixar_documentos_timeline_filtrando(
                    busca_pesquisa=busca_pesquisa,
                    filtro_titulo=filtro_titulo,
                    processo_numero=process_number
                )

                # Atualiza contadores do resumo
                status = resultado_processo["status"]
                if status == "sucesso_total":
                    relatorio_detalhado["resumo"]["sucessoTotal"] += 1
                elif status == "sucesso_parcial":
                    relatorio_detalhado["resumo"]["sucessoParcial"] += 1
                elif status == "sem_documentos":
                    relatorio_detalhado["resumo"]["semDocumentos"] += 1
                elif status == "falha_total":
                    relatorio_detalhado["resumo"]["falhaTotal"] += 1
                else:
                    relatorio_detalhado["resumo"]["erros"] += 1

                relatorio_detalhado["resumo"]["totalDocumentosBaixados"] += resultado_processo["documentos_baixados"]
                relatorio_detalhado["processosAnalisados"].append(
                    resultado_processo)

                time.sleep(1)
                driver.close()
                print("Janela atual fechada com sucesso.")
                driver.switch_to.window(original_window)
                print("Retornado para a janela original.")
                wait.until(EC.frame_to_be_available_and_switch_to_it(
                    (By.ID, 'ngFrame')))
                print("Alternado para o frame 'ngFrame'.")

            except Exception as e:
                print(f"Erro no processo {raw_process_number}: {e}")

                resultado_erro = {
                    "numero": raw_process_number,
                    "busca_termo": busca_pesquisa,
                    "filtro_aplicado": filtro_titulo,
                    "status": "erro_geral",
                    "documentos_encontrados": 0,
                    "documentos_baixados": 0,
                    "documentos_falharam": 0,
                    "detalhes_downloads": [],
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "observacoes": f"Erro geral: {str(e)}"
                }

                relatorio_detalhado["processosAnalisados"].append(
                    resultado_erro)
                relatorio_detalhado["resumo"]["erros"] += 1

                try:
                    if len(driver.window_handles) > 1:
                        driver.close()
                        print("Janela atual fechada após erro.")
                        driver.switch_to.window(original_window)
                        wait.until(EC.frame_to_be_available_and_switch_to_it(
                            (By.ID, 'ngFrame')))
                except Exception as inner_e:
                    print(f"Erro ao fechar janela após erro: {inner_e}")

    except Exception as e:
        print(f"Erro geral na listagem de processos: {e}")
        save_exception_screenshot("erro_geral_listagem.png")

    relatorio_detalhado["dataHoraFim"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return relatorio_detalhado

# ----------------------------------------------------------------------
# DOWNLOAD DE AUTO COMPLETO (mantido do código original)
# ----------------------------------------------------------------------


def baixar_autos(document_type: str):
    """Baixa autos completos do processo."""
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
# FUNÇÃO MODIFICADA: downloadRequestedFileOnProcessesTimeline
# ----------------------------------------------------------------------


def downloadRequestedFilesPageDownload(processos_da_etiqueta, etiqueta, relatorio_parcial):
    """
    Acessa a página de requisição de downloads e baixa APENAS os processos que:
    1. Estão na área de download E
    2. Pertencem à etiqueta atual sendo processada
    """
    resultados_finais = {
        "nomeEtiqueta": etiqueta,
        "tipoDocumento": relatorio_parcial.get("tipoDocumento", "Petição Inicial"),
        "dataHoraInicio": relatorio_parcial["dataHoraInicio"],
        "dataHoraFinalizacao": time.strftime("%Y-%m-%d %H:%M:%S"),
        "processosDetalhados": relatorio_parcial["processosAnalisados"],
        "areaDownload": {
            "processosVerificados": len(processos_da_etiqueta),
            "processosBaixados": [],
            "processosNaoEncontrados": [],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "resumoFinal": {
            "totalProcessosAnalisados": relatorio_parcial["resumo"]["totalProcessos"],
            "downloadsDiretos": relatorio_parcial["resumo"]["downloadsDiretos"],
            "verificadosAreaDownload": len(processos_da_etiqueta),
            "baixadosAreaDownload": 0,
            "naoEncontradosAreaDownload": 0,
            "semDocumento": relatorio_parcial["resumo"]["semDocumento"],
            "erros": relatorio_parcial["resumo"]["erros"],
            "sucessoTotal": 0
        }
    }

    if not processos_da_etiqueta:
        print("Nenhum processo da etiqueta para verificar na área de download.")
        resultados_finais["resumoFinal"]["sucessoTotal"] = resultados_finais["resumoFinal"]["downloadsDiretos"]
        json_filename = f".logs/processos_download_{etiqueta}_completo.json"
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(resultados_finais, f, ensure_ascii=False, indent=4)
        return resultados_finais

    try:
        print(
            f"\nAcessando área de download para verificar {len(processos_da_etiqueta)} processos da etiqueta '{etiqueta}'...")
        driver.get('https://pje.tjba.jus.br/pje/AreaDeDownload/listView.seam')
        wait.until(EC.frame_to_be_available_and_switch_to_it(
            (By.ID, 'ngFrame')))
        print("Dentro do iframe 'ngFrame'.")

        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'table')))
        print("Tabela carregada.")

        rows = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//table//tbody//tr")))
        print(f"Número total de processos na lista de downloads: {len(rows)}")

        # Conjunto de números de processos da etiqueta para verificação rápida
        numeros_etiqueta = set(processos_da_etiqueta)
        downloaded_process_numbers = set()

        for row in rows:
            try:
                process_number_td = row.find_element(By.XPATH, "./td[1]")
                process_number = process_number_td.text.strip()

                # Verifica se o processo pertence à etiqueta atual
                if process_number in numeros_etiqueta and process_number not in downloaded_process_numbers:
                    print(
                        f"Processo {process_number} da etiqueta '{etiqueta}' encontrado. Baixando...")

                    try:
                        download_button = row.find_element(
                            By.XPATH, "./td[last()]//button")
                        driver.execute_script(
                            "arguments[0].scrollIntoView(true);", download_button)
                        download_button.click()
                        time.sleep(5)

                        downloaded_process_numbers.add(process_number)
                        resultados_finais["areaDownload"]["processosBaixados"].append(
                            process_number)

                        # Atualiza o status do processo no relatório detalhado
                        for proc in resultados_finais["processosDetalhados"]:
                            if proc["numero"] == process_number:
                                proc["statusDownload"] = "baixado_area_download"
                                proc["observacoes"] += " - Baixado com sucesso da área de download"
                                proc["timestampAreaDownload"] = time.strftime(
                                    "%Y-%m-%d %H:%M:%S")

                    except Exception as e:
                        print(
                            f"Erro ao baixar processo {process_number} da área de download: {e}")

            except Exception as e:
                print(f"Erro ao processar linha da tabela: {e}")
                continue

        # Identificar processos da etiqueta que não foram encontrados na área de download
        processos_nao_encontrados = [
            proc for proc in processos_da_etiqueta
            if proc not in downloaded_process_numbers
        ]

        resultados_finais["areaDownload"]["processosNaoEncontrados"] = processos_nao_encontrados

        # Atualiza processos não encontrados no relatório detalhado
        for proc_num in processos_nao_encontrados:
            for proc in resultados_finais["processosDetalhados"]:
                if proc["numero"] == proc_num:
                    proc["statusDownload"] = "nao_encontrado_area_download"
                    proc["observacoes"] += " - Não encontrado na área de download"

        driver.switch_to.default_content()
        print("Voltando para o conteúdo principal.")

    except Exception as e:
        save_exception_screenshot("download_area_exception.png")
        print(f"Erro ao acessar área de download: {e}")

    # Atualiza resumo final
    resultados_finais["resumoFinal"]["baixadosAreaDownload"] = len(
        resultados_finais["areaDownload"]["processosBaixados"]
    )
    resultados_finais["resumoFinal"]["naoEncontradosAreaDownload"] = len(
        resultados_finais["areaDownload"]["processosNaoEncontrados"]
    )
    resultados_finais["resumoFinal"]["sucessoTotal"] = (
        resultados_finais["resumoFinal"]["downloadsDiretos"] +
        resultados_finais["resumoFinal"]["baixadosAreaDownload"]
    )

    # Salvar relatório final
    json_filename = f".logs/processos_download_{etiqueta}_completo.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(resultados_finais, f, ensure_ascii=False, indent=4)

    print(f"\nRelatório final salvo em {json_filename}")
    print(
        f"Processos baixados da área de download: {len(resultados_finais['areaDownload']['processosBaixados'])}")
    print(
        f"Total de sucessos: {resultados_finais['resumoFinal']['sucessoTotal']} de {resultados_finais['resumoFinal']['totalProcessosAnalisados']}")

    return resultados_finais

# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------


def iniciar_automacao():
    """Inicializa a automação usando a classe PjeConsultaAutomator."""
    load_dotenv()

    global driver, wait
    # Instancia a classe de automação
    automator = PjeConsultaAutomator()
    # Pegamos o driver e o wait inicializados lá dentro
    driver = automator.driver
    wait = automator.wait

    # Pegamos usuário/senha/perfil do .env
    user = os.getenv("USER")
    password = os.getenv("PASSWORD")
    profile = os.getenv("PROFILE")

    # Chamamos as funções do pje_automation
    automator.login(user, password)
    if profile:
        automator.select_profile(profile)

    print("Automação inicializada com sucesso!")
    return automator


def main():
    automator = iniciar_automacao()
    try:
        # Cria diretório de logs se não existir
        os.makedirs(".logs", exist_ok=True)

        # Define a etiqueta a ser pesquisada
        etiqueta = "Felipe [ Analise ] "

        # Abre página de etiquetas
        open_tag_page(etiqueta)

        # Processar diretamente da lista de etiquetas
        relatorio_timeline = processos_em_lista_timeline(
            busca_pesquisa="Petição inicial",
            filtro_titulo="petição"
        )

        # Salva relatório da timeline
        with open(".logs/relatorio_timeline_completo.json", "w", encoding="utf-8") as f:
            json.dump(relatorio_timeline, f, ensure_ascii=False, indent=2)

        # MODIFICAÇÃO: Pega TODOS os processos da etiqueta para verificar na área de download
        processos_da_etiqueta = [
            proc["numero"] for proc in relatorio_timeline["processosAnalisados"]
            if proc["numero"] != "NÃO IDENTIFICADO"
        ]

        print(
            f"\nTotal de processos da etiqueta '{etiqueta}' para verificar na área de download: {len(processos_da_etiqueta)}")

        # Sempre verifica a área de download se houver processos
        if processos_da_etiqueta:
            # Prepara o relatório parcial para a função
            relatorio_parcial = {
                "tipoDocumento": "Petição Inicial",
                "dataHoraInicio": relatorio_timeline["dataHoraInicio"],
                "processosAnalisados": relatorio_timeline["processosAnalisados"],
                "resumo": {
                    "totalProcessos": relatorio_timeline["resumo"]["totalProcessos"],
                    "downloadsDiretos": relatorio_timeline["resumo"]["sucessoTotal"] + relatorio_timeline["resumo"]["sucessoParcial"],
                    # Todos serão verificados
                    "enviadosAreaDownload": len(processos_da_etiqueta),
                    "semDocumento": relatorio_timeline["resumo"]["semDocumentos"],
                    "erros": relatorio_timeline["resumo"]["erros"]
                }
            }

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
            print(
                f"Total de processos analisados: {resultados_finais['resumoFinal']['totalProcessosAnalisados']}")
            print(
                f"Downloads diretos (timeline): {resultados_finais['resumoFinal']['downloadsDiretos']}")
            print(
                f"Verificados na área de download: {resultados_finais['resumoFinal']['verificadosAreaDownload']}")
            print(
                f"Baixados da área de download: {resultados_finais['resumoFinal']['baixadosAreaDownload']}")
            print(
                f"Não encontrados na área de download: {resultados_finais['resumoFinal']['naoEncontradosAreaDownload']}")
            print(
                f"Sem documentos: {resultados_finais['resumoFinal']['semDocumento']}")
            print(f"Erros: {resultados_finais['resumoFinal']['erros']}")
            print(
                f"SUCESSO TOTAL: {resultados_finais['resumoFinal']['sucessoTotal']}")
            print("===========================================")
            input("Pressione Enter para finalizar...")
        else:
            # Se não houver processos, apenas exibe resumo da timeline
            print("\n========== RESUMO FINAL TIMELINE ==========")
            print(
                f"Total de processos: {relatorio_timeline['resumo']['totalProcessos']}")
            print(
                f"Sucesso total: {relatorio_timeline['resumo']['sucessoTotal']}")
            print(
                f"Sucesso parcial: {relatorio_timeline['resumo']['sucessoParcial']}")
            print(
                f"Sem documentos: {relatorio_timeline['resumo']['semDocumentos']}")
            print(f"Falha total: {relatorio_timeline['resumo']['falhaTotal']}")
            print(f"Erros: {relatorio_timeline['resumo']['erros']}")
            print(
                f"Total documentos baixados: {relatorio_timeline['resumo']['totalDocumentosBaixados']}")
            print("===========================================")

        time.sleep(5)

    except Exception as e:
        print(f"Erro na execução principal: {e}")
        save_exception_screenshot("erro_main.png")
        raise

    finally:
        automator.close()


if __name__ == "__main__":
    main()
