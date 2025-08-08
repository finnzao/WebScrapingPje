import os
import json
import math
import re
import time
import logging
from dotenv import load_dotenv

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from openpyxl import Workbook
from openpyxl.styles import Font

from utils.pje_automation import PjeConsultaAutomator

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

driver = None
wait = None

def search_process(numOrgaoJustica="", numTribunal="", processoAno='', numeroOAB="", estadoOAB="", dataAutuacaoDe="",
                   dataAutuacaoAte="", Assunto="", classeJudicial="", nomeParte="", nomeAdvogado="",
                   outrosNomesAlcunha="", orgaoJulgadorCombo="V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL"):
    """
    Realiza busca de processos no PJE com preenchimento seguro dos campos

    Args:
        numOrgaoJustica (str): Número do órgão de justiça
        numTribunal (str): Número do tribunal
        processoAno (str): Ano do processo
        numeroOAB (str): Número da OAB
        estadoOAB (str): Estado da OAB
        dataAutuacaoDe (str): Data inicial de autuação
        dataAutuacaoAte (str): Data final de autuação
        Assunto (str): Assunto do processo
        classeJudicial (str): Classe judicial
        nomeParte (str): Nome da parte
        nomeAdvogado (str): Nome do advogado
        outrosNomesAlcunha (str): Outros nomes/alcunha
        orgaoJulgadorCombo (str): Órgão julgador
    """
    
    def safe_fill_field(element, value, field_name="campo", clear_first=True, use_js=False):
        """
        Preenche um campo de forma segura com verificação
        
        Args:
            element: Elemento do campo
            value: Valor a ser preenchido
            field_name: Nome do campo para logs
            clear_first: Se deve limpar o campo primeiro
            use_js: Se deve usar JavaScript para preenchimento
        """
        try:
            if not value:
                return True
                
            # Aguarda o elemento estar interagível
            wait.until(EC.element_to_be_clickable(element))
            
            # Move para o elemento e clica nele
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)
            element.click()
            time.sleep(0.3)
            
            # Limpa o campo se solicitado
            if clear_first:
                if use_js:
                    driver.execute_script("arguments[0].value = '';", element)
                else:
                    element.clear()
                    # Usa Ctrl+A e Delete como backup
                    element.send_keys(Keys.CONTROL + "a")
                    element.send_keys(Keys.DELETE)
                time.sleep(0.3)
            
            # Preenche o campo
            if use_js:
                driver.execute_script(f"arguments[0].value = '{value}';", element)
                # Dispara eventos para garantir que o valor seja registrado
                driver.execute_script("""
                    var element = arguments[0];
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                    element.dispatchEvent(new Event('change', { bubbles: true }));
                """, element)
            else:
                element.send_keys(value)
            
            time.sleep(0.5)
            
            # Verifica se o valor foi preenchido corretamente
            actual_value = element.get_attribute('value')
            if actual_value == value:
                logging.info(f"✅ {field_name} preenchido corretamente: {value}")
                return True
            else:
                logging.warning(f"⚠️ {field_name} - Valor esperado: {value}, Valor atual: {actual_value}")
                
                # Tenta novamente com JavaScript se necessário
                if not use_js:
                    logging.info(f"🔄 Tentando preencher {field_name} novamente com JavaScript...")
                    return safe_fill_field(element, value, field_name, clear_first, use_js=True)
                return False
                
        except Exception as e:
            logging.error(f"❌ Erro ao preencher {field_name}: {e}")
            return False
    
    try:
        # Aguarda e entra no frame principal
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
        logging.info("🔍 Dentro do frame principal")
        
        # Clica no botão de busca
        icon_search_button = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'li#liConsultaProcessual i.fas'))
        )
        icon_search_button.click()
        logging.info("🔍 Botão de consulta processual clicado")
        
        # Entra no frame de consulta
        wait.until(EC.frame_to_be_available_and_switch_to_it(
            (By.ID, 'frameConsultaProcessual')))
        logging.info("🔍 Dentro do frame de consulta processual")
        
        # Aguarda o formulário carregar completamente
        wait.until(EC.presence_of_element_located((By.ID, 'fPP:searchProcessos')))
        time.sleep(2)  # Aguarda estabilização do formulário
        
        # Preenche Número do Órgão de Justiça
        if numOrgaoJustica:
            elemento_orgao = wait.until(
                EC.presence_of_element_located(
                    (By.ID, 'fPP:numeroProcesso:NumeroOrgaoJustica'))
            )
            safe_fill_field(elemento_orgao, numOrgaoJustica, "Número do Órgão de Justiça")
        
        # Preenche Respectivo Tribunal
        if numTribunal:
            elemento_tribunal = wait.until(
                EC.presence_of_element_located(
                    (By.ID, 'fPP:numeroProcesso:respectivoTribunal'))
            )
            safe_fill_field(elemento_tribunal, numTribunal, "Número do Tribunal")
        
        # Preenche ANO DO PROCESSO - CRÍTICO
        if processoAno:
            logging.info(f"🗓️ Preenchendo ano do processo: {processoAno}")
            elemento_ano = wait.until(
                EC.presence_of_element_located(
                    (By.ID, 'fPP:numeroProcesso:Ano'))
            )
            
            # Método especial para o campo ano (mais crítico)
            max_attempts = 3
            success = False
            
            for attempt in range(max_attempts):
                logging.info(f"🗓️ Tentativa {attempt + 1} de preenchimento do ano...")
                
                # Move para o elemento e garante foco
                driver.execute_script("arguments[0].scrollIntoView(true);", elemento_ano)
                time.sleep(0.5)
                
                # Clica no campo várias vezes para garantir foco
                elemento_ano.click()
                time.sleep(0.3)
                elemento_ano.click()
                time.sleep(0.3)
                
                # Limpa o campo completamente
                driver.execute_script("arguments[0].value = '';", elemento_ano)
                elemento_ano.send_keys(Keys.CONTROL + "a")
                elemento_ano.send_keys(Keys.DELETE)
                time.sleep(0.5)
                
                # Preenche caractere por caractere com delay
                for char in processoAno:
                    elemento_ano.send_keys(char)
                    time.sleep(0.1)  # Delay entre caracteres
                
                time.sleep(0.5)
                
                # Verifica se preencheu corretamente
                valor_atual = elemento_ano.get_attribute('value')
                if valor_atual == processoAno:
                    logging.info(f"✅ Ano preenchido corretamente: {processoAno}")
                    success = True
                    break
                else:
                    logging.warning(f"⚠️ Tentativa {attempt + 1} falhou. Esperado: {processoAno}, Atual: {valor_atual}")
                    time.sleep(1)
            
            if not success:
                # Última tentativa com JavaScript puro
                logging.info("🔄 Última tentativa com JavaScript...")
                driver.execute_script(f"arguments[0].value = '{processoAno}';", elemento_ano)
                driver.execute_script("""
                    var element = arguments[0];
                    element.focus();
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                    element.dispatchEvent(new Event('change', { bubbles: true }));
                    element.blur();
                """, elemento_ano)
                time.sleep(1)
                
                valor_final = elemento_ano.get_attribute('value')
                if valor_final == processoAno:
                    logging.info(f"✅ Ano preenchido com JavaScript: {processoAno}")
                else:
                    logging.error(f"❌ FALHA CRÍTICA: Não foi possível preencher o ano corretamente!")
        
        # Seleção do Órgão Julgador
        if orgaoJulgadorCombo:
            try:
                elemento_orgao_julgador = wait.until(
                    EC.presence_of_element_located(
                        (By.ID, 'fPP:orgaoJulgadorComboDecoration:orgaoJulgadorCombo'))
                )
                lista_orgao_julgador = Select(elemento_orgao_julgador)
                
                # Tenta selecionar por texto visível primeiro
                try:
                    lista_orgao_julgador.select_by_visible_text(orgaoJulgadorCombo)
                    logging.info(f"✅ Órgão julgador selecionado por texto: {orgaoJulgadorCombo}")
                except:
                    # Se não encontrar por texto, tenta selecionar por valor
                    try:
                        lista_orgao_julgador.select_by_value(orgaoJulgadorCombo)
                        logging.info(f"✅ Órgão julgador selecionado por valor: {orgaoJulgadorCombo}")
                    except:
                        # Se nenhuma das opções funcionar, tenta buscar por texto parcial
                        options = lista_orgao_julgador.options
                        option_found = False
                        for option in options:
                            if orgaoJulgadorCombo.upper() in option.text.upper():
                                lista_orgao_julgador.select_by_visible_text(option.text)
                                logging.info(f"✅ Órgão julgador selecionado por texto parcial: {option.text}")
                                option_found = True
                                break
                        
                        if not option_found:
                            logging.warning(f"⚠️ Não foi possível selecionar o órgão julgador: {orgaoJulgadorCombo}")
            
            except Exception as e:
                logging.error(f"❌ Erro ao selecionar órgão julgador: {e}")
        
        # Preenche dados OAB se fornecidos
        if estadoOAB and numeroOAB:
            elemento_numero_oab = wait.until(
                EC.presence_of_element_located(
                    (By.ID, 'fPP:decorationDados:numeroOAB'))
            )
            safe_fill_field(elemento_numero_oab, numeroOAB, "Número OAB")
            
            elemento_estado_oab = wait.until(
                EC.presence_of_element_located(
                    (By.ID, 'fPP:decorationDados:ufOABCombo'))
            )
            lista_estados_oab = Select(elemento_estado_oab)
            lista_estados_oab.select_by_value(estadoOAB)
            logging.info(f"✅ Estado OAB selecionado: {estadoOAB}")
        
        # Preenche data de autuação inicial
        if dataAutuacaoDe:
            elemento_data_inicio = wait.until(
                EC.presence_of_element_located(
                    (By.ID, 'fPP:dataAutuacaoDecoration:dataAutuacaoInicioInputDate'))
            )
            safe_fill_field(elemento_data_inicio, dataAutuacaoDe, "Data de Autuação (De)")
        
        # Preenche data de autuação final
        if dataAutuacaoAte:
            elemento_data_fim = wait.until(
                EC.presence_of_element_located(
                    (By.ID, 'fPP:dataAutuacaoDecoration:dataAutuacaoFimInputDate'))
            )
            safe_fill_field(elemento_data_fim, dataAutuacaoAte, "Data de Autuação (Até)")
        
        # Preenche Assunto
        if Assunto:
            elemento_assunto = wait.until(
                EC.presence_of_element_located((By.ID, 'fPP:j_id237:assunto'))
            )
            safe_fill_field(elemento_assunto, Assunto, "Assunto")
        
        # Preenche Classe Judicial
        if classeJudicial:
            elemento_classe = wait.until(
                EC.presence_of_element_located(
                    (By.ID, 'fPP:j_id246:classeJudicial'))
            )
            safe_fill_field(elemento_classe, classeJudicial, "Classe Judicial")
        
        # Preenche Nome da Parte
        if nomeParte:
            elemento_nome_parte = wait.until(
                EC.presence_of_element_located((By.ID, 'fPP:j_id150:nomeParte'))
            )
            safe_fill_field(elemento_nome_parte, nomeParte, "Nome da Parte")
        
        # Preenche Outros Nomes/Alcunha
        if outrosNomesAlcunha:
            elemento_alcunha = wait.until(
                EC.presence_of_element_located(
                    (By.ID, 'fPP:j_id159:outrosNomesAlcunha'))
            )
            safe_fill_field(elemento_alcunha, outrosNomesAlcunha, "Outros Nomes/Alcunha")
        
        # Preenche Nome do Advogado
        if nomeAdvogado:
            elemento_advogado = wait.until(
                EC.presence_of_element_located((By.ID, 'fPP:j_id168:nomeAdvogado'))
            )
            safe_fill_field(elemento_advogado, nomeAdvogado, "Nome do Advogado")
        
        # Aguarda antes de clicar no botão de busca
        time.sleep(2)
        
        # Clica no botão de buscar processos
        btn_procurar = wait.until(
            EC.element_to_be_clickable((By.ID, 'fPP:searchProcessos'))
        )
        
        # Scroll para o botão e clica
        driver.execute_script("arguments[0].scrollIntoView(true);", btn_procurar)
        time.sleep(1)
        btn_procurar.click()
        
        logging.info("🔍 Busca de processos iniciada com sucesso!")
        
    except Exception as e:
        logging.error(f"❌ Erro durante a busca de processos: {e}")
        # Salva screenshot para debug
        try:
            driver.save_screenshot("error_search_process.png")
            logging.info("📸 Screenshot de erro salvo: error_search_process.png")
        except:
            pass
        raise e


