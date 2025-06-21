from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv
from typing import TypedDict, NotRequired, Any, Dict
import time
import os
import json

# Tipos para o config.json
class OptionSearch(TypedDict):
    nomeParte: NotRequired[str]
    numOrgaoJustica: NotRequired[str]
    Assunto: NotRequired[str]
    NomeDoRepresentante: NotRequired[str]
    Alcunha: NotRequired[str]
    classeJudicial: NotRequired[str]
    numDoc: NotRequired[str]
    estadoOAB: NotRequired[str]
    numeroOAB: NotRequired[str]
    dataAutuacaoDe: NotRequired[str]
    dataAutuacaoAte: NotRequired[str]

class LoginInfo(TypedDict):
    oc: str

class ConfigData(TypedDict):
    optionSearch: OptionSearch
    LoginInfo: LoginInfo

class PjeConsultaAutomator:
    load_dotenv()
    user, password = os.getenv("USER"), os.getenv("PASSWORD")

    def __init__(
        self,
        driver: webdriver.Chrome = None,
        download_directory: str = None,
        custom_prefs: dict = None,
        wait_timeout: int = 50
    ):
        if driver is None:
            self.driver, self.wait = self.initialize_driver(
                download_directory=download_directory,
                prefs=custom_prefs,
                wait_timeout=wait_timeout
            )
        else:
            self.driver = driver
            self.wait = WebDriverWait(self.driver, wait_timeout)

    def initialize_driver(
        self,
        download_directory: str = None,
        prefs: dict = None,
        wait_timeout: int = 50,
        headless: bool = False
    ) -> tuple[webdriver.Chrome, WebDriverWait]:
        """
        Inicializa o driver do Chrome com configurações personalizadas.
        
        Args:
            download_directory (str, optional): Diretório para downloads. 
                Se None, usa pasta padrão em Downloads/processosBaixadosEtiqueta
            prefs (dict, optional): Preferências customizadas do Chrome. 
                Se None, usa preferências padrão
            wait_timeout (int, optional): Tempo de espera para WebDriverWait. Padrão 50 segundos
            headless (bool, optional): Se True, executa em modo headless (sem interface gráfica). 
                Padrão False (navegador visível)
        
        Returns:
            tuple: (driver, wait) - instâncias do Chrome WebDriver e WebDriverWait
        """
        chrome_options = webdriver.ChromeOptions()
    
        # Configurar modo headless se solicitado
        if headless:
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            print("Modo HEADLESS ativado - navegador não será visível")
    
        if not download_directory:
            user_home = os.path.expanduser("~")
            download_directory = os.path.join(user_home, "Downloads", "processosBaixadosEtiqueta")
    
        os.makedirs(download_directory, exist_ok=True)
        print(f"Diretório de download configurado para: {download_directory}")
    
        default_prefs = {
            "plugins.always_open_pdf_externally": True,
            "download.default_directory": download_directory,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
    
        # Em modo headless, adicionar configurações extras para garantir downloads
        if headless:
            default_prefs.update({
                "download.extensions_to_open": "applications/pdf",
                "profile.default_content_settings.popups": 0,
                "profile.content_settings.exceptions.automatic_downloads.*.setting": 1
            })
    
        prefs = prefs or default_prefs
        chrome_options.add_experimental_option("prefs", prefs)
    
        driver = webdriver.Chrome(options=chrome_options)
        wait = WebDriverWait(driver, wait_timeout)
    
        # Em modo headless, habilitar download via CDP (Chrome DevTools Protocol)
        if headless:
            driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": download_directory
            })
    
        return driver, wait

    def _detect_redirect_loop(self):
        time.sleep(3)
        try:
            error_element = self.driver.find_element(By.ID, 'sub-frame-error-details')
            if "Redirecionamento em excesso" in error_element.text:
                return True
        except:
            pass
        return False


    def login(self, user=user, password=password):
        login_url = 'https://pje.tjba.jus.br/pje/login.seam'
        self.driver.get(login_url)

        if self._detect_redirect_loop():
            print("Redirecionamento em excesso detectado. Recarregando a página...")
            self.driver.refresh()
            time.sleep(2)

        self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ssoFrame')))
        self.wait.until(EC.presence_of_element_located((By.ID, 'username'))).send_keys(user)
        self.wait.until(EC.presence_of_element_located((By.ID, 'password'))).send_keys(password)
        self.wait.until(EC.presence_of_element_located((By.ID, 'kc-login'))).click()

        if self._detect_redirect_loop():
            print("Redirecionamento em excesso detectado após login. Recarregando a página...")
            self.driver.refresh()
            time.sleep(2)

        self.driver.switch_to.default_content()

        try:
            WebDriverWait(self.driver, 6).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'dropdown-toggle'))
            )
            print("Login efetuado com sucesso.")
        except TimeoutException:
            print("Login falhou. Elemento de perfil não apareceu. Recarregando a página...")
            self.driver.refresh()
        time.sleep(2)


    def skip_token(self):
        self.wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(text(),'Prosseguir sem o Token')]"))).click()

    def select_profile(self, profile):
        try:
            dropdown = self.wait.until(EC.element_to_be_clickable(
                (By.CLASS_NAME, "dropdown-toggle")))
            dropdown.click()
            opt = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, f"//a[contains(text(),'{profile}')]")))
            self.driver.execute_script("arguments[0].click();", opt)
            print(f"[OK] Perfil '{profile}' selecionado")

        except Exception as e:
            print(f"[select_profile] Erro ao selecionar perfil '{profile}'. Continuando mesmo Assim")
            return



    def save_to_json(self, data, filename="ResultadoProcessosPesquisa"):
        os.makedirs("./docs", exist_ok=True)
        with open(f"./docs/{filename}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def loadConfig(self) -> ConfigData:
        with open('config.json', 'r', encoding='utf-8') as f:
            config: ConfigData = json.load(f)
        return config

    def update_config(self, updates: Dict[str, Any], file: str = "config.json") -> None:
        with open(file, "r", encoding="utf-8") as f:
            config = json.load(f)

        def recursive_update(d: dict, u: dict):
            for k, v in u.items():
                if isinstance(v, dict) and isinstance(d.get(k), dict):
                    recursive_update(d[k], v)
                else:
                    d[k] = v

        recursive_update(config, updates)

        with open(file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

        print("Arquivo config.json atualizado com sucesso.")

    def close(self):
        self.driver.quit()

    def download_files_from_download_area(self, process_numbers, tag_name=None, partial_report=None, save_report=True):
        """
        Acessa a página de downloads do PJe e baixa apenas os processos especificados.

        Args:
            process_numbers (list): Lista de números de processos para baixar
            tag_name (str, optional): Nome da etiqueta para identificação no relatório
            partial_report (dict, optional): Relatório parcial com informações prévias dos processos
            save_report (bool): Se deve salvar o relatório em arquivo JSON

        Returns:
            dict: Relatório completo com informações sobre os downloads realizados
        """


        # Prepara o relatório de resultados
        results_report = self._prepare_download_area_report(process_numbers, tag_name, partial_report)

        if not process_numbers:
            self._log_info("Nenhum processo para verificar na área de download.")
            results_report["resumoFinal"]["sucessoTotal"] = results_report["resumoFinal"]["downloadsDiretos"]

            if save_report:
                self._save_download_report(results_report, tag_name)
            return results_report

        try:
            # Acessa a página de downloads
            self._log_info(f"\nAcessando área de download para verificar {len(process_numbers)} processos...")
            self.driver.get('https://pje.tjba.jus.br/pje/AreaDeDownload/listView.seam')

            # Aguarda e entra no iframe
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ngFrame')))
            self._log_info("Dentro do iframe 'ngFrame'.")

            # Aguarda a tabela carregar
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'table')))
            self._log_info("Tabela de downloads carregada.")

            # Processa os downloads
            downloaded_numbers = self._process_download_table(process_numbers, results_report, tag_name)

            # Identifica processos não encontrados
            self._update_not_found_processes(process_numbers, downloaded_numbers, results_report)

            # Volta ao conteúdo principal
            self.driver.switch_to.default_content()
            self._log_info("Voltando para o conteúdo principal.")

        except Exception as e:
            self._log_error(f"Erro ao acessar área de download: {e}")
            self._save_exception_screenshot("download_area_exception.png")

        # Atualiza resumo final
        self._update_final_summary(results_report)

        # Salva relatório se solicitado
        if save_report:
            self._save_download_report(results_report, tag_name)

        self._print_download_summary(results_report)

        return results_report

    def _prepare_download_area_report(self, process_numbers, tag_name, partial_report):
        """Prepara a estrutura inicial do relatório de downloads."""
        base_report = {
            "nomeEtiqueta": tag_name or "Não especificada",
            "dataHoraInicio": time.strftime("%Y-%m-%d %H:%M:%S"),
            "dataHoraFinalizacao": None,
            "processosDetalhados": [],
            "areaDownload": {
                "processosVerificados": len(process_numbers),
                "processosBaixados": [],
                "processosNaoEncontrados": [],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "resumoFinal": {
                "totalProcessosAnalisados": 0,
                "downloadsDiretos": 0,
                "verificadosAreaDownload": len(process_numbers),
                "baixadosAreaDownload": 0,
                "naoEncontradosAreaDownload": 0,
                "semDocumento": 0,
                "erros": 0,
                "sucessoTotal": 0
            }
        }

        # Se houver relatório parcial, integra as informações
        if partial_report:
            base_report["tipoDocumento"] = partial_report.get("tipoDocumento", "Não especificado")
            base_report["processosDetalhados"] = partial_report.get("processosAnalisados", [])

            if "resumo" in partial_report:
                resumo = partial_report["resumo"]
                base_report["resumoFinal"]["totalProcessosAnalisados"] = resumo.get("totalProcessos", 0)
                base_report["resumoFinal"]["downloadsDiretos"] = resumo.get("downloadsDiretos", 0)
                base_report["resumoFinal"]["semDocumento"] = resumo.get("semDocumento", 0)
                base_report["resumoFinal"]["erros"] = resumo.get("erros", 0)

        return base_report

    def _process_download_table(self, process_numbers, results_report, tag_name):
        """Processa a tabela de downloads e baixa os processos especificados."""
        rows = self.wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//table//tbody//tr")))
        self._log_info(f"Número total de processos na lista de downloads: {len(rows)}")

        # Conjunto para verificação rápida
        target_processes = set(process_numbers)
        downloaded_numbers = set()

        for row in rows:
            try:
                process_number_td = row.find_element(By.XPATH, "./td[1]")
                process_number = process_number_td.text.strip()

                # Verifica se é um processo desejado e ainda não foi baixado
                if process_number in target_processes and process_number not in downloaded_numbers:
                    if tag_name:
                        self._log_info(f"Processo {process_number} da etiqueta '{tag_name}' encontrado. Baixando...")
                    else:
                        self._log_info(f"Processo {process_number} encontrado. Baixando...")

                    if self._download_process_from_row(row, process_number):
                        downloaded_numbers.add(process_number)
                        results_report["areaDownload"]["processosBaixados"].append(process_number)
                        self._update_process_status_in_report(results_report, process_number, "baixado_area_download")

            except Exception as e:
                self._log_error(f"Erro ao processar linha da tabela: {e}")
                continue
            
        return downloaded_numbers

    def _download_process_from_row(self, row, process_number):
        """Tenta baixar um processo específico da linha da tabela."""
        try:
            download_button = row.find_element(By.XPATH, "./td[last()]//button")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
            download_button.click()
            time.sleep(5)  # Aguarda o download iniciar
            return True
        except Exception as e:
            self._log_error(f"Erro ao baixar processo {process_number} da área de download: {e}")
            return False

    def _update_process_status_in_report(self, report, process_number, status):
        """Atualiza o status de um processo específico no relatório."""
        for proc in report.get("processosDetalhados", []):
            if proc.get("numero") == process_number:
                proc["statusDownload"] = status

                if status == "baixado_area_download":
                    proc["observacoes"] = proc.get("observacoes", "") + " - Baixado com sucesso da área de download"
                    proc["timestampAreaDownload"] = time.strftime("%Y-%m-%d %H:%M:%S")
                elif status == "nao_encontrado_area_download":
                    proc["observacoes"] = proc.get("observacoes", "") + " - Não encontrado na área de download"
                break

    def _update_not_found_processes(self, process_numbers, downloaded_numbers, results_report):
        """Identifica e atualiza processos que não foram encontrados na área de download."""
        not_found = [proc for proc in process_numbers if proc not in downloaded_numbers]
        results_report["areaDownload"]["processosNaoEncontrados"] = not_found

        for proc_num in not_found:
            self._update_process_status_in_report(results_report, proc_num, "nao_encontrado_area_download")

    def _update_final_summary(self, results_report):
        """Atualiza o resumo final do relatório."""
        results_report["dataHoraFinalizacao"] = time.strftime("%Y-%m-%d %H:%M:%S")

        area_download = results_report["areaDownload"]
        resumo_final = results_report["resumoFinal"]

        resumo_final["baixadosAreaDownload"] = len(area_download["processosBaixados"])
        resumo_final["naoEncontradosAreaDownload"] = len(area_download["processosNaoEncontrados"])
        resumo_final["sucessoTotal"] = (
            resumo_final["downloadsDiretos"] + 
            resumo_final["baixadosAreaDownload"]
        )

    def _save_download_report(self, report, tag_name):
        """Salva o relatório de downloads em arquivo JSON."""
        import os

        # Cria diretório se não existir
        os.makedirs(".logs", exist_ok=True)

        # Define nome do arquivo
        tag_suffix = f"_{tag_name}" if tag_name else ""
        filename = f".logs/processos_download{tag_suffix}_completo.json"

        # Salva o relatório
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=4)

        self._log_info(f"\nRelatório final salvo em {filename}")

    def _print_download_summary(self, report):
        """Imprime um resumo dos downloads realizados."""
        area_download = report["areaDownload"]
        resumo_final = report["resumoFinal"]

        self._log_info(f"Processos baixados da área de download: {len(area_download['processosBaixados'])}")
        self._log_info(f"Total de sucessos: {resumo_final['sucessoTotal']} de {resumo_final['totalProcessosAnalisados']}")

    def _log_info(self, message):
        """Método auxiliar para logging (pode ser expandido conforme necessário)."""
        print(message)

    def _log_error(self, message):
        """Método auxiliar para logging de erros."""
        print(f"[ERRO] {message}")

    def _save_exception_screenshot(self, filename):
        """Salva screenshot em caso de exceção."""
        import os

        directory = ".logs/exception"
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, filename)
        self.driver.save_screenshot(filepath)
        print(f"Screenshot de exceção salvo em: {filepath}")  
