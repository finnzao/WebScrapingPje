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

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

driver = None
wait = None


def search_process(numOrgaoJustica="0216", numTribunal="05", processoAno='', numeroOAB="", estadoOAB="", dataAutuacaoDe="",
                   dataAutuacaoAte="", Assunto="", classeJudicial="", nomeParte="", nomeAdvogado="",
                   outrosNomesAlcunha="", orgaoJulgadorCombo="V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL"):
    """
    Realiza busca de processos no PJE

    Args:
        numOrgaoJustica (str): Número do órgão de justiça (padrão: "0216")
        numTribunal (str): Número do tribunal (padrão: "05")
        numeroOAB (str): Número da OAB
        estadoOAB (str): Estado da OAB
        dataAutuacaoDe (str): Data inicial de autuação
        dataAutuacaoAte (str): Data final de autuação
        Assunto (str): Assunto do processo
        classeJudicial (str): Classe judicial
        nomeParte (str): Nome da parte
        nomeAdvogado (str): Nome do advogado
        outrosNomesAlcunha (str): Outros nomes/alcunha
        orgaoJulgadorCombo (str): Órgão julgador (padrão: "V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL")
    """
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
    icon_search_button = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, 'li#liConsultaProcessual i.fas'))
    )
    icon_search_button.click()
    wait.until(EC.frame_to_be_available_and_switch_to_it(
        (By.ID, 'frameConsultaProcessual')))

    ElementoNumOrgaoJutica = wait.until(
        EC.presence_of_element_located(
            (By.ID, 'fPP:numeroProcesso:NumeroOrgaoJustica'))
    )
    ElementoNumOrgaoJutica.send_keys(numOrgaoJustica)

    ElementoRespectivoTribunal = wait.until(
        EC.presence_of_element_located(
            (By.ID, 'fPP:numeroProcesso:respectivoTribunal'))
    )
    ElementoRespectivoTribunal.send_keys(numTribunal)

    # Seleção do Órgão Julgador
    if orgaoJulgadorCombo:
        try:
            ElementoOrgaoJulgador = wait.until(
                EC.presence_of_element_located(
                    (By.ID, 'fPP:orgaoJulgadorComboDecoration:orgaoJulgadorCombo'))
            )
            listaOrgaoJulgador = Select(ElementoOrgaoJulgador)

            # Tenta selecionar por texto visível primeiro
            try:
                listaOrgaoJulgador.select_by_visible_text(orgaoJulgadorCombo)
                logging.info(
                    f"Órgão julgador selecionado por texto: {orgaoJulgadorCombo}")
            except:
                # Se não encontrar por texto, tenta selecionar por valor
                try:
                    listaOrgaoJulgador.select_by_value(orgaoJulgadorCombo)
                    logging.info(
                        f"Órgão julgador selecionado por valor: {orgaoJulgadorCombo}")
                except:
                    # Se nenhuma das opções funcionar, tenta buscar por texto parcial
                    options = listaOrgaoJulgador.options
                    option_found = False
                    for option in options:
                        if orgaoJulgadorCombo.upper() in option.text.upper():
                            listaOrgaoJulgador.select_by_visible_text(
                                option.text)
                            logging.info(
                                f"Órgão julgador selecionado por texto parcial: {option.text}")
                            option_found = True
                            break

                    if not option_found:
                        logging.warning(
                            f"Não foi possível selecionar o órgão julgador: {orgaoJulgadorCombo}")

        except Exception as e:
            logging.error(f"Erro ao selecionar órgão julgador: {e}")

    if estadoOAB and numeroOAB:
        ElementoNumeroOAB = wait.until(
            EC.presence_of_element_located(
                (By.ID, 'fPP:decorationDados:numeroOAB'))
        )
        ElementoNumeroOAB.send_keys(numeroOAB)
        ElementoEstadosOAB = wait.until(
            EC.presence_of_element_located(
                (By.ID, 'fPP:decorationDados:ufOABCombo'))
        )
        listaEstadosOAB = Select(ElementoEstadosOAB)
        listaEstadosOAB.select_by_value(estadoOAB)

    if dataAutuacaoDe:
        ElementoDataAutuacao = wait.until(
            EC.presence_of_element_located(
                (By.ID, 'fPP:dataAutuacaoDecoration:dataAutuacaoInicioInputDate'))
        )
        ElementoDataAutuacao.send_keys(dataAutuacaoDe)

    if processoAno:
        ElementoProcessoAno = wait.until(
            EC.presence_of_element_located(
                (By.ID, 'fPP:numeroProcesso:Ano'))
        )
        ElementoProcessoAno.send_keys(processoAno)

    if dataAutuacaoAte:
        ElementoDataAutuacaoAte = wait.until(
            EC.presence_of_element_located(
                (By.ID, 'fPP:dataAutuacaoDecoration:dataAutuacaoFimInputDate'))
        )
        ElementoDataAutuacaoAte.send_keys(dataAutuacaoAte)

    if Assunto:
        ElementoAssunto = wait.until(
            EC.presence_of_element_located((By.ID, 'fPP:j_id237:assunto'))
        )
        ElementoAssunto.send_keys(Assunto)

    if classeJudicial:
        consulta_classe = wait.until(
            EC.presence_of_element_located(
                (By.ID, 'fPP:j_id246:classeJudicial'))
        )
        consulta_classe.send_keys(classeJudicial)

    if nomeParte:
        ElementonomeDaParte = wait.until(
            EC.presence_of_element_located((By.ID, 'fPP:j_id150:nomeParte'))
        )
        ElementonomeDaParte.send_keys(nomeParte)

    if outrosNomesAlcunha:
        ElementonomeDaParte = wait.until(
            EC.presence_of_element_located(
                (By.ID, 'fPP:j_id159:outrosNomesAlcunha'))
        )
        ElementonomeDaParte.send_keys(outrosNomesAlcunha)

    if nomeAdvogado:
        ElementonomeDaParte = wait.until(
            EC.presence_of_element_located((By.ID, 'fPP:j_id168:nomeAdvogado'))
        )
        ElementonomeDaParte.send_keys(nomeAdvogado)

    btnProcurarProcesso = wait.until(
        EC.presence_of_element_located((By.ID, 'fPP:searchProcessos'))
    )
    btnProcurarProcesso.click()


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
    # profile = os.getenv("PROFILE")
    profile = "V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL / Assessoria / Assessor"
    bot = PjeConsultaAutomator()
    driver = bot.driver
    wait = bot.wait

    bot.login(user, password)
    # bot.skip_token()
    bot.select_profile(profile)
    ano = "2016"
    time.sleep(5)
    search_process(
        numOrgaoJustica="0216",
        numTribunal="05",
        processoAno=ano,
        numeroOAB="",
        estadoOAB="",
        dataAutuacaoDe="",
        dataAutuacaoAte="",
        Assunto="",
        classeJudicial="",
        nomeParte="",
        nomeAdvogado="LUIZ CESAR DONATO DA CRUZ",
        orgaoJulgadorCombo="V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL"
    )

    time.sleep(40)

    process_data = collect_process_date()
    bot.close()

    logging.info(f"Dados dos processos coletados com sucesso")
    logging.info(f"Salvando dados json...")
    filename = f'Processos{ano}LCDC'
    if process_data:
        bot.save_to_json(process_data, filename)
        save_data_to_excel(process_data, f'./docs/{filename}.xlsx')
    else:
        logging.info("Nenhum processo encontrado para salvar.")


if __name__ == "__main__":
    main()
