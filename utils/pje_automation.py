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
import random

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
        wait_timeout: int = 50,
        clear_cache_on_start: bool = True,  # Novo parâmetro
        auto_clear_cache: bool = True       # Limpeza automática
    ):
        """
        Inicializa o PjeConsultaAutomator com opções de limpeza de cache.
        
        Args:
            clear_cache_on_start (bool): Limpa cache durante inicialização
            auto_clear_cache (bool): Ativa limpeza automática de cache
        """
        if driver is None:
            self.driver, self.wait = self.initialize_driver(
                download_directory=download_directory,
                prefs=custom_prefs,
                wait_timeout=wait_timeout,
                clear_cache=clear_cache_on_start
            )
        else:
            self.driver = driver
            self.wait = WebDriverWait(self.driver, wait_timeout)
        
        # Configuração de limpeza automática
        self.auto_clear_cache = auto_clear_cache
        
        # Executa limpeza manual adicional se solicitado
        if auto_clear_cache:
            print("🚀 Executando limpeza automática de cache...")
            self.clear_browser_cache()
            time.sleep(2)  # Aguarda estabilização

    def initialize_driver(
        self,
        download_directory: str = None,
        prefs: dict = None,
        wait_timeout: int = 50,
        headless: bool = False,
        clear_cache: bool = True  # Novo parâmetro
    ) -> tuple[webdriver.Chrome, WebDriverWait]:
        """
        Inicializa o driver do Chrome com configurações personalizadas.
        
        Args:
            clear_cache (bool): Se True, limpa cache e dados do navegador a cada inicialização
        """
        chrome_options = webdriver.ChromeOptions()
    
        # Configurações para limpeza de cache
        if clear_cache:
            # Força o Chrome a iniciar com perfil temporário (limpo)
            chrome_options.add_argument("--incognito")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            
            # Limpa cache e dados de navegação
            chrome_options.add_argument("--aggressive-cache-discard")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            
            # Força recarregamento de recursos
            chrome_options.add_argument("--disable-cache")
            chrome_options.add_argument("--disable-application-cache")
            chrome_options.add_argument("--disable-offline-load-stale-cache")
            chrome_options.add_argument("--disk-cache-size=0")
            chrome_options.add_argument("--media-cache-size=0")
            
            # Anti-detecção para evitar rate limiting
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            print("🧹 Cache será limpo automaticamente a cada inicialização")
    
        # Configurar modo headless se solicitado
        if headless:
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            if not clear_cache:  # Evita duplicar se já foi adicionado
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
    
        # Configurações adicionais para limpeza de cache via preferências
        if clear_cache:
            default_prefs.update({
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.cookie_controls_mode": 0,
                # Limpa dados ao fechar
                "profile.exit_type": "normal",
                "profile.exited_cleanly": True,
                # Configurações para evitar detecção
                "profile.default_content_setting_values.plugins": 1,
                "profile.content_settings.plugin_whitelist.adobe-flash-player": 1,
                "profile.content_settings.exceptions.plugins.*,*.per_resource.adobe-flash-player": 1
            })
    
        # Em modo headless, adicionar configurações extras
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
    
        # Limpeza adicional via DevTools após inicialização
        if clear_cache:
            try:
                # Limpa cache via Chrome DevTools Protocol
                driver.execute_cdp_cmd("Network.clearBrowserCache", {})
                driver.execute_cdp_cmd("Network.clearBrowserCookies", {})
                
                # Remove indicadores de automação
                driver.execute_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                    
                    window.chrome = {
                        runtime: {},
                    };
                    
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                """)
                
                print("✅ Cache e cookies limpos via DevTools")
            except Exception as e:
                print(f"⚠️ Aviso: Não foi possível limpar cache via DevTools: {e}")
    
        # Em modo headless, habilitar download via CDP
        if headless:
            driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": download_directory
            })
    
        return driver, wait

    def clear_browser_cache(self):
        """
        Limpa cache, cookies e dados de navegação manualmente.
        Chame este método antes do login para garantir estado limpo.
        """
        try:
            print("🧹 Iniciando limpeza manual de cache...")
            
            # Método 1: Via Chrome DevTools Protocol (mais eficaz)
            try:
                self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
                self.driver.execute_cdp_cmd("Network.clearBrowserCookies", {})
                self.driver.execute_cdp_cmd("Storage.clearDataForOrigin", {
                    "origin": "*",
                    "storageTypes": "all"
                })
                print("✅ Cache limpo via DevTools Protocol")
            except Exception as e:
                print(f"⚠️ Falha na limpeza via DevTools: {e}")
            
            # Método 2: Via JavaScript (backup)
            try:
                # Limpa localStorage e sessionStorage
                self.driver.execute_script("window.localStorage.clear();")
                self.driver.execute_script("window.sessionStorage.clear();")
                
                # Limpa cache de aplicação se disponível
                self.driver.execute_script("""
                    if ('caches' in window) {
                        caches.keys().then(function(names) {
                            names.forEach(function(name) {
                                caches.delete(name);
                            });
                        });
                    }
                """)
                print("✅ Storage local limpo via JavaScript")
            except Exception as e:
                print(f"⚠️ Falha na limpeza via JavaScript: {e}")
                
            # Método 3: Navegação para about:blank e reload
            try:
                self.driver.get("about:blank")
                time.sleep(1)
                print("✅ Navegador resetado para página em branco")
            except Exception as e:
                print(f"⚠️ Falha ao resetar navegador: {e}")
                
            print("🎯 Limpeza de cache concluída")
            
        except Exception as e:
            print(f"❌ Erro durante limpeza de cache: {e}")

    def clear_cache_and_restart_session(self):
        """
        Limpa cache e reinicia a sessão do navegador completamente.
        Use para casos onde a limpeza simples não resolve.
        """
        try:
            print("🔄 Reiniciando sessão completa do navegador...")
            
            # Salva configurações atuais
            current_url = self.driver.current_url if hasattr(self, 'driver') else None
            
            # Fecha o navegador atual
            if hasattr(self, 'driver'):
                self.driver.quit()
                time.sleep(2)
            
            # Reinicializa com cache limpo
            self.driver, self.wait = self.initialize_driver(clear_cache=True)
            
            print("✅ Sessão reiniciada com cache limpo")
            
            # Retorna à URL anterior se necessário
            if current_url and current_url != "about:blank":
                self.driver.get(current_url)
                
        except Exception as e:
            print(f"❌ Erro ao reiniciar sessão: {e}")
            # Tenta inicializar driver básico em caso de erro
            self.driver, self.wait = self.initialize_driver()

    def wait_with_random_delay(self, min_seconds=2, max_seconds=5):
        """
        Adiciona delay aleatório para evitar detecção de bot.
        """
        delay = random.uniform(min_seconds, max_seconds)
        print(f"⏱️ Aguardando {delay:.2f} segundos...")
        time.sleep(delay)

    def add_rate_limit_protection(self):
        """
        Adiciona proteções contra rate limiting.
        """
        try:
            # Headers para parecer mais humano
            self.driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            
            # Simula comportamento humano
            self.driver.execute_script("""
                // Remove indicadores de automação
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                // Remove propriedades do Chrome automation
                window.chrome = {
                    runtime: {},
                };
                
                // Remove propriedades do WebDriver
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            """)
            print("🛡️ Proteções anti-detecção ativadas")
        except Exception as e:
            print(f"⚠️ Falha ao aplicar proteções: {e}")

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
        """
        Realiza login no sistema PJE com a nova estrutura de formulário.
        
        Args:
            user (str): CPF/CNPJ do usuário
            password (str): Senha do usuário
        """
        try:
            # Aplica proteções antes do login
            self.add_rate_limit_protection()
            self.wait_with_random_delay(2, 4)
            
            login_url = 'https://pje.tjba.jus.br/pje/login.seam'
            self.driver.get(login_url)

            if self._detect_redirect_loop():
                print("Redirecionamento em excesso detectado. Recarregando a página...")
                self.driver.refresh()
                time.sleep(2)

            # Aguarda e preenche o campo de usuário (CPF/CNPJ)
            username_field = self.wait.until(EC.presence_of_element_located((By.ID, 'username')))
            username_field.clear()
            self.wait_with_random_delay(0.5, 1.5)  # Delay humano
            username_field.send_keys(user)
            print(f"CPF/CNPJ preenchido: {user}")

            # Aguarda e preenche o campo de senha
            password_field = self.wait.until(EC.presence_of_element_located((By.ID, 'password')))
            password_field.clear()
            self.wait_with_random_delay(0.5, 1.5)  # Delay humano
            password_field.send_keys(password)
            print("Senha preenchida")

            # Aguarda antes de clicar no botão
            self.wait_with_random_delay(1, 2)
            
            # Clica no botão de entrar
            login_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'btnEntrar')))
            login_button.click()
            print("Botão de login clicado")

            # Aguarda o redirecionamento e verifica se o login foi bem-sucedido
            if self._detect_redirect_loop():
                print("Redirecionamento em excesso detectado após login. Recarregando a página...")
                self.driver.refresh()
                time.sleep(2)

            # Verifica se o login foi bem-sucedido procurando pelo dropdown de perfil
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'dropdown-toggle'))
                )
                print("Login efetuado com sucesso.")
                return True
                
            except TimeoutException:
                # Se não encontrar o dropdown, tenta verificar outros indicadores de sucesso
                try:
                    # Verifica se há algum iframe ou elemento que indique login bem-sucedido
                    WebDriverWait(self.driver, 5).until(
                        EC.any_of(
                            EC.presence_of_element_located((By.ID, 'ngFrame')),
                            EC.presence_of_element_located((By.CLASS_NAME, 'user-info')),
                            EC.presence_of_element_located((By.ID, 'menuPrincipal'))
                        )
                    )
                    print("Login efetuado com sucesso (verificação alternativa).")
                    return True
                    
                except TimeoutException:
                    print("Login falhou. Verifique as credenciais ou tente novamente.")
                    
                    # Verifica se há mensagem de erro na página
                    try:
                        error_message = self.driver.find_element(By.CSS_SELECTOR, '.alert-danger, .error-message, .login-error')
                        print(f"Erro de login detectado: {error_message.text}")
                    except:
                        print("Não foi possível detectar mensagem de erro específica.")
                    
                    return False

        except TimeoutException as e:
            print(f"Timeout durante o login: {e}")
            return False
        except Exception as e:
            print(f"Erro inesperado durante o login: {e}")
            # Se erro contém 429, tenta reiniciar sessão
            if "429" in str(e) or "rate limit" in str(e).lower():
                print("🔄 Erro de rate limit detectado. Reiniciando sessão...")
                self.clear_cache_and_restart_session()
                time.sleep(10)
            return False

    def skip_token(self):
        self.wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(text(),'Prosseguir sem o Token')]"))).click()

    def select_profile(self, profile):
        try:
            # Adiciona delay antes de selecionar perfil
            self.wait_with_random_delay(2, 4)
            
            dropdown = self.wait.until(EC.element_to_be_clickable(
                (By.CLASS_NAME, "dropdown-toggle")))
            dropdown.click()
            
            self.wait_with_random_delay(1, 2)
            
            opt = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, f"//a[contains(text(),'{profile}')]")))
            self.driver.execute_script("arguments[0].click();", opt)
            print(f"[OK] Perfil '{profile}' selecionado")

        except Exception as e:
            print(f"[select_profile] Erro ao selecionar perfil '{profile}'. Continuando mesmo assim")
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
        try:
            # Limpeza final antes de fechar
            if self.auto_clear_cache:
                print("🧹 Limpeza final antes de fechar...")
                self.clear_browser_cache()
            self.driver.quit()
        except Exception as e:
            print(f"Erro ao fechar navegador: {e}")

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
            # Limpa cache antes de acessar área de download
            if self.auto_clear_cache:
                self.clear_browser_cache()
                self.wait_with_random_delay(2, 4)

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
            # Se erro contém 429, tenta reiniciar sessão
            if "429" in str(e) or "rate limit" in str(e).lower():
                print("🔄 Erro de rate limit na área de download. Aguardando...")
                time.sleep(30)
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

                    # Adiciona delay antes do download
                    self.wait_with_random_delay(1, 3)
                    
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
            self.wait_with_random_delay(0.5, 1.5)  # Delay humano
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