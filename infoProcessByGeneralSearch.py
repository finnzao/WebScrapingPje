import os
import json
import math
import re
import time
import logging
from dotenv import load_dotenv

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from openpyxl import Workbook
from openpyxl.styles import Font

from utils.pje_automation import PjeConsultaAutomator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

driver = None
wait = None

def search_process(optionSearch):
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    icon_search_button = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'li#liConsultaProcessual i.fas'))
    )
    icon_search_button.click()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'frameConsultaProcessual')))

    ElementoNumOrgaoJutica = wait.until(
        EC.presence_of_element_located((By.ID, 'fPP:numeroProcesso:NumeroOrgaoJustica'))
    )
    ElementoNumOrgaoJutica.send_keys(optionSearch.get('numOrgaoJustica'))

    if optionSearch.get('estadoOAB'):
        ElementoNumeroOAB = wait.until(
            EC.presence_of_element_located((By.ID, 'fPP:decorationDados:numeroOAB'))
        )
        ElementoNumeroOAB.send_keys(optionSearch.get('numeroOAB'))
        ElementoEstadosOAB = wait.until(
            EC.presence_of_element_located((By.ID, 'fPP:decorationDados:ufOABCombo'))
        )
        listaEstadosOAB = Select(ElementoEstadosOAB)
        listaEstadosOAB.select_by_value(optionSearch.get('estadoOAB'))

    if optionSearch.get('dataAutuacaoDe'):
        ElementoDataAutuacao = wait.until(
            EC.presence_of_element_located((By.ID, 'fPP:dataAutuacaoDecoration:dataAutuacaoInicioInputDate'))
        )
        ElementoDataAutuacao.send_keys(optionSearch.get('dataAutuacaoDe'))

    if optionSearch.get('dataAutuacaoAte'):
        ElementoDataAutuacaoAte = wait.until(
            EC.presence_of_element_located((By.ID, 'fPP:dataAutuacaoDecoration:dataAutuacaoFimInputDate'))
        )
        ElementoDataAutuacaoAte.send_keys(optionSearch.get('dataAutuacaoAte'))

    if optionSearch.get('Assunto'):
        ElementoAssunto = wait.until(
            EC.presence_of_element_located((By.ID, 'fPP:j_id236:assunto'))
        )
        ElementoAssunto.send_keys(optionSearch.get('Assunto'))

    btnProcurarProcesso = wait.until(
        EC.presence_of_element_located((By.ID, 'fPP:searchProcessos'))
    )
    btnProcurarProcesso.click()

    consulta_classe = wait.until(
        EC.presence_of_element_located((By.ID, 'fPP:j_id245:classeJudicial'))
    )
    consulta_classe.send_keys(optionSearch.get('classeJudicial'))

    ElementonomeDaParte = wait.until(
        EC.presence_of_element_located((By.ID, 'fPP:j_id150:nomeParte'))
    )
    ElementonomeDaParte.send_keys(optionSearch.get('nomeParte'))

    btnProcurarProcesso = wait.until(
        EC.presence_of_element_located((By.ID, 'fPP:searchProcessos'))
    )
    btnProcurarProcesso.click()

def get_total_pages():
    try:
        total_results_element = wait.until(
            EC.visibility_of_element_located(
                (By.XPATH, "//table[contains(@id, 'processosTable')]//tfoot//span[contains(text(), 'resultados encontrados')]")
            )
        )
        try:
            total_results_text = driver.find_element(By.XPATH, "//table[contains(@id, 'processosTable')]//tfoot").text
            logging.info(f"Texto do rodapé da tabela: {total_results_text}")
            match = re.search(r'(\d+)\s+resultados encontrados', total_results_text)
            if match:
                total_results_number = int(match.group(1))
                total_pages = math.ceil(total_results_number / 20)
                return total_pages
            else:
                logging.warning("Não foi possível extrair o número total de resultados.")
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
                    logging.warning("Número insuficiente de colunas na linha, pulando.")
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
                wait.until(EC.invisibility_of_element((By.ID, 'j_id136:modalStatusCDiv')))
                next_page_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//td[contains(@onclick, 'next')]"))
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
        logging.error(f"Ocorreu uma exceção ao salvar os dados no Excel. Erro: {e}")
        raise e

def main():
    global driver, wait

    load_dotenv()
    user, password = os.getenv("USER"), os.getenv("PASSWORD")
    #profile = os.getenv("PROFILE")
    profile = "V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL / Assessoria / Assessor"
    bot = PjeConsultaAutomator()
    driver = bot.driver
    wait = bot.wait
    config = bot.loadConfig()
    optionSearch = config["optionSearch"]

    bot.login(user, password)
    # bot.skip_token()
    bot.select_profile(profile)

    search_process(optionSearch)
    time.sleep(40)

    process_data = collect_process_date()
    bot.close()

    logging.info(f"Dados dos processos coletados com sucesso")
    logging.info(f"Salvando dados json...")
    if process_data:
        bot.save_to_json(process_data,filename="PesquisaGeral")
        save_data_to_excel(process_data)
    else:
        logging.info("Nenhum processo encontrado para salvar.")

if __name__ == "__main__":
    main()