def get_total_pages():
    try:
        total_results_element = wait.until(
            EC.visibility_of_element_located(
                (By.XPATH,
                 "//table[contains(@id, 'processosTable')]//tfoot//span[contains(text(), 'resultados encontrados')]")
            )
        )
        try:
            total_results_text = driver.find_element(
                By.XPATH, "//table[contains(@id, 'processosTable')]//tfoot").text
            logging.info(f"Texto do rodapé da tabela: {total_results_text}")
            match = re.search(
                r'(\d+)\s+resultados encontrados', total_results_text)
            if match:
                total_results_number = int(match.group(1))
                total_pages = math.ceil(total_results_number / 20)
                return total_pages
            else:
                logging.warning(
                    "Não foi possível extrair o número total de resultados.")
                return 0
        except Exception as e:
            logging.error(f"Erro ao obter o número total de páginas: {e}")
            return 0
    except Exception as e:
        logging.error(f"Erro ao obter o número total de páginas: {e}")
        return 0


def collect_process_date():
    WebDriverWait(driver, 50).until(
        EC.presence_of_element_located((By.ID, 'fPP:processosTable:tb'))
    )
    process_data_list = []
    total_pages = get_total_pages()
    logging.info(f"Total de páginas para processar: {total_pages}")

    for page_num in range(1, total_pages + 1):
        logging.info(f"Processando página {page_num} de {total_pages}")
        table_body = WebDriverWait(driver, 50).until(
            EC.presence_of_element_located((By.ID, 'fPP:processosTable:tb'))
        )

        rows = table_body.find_elements(By.XPATH, "./tr")
        logging.info(f"Número de processos encontrados na página: {len(rows)}")

        for row in rows:
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 10:
                    logging.warning(
                        "Número insuficiente de colunas na linha, pulando.")
                    continue

                try:
                    a_tag = cells[0].find_element(By.TAG_NAME, "a")
                    numero_do_processo = a_tag.get_attribute('title').strip()
                except Exception:
                    numero_do_processo = cells[0].text.strip()

                orgao_julgador = cells[2].text.strip()
                autuado_em = cells[4].text.strip()
                classe_judicial = cells[5].text.strip()
                polo_ativo = cells[6].text.strip()
                polo_passivo = cells[7].text.strip()
                ultima_movimentacao = cells[9].text.strip()

                process_data_list.append({
                    "Número do Processo": numero_do_processo,
                    "Órgão Julgador": orgao_julgador,
                    "Autuado em": autuado_em,
                    "Classe Judicial": classe_judicial,
                    "Polo Ativo": polo_ativo,
                    "Polo Passivo": polo_passivo,
                    "Última Movimentação": ultima_movimentacao
                })

                logging.info(f"Processo coletado: {numero_do_processo}")
            except Exception as e:
                logging.error(f"Erro ao extrair dados da linha: {e}")
                continue

        if page_num < total_pages:
            try:
                wait.until(EC.invisibility_of_element(
                    (By.ID, 'j_id136:modalStatusCDiv')))
                next_page_button = wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//td[contains(@onclick, 'next')]"))
                )
                next_page_button.click()
                wait.until(EC.staleness_of(table_body))
            except Exception as e:
                logging.error(f"Erro ao navegar para a próxima página: {e}")
                break
        else:
            logging.info("Última página alcançada.")
            time.sleep(2)

    return process_data_list


def save_data_to_excel(data_list, filename="./docs/Pesqisa_Geral_Dados.xlsx"):
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Dados dos Processos"

        headers = ['Número do Processo', 'Órgão Julgador', 'Autuado em', 'Classe Judicial',
                   'Polo Ativo', 'Polo Passivo', 'Última Movimentação']
        ws.append(headers)

        bold_font = Font(bold=True)
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = bold_font

        for data in data_list:
            ws.append([
                data.get('Número do Processo', ''),
                data.get('Órgão Julgador', ''),
                data.get('Autuado em', ''),
                data.get('Classe Judicial', ''),
                data.get('Polo Ativo', ''),
                data.get('Polo Passivo', ''),
                data.get('Última Movimentação', '')
            ])

        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if cell.value and len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column_letter].width = adjusted_width

        wb.save(filename)
        logging.info(f"Dados salvos com sucesso no xlsx '{filename}'.")
    except Exception as e:
        logging.error(
            f"Ocorreu uma exceção ao salvar os dados no Excel. Erro: {e}")
        raise e


def main():
    global driver, wait

    load_dotenv()
    user, password = os.getenv("USER"), os.getenv("PASSWORD")
    profile = "V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL / Assessoria / Assessor"

    # Inicializa bot com limpeza automática de cache
    bot = PjeConsultaAutomator(
        clear_cache_on_start=True,  # Limpa cache na inicialização
        auto_clear_cache=True       # Ativa limpeza automática
    )
    driver = bot.driver
    wait = bot.wait

    try:
        # Limpeza adicional antes do login (opcional, mas recomendado)
        print("🔧 Executando limpeza final antes do login...")
        bot.clear_browser_cache()
        time.sleep(3)

        # Procede com login e demais operações
        bot.login(user, password)
        bot.select_profile(profile)

        ano = "1996"

        search_process(
            numOrgaoJustica="",
            numTribunal="", 
            processoAno="",
            numeroOAB="",
            estadoOAB="",
            dataAutuacaoDe="01/01/1981",
            dataAutuacaoAte="31/12/2004",
            Assunto="",
            classeJudicial="",
            nomeParte="",
            nomeAdvogado="LUIZ CESAR DONATO DA CRUZ",
            orgaoJulgadorCombo="V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL"
        )

        time.sleep(20)

        process_data = collect_process_date()

        logging.info(f"Dados dos processos coletados com sucesso")
        logging.info(f"Salvando dados json...")
        filename = f'Processos{ano}LCDC'

        if process_data:
            bot.save_to_json(process_data, filename)
            save_data_to_excel(process_data, f'./docs/{filename}.xlsx')
        else:
            logging.info("Nenhum processo encontrado para salvar.")

    except Exception as e:
        logging.error(f"Erro durante execução: {e}")
        
        if "429" in str(e) or "rate limit" in str(e).lower():
            print("🔄 Erro de rate limit detectado. Reiniciando sessão...")
            bot.clear_cache_and_restart_session()
            time.sleep(10)

    finally:
        bot.close()


if __name__ == "__main__":
    main()
