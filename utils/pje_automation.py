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
import pickle
from pathlib import Path

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


class SessionManager:
    """
    Gerenciador de sessão para persistência de cookies e verificação de login.
    """
    
    def __init__(self, session_dir: str = ".session"):
        """
        Inicializa o gerenciador de sessão.
        
        Args:
            session_dir (str): Diretório para armazenar dados da sessão
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(exist_ok=True)
        self.cookies_file = self.session_dir / "cookies.pkl"
        self.session_info_file = self.session_dir / "session_info.json"
        
    def save_cookies(self, driver: webdriver.Chrome) -> bool:
        """
        Salva os cookies do navegador em arquivo.
        
        Args:
            driver: Instância do WebDriver
            
        Returns:
            bool: True se salvo com sucesso
        """
        try:
            cookies = driver.get_cookies()
            with open(self.cookies_file, 'wb') as f:
                pickle.dump(cookies, f)
            
            # Salva informações adicionais da sessão
            session_info = {
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": time.time(),
                "cookies_count": len(cookies),
                "current_url": driver.current_url
            }
            with open(self.session_info_file, 'w', encoding='utf-8') as f:
                json.dump(session_info, f, indent=4)
                
            print(f"✅ Sessão salva com {len(cookies)} cookies")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao salvar cookies: {e}")
            return False
    
    def load_cookies(self, driver: webdriver.Chrome, domain_url: str = "https://pje.tjba.jus.br") -> bool:
        """
        Carrega os cookies salvos no navegador.
        
        Args:
            driver: Instância do WebDriver
            domain_url: URL do domínio para carregar cookies
            
        Returns:
            bool: True se carregado com sucesso
        """
        if not self.cookies_file.exists():
            print("⚠️ Nenhum cookie salvo encontrado")
            return False
            
        try:
            # Navega para o domínio antes de adicionar cookies
            driver.get(domain_url)
            time.sleep(2)
            
            with open(self.cookies_file, 'rb') as f:
                cookies = pickle.load(f)
            
            for cookie in cookies:
                try:
                    # Remove atributos que podem causar problemas
                    if 'expiry' in cookie:
                        cookie['expiry'] = int(cookie['expiry'])
                    driver.add_cookie(cookie)
                except Exception as e:
                    # Ignora cookies que não podem ser adicionados
                    pass
            
            print(f"✅ {len(cookies)} cookies carregados")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao carregar cookies: {e}")
            return False
    
    def get_session_info(self) -> dict:
        """
        Retorna informações sobre a sessão salva.
        
        Returns:
            dict: Informações da sessão ou dicionário vazio
        """
        if not self.session_info_file.exists():
            return {}
            
        try:
            with open(self.session_info_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Erro ao ler informações da sessão: {e}")
            return {}
    
    def is_session_valid(self, max_age_hours: int = 8) -> bool:
        """
        Verifica se a sessão salva ainda é válida baseado no tempo.
        
        Args:
            max_age_hours (int): Idade máxima da sessão em horas
            
        Returns:
            bool: True se a sessão ainda pode ser válida
        """
        session_info = self.get_session_info()
        
        if not session_info:
            return False
            
        saved_timestamp = session_info.get("timestamp", 0)
        age_seconds = time.time() - saved_timestamp
        age_hours = age_seconds / 3600
        
        if age_hours > max_age_hours:
            print(f"⚠️ Sessão expirada (idade: {age_hours:.1f}h, máximo: {max_age_hours}h)")
            return False
            
        print(f"✅ Sessão dentro do prazo de validade ({age_hours:.1f}h de {max_age_hours}h)")
        return True
    
    def clear_session(self) -> bool:
        """
        Remove todos os dados de sessão salvos.
        
        Returns:
            bool: True se limpo com sucesso
        """
        try:
            if self.cookies_file.exists():
                self.cookies_file.unlink()
            if self.session_info_file.exists():
                self.session_info_file.unlink()
            print("🧹 Dados de sessão removidos")
            return True
        except Exception as e:
            print(f"❌ Erro ao limpar sessão: {e}")
            return False


class PjeConsultaAutomator:
    load_dotenv()
    user, password = os.getenv("USER"), os.getenv("PASSWORD")

    def __init__(
        self,
        driver: webdriver.Chrome = None,
        download_directory: str = None,
        custom_prefs: dict = None,
        wait_timeout: int = 50,
        clear_cache_on_start: bool = False,  # Alterado para False - preservar sessão
        auto_clear_cache: bool = False,      # Alterado para False - preservar sessão
        session_dir: str = ".session",       # Novo: diretório da sessão
        profile_dir: str = ".chrome_profile", # Novo: diretório do perfil Chrome
        session_max_age_hours: int = 8       # Novo: tempo máximo de sessão
    ):
        """
        Inicializa o PjeConsultaAutomator com gerenciamento de sessão.
        
        Args:
            clear_cache_on_start (bool): Limpa cache durante inicialização (padrão: False para manter sessão)
            auto_clear_cache (bool): Ativa limpeza automática de cache (padrão: False para manter sessão)
            session_dir (str): Diretório para armazenar dados da sessão
            profile_dir (str): Diretório do perfil do Chrome (persistência local)
            session_max_age_hours (int): Tempo máximo de validade da sessão em horas
        """
        # Inicializa o gerenciador de sessão
        self.session_manager = SessionManager(session_dir)
        self.profile_dir = Path(profile_dir).absolute()
        self.session_max_age_hours = session_max_age_hours
        
        # Configuração de limpeza automática
        self.auto_clear_cache = auto_clear_cache
        
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
        
        # Executa limpeza manual adicional se solicitado
        if auto_clear_cache:
            print("🚀 Executando limpeza automática de cache...")
            self.clear_browser_cache()
            time.sleep(2)

    def initialize_driver(
        self,
        download_directory: str = None,
        prefs: dict = None,
        wait_timeout: int = 50,
        headless: bool = False,
        clear_cache: bool = False
    ) -> tuple[webdriver.Chrome, WebDriverWait]:
        """
        Inicializa o driver do Chrome com configurações personalizadas.
        SEM modo incógnito para permitir cookies de terceiros e persistência de sessão.
        
        Args:
            clear_cache (bool): Se True, limpa cache e dados do navegador
        """
        chrome_options = webdriver.ChromeOptions()
        
        # Cria diretório do perfil se não existir
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        # ============================================
        # CONFIGURAÇÕES PARA PERSISTÊNCIA DE SESSÃO
        # ============================================
        
        # Usa perfil persistente (NÃO incógnito)
        chrome_options.add_argument(f"--user-data-dir={self.profile_dir}")
        chrome_options.add_argument("--profile-directory=Default")
        
        # Permite cookies de terceiros
        chrome_options.add_argument("--disable-features=SameSiteByDefaultCookies")
        chrome_options.add_argument("--disable-features=CookiesWithoutSameSiteMustBeSecure")
        
        # Anti-detecção para evitar rate limiting
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Configurações gerais
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        
        print("🔓 Modo normal (não-incógnito) - Cookies de terceiros permitidos")
        print(f"📁 Perfil Chrome persistente em: {self.profile_dir}")
        
        # Configurações opcionais de limpeza de cache
        if clear_cache:
            chrome_options.add_argument("--aggressive-cache-discard")
            chrome_options.add_argument("--disable-cache")
            chrome_options.add_argument("--disable-application-cache")
            chrome_options.add_argument("--disable-offline-load-stale-cache")
            chrome_options.add_argument("--disk-cache-size=0")
            chrome_options.add_argument("--media-cache-size=0")
            print("🧹 Cache será limpo (mas cookies serão preservados)")
    
        # Configurar modo headless se solicitado
        if headless:
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
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
            "safebrowsing.enabled": True,
            # Configurações para permitir cookies de terceiros
            "profile.default_content_setting_values.cookies": 1,
            "profile.cookie_controls_mode": 0,
            "profile.block_third_party_cookies": False,
            # Não limpar dados ao sair
            "profile.exit_type": "normal",
            "profile.exited_cleanly": True,
            # Permitir notificações e popups controlados
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
        }
    
        # Em modo headless, adicionar configurações extras
        if headless:
            default_prefs.update({
                "download.extensions_to_open": "applications/pdf",
                "profile.content_settings.exceptions.automatic_downloads.*.setting": 1
            })
    
        prefs = prefs or default_prefs
        chrome_options.add_experimental_option("prefs", prefs)
    
        driver = webdriver.Chrome(options=chrome_options)
        wait = WebDriverWait(driver, wait_timeout)
    
        # Remove indicadores de automação via JavaScript
        try:
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
            print("✅ Proteções anti-detecção aplicadas")
        except Exception as e:
            print(f"⚠️ Aviso: Não foi possível aplicar proteções anti-detecção: {e}")
    
        # Em modo headless, habilitar download via CDP
        if headless:
            driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": download_directory
            })
    
        return driver, wait

    def is_session_active(self) -> bool:
        """
        Verifica se há uma sessão ativa no navegador (usuário logado).
        
        Returns:
            bool: True se o usuário está logado
        """
        try:
            print("🔍 Verificando se há sessão ativa...")
            
            # Navega para uma página que requer autenticação
            self.driver.get('https://pje.tjba.jus.br/pje/Painel/painel_usuario/advogado.seam')
            time.sleep(3)
            
            current_url = self.driver.current_url.lower()
            
            # Se foi redirecionado para login, não está autenticado
            if 'login' in current_url or 'auth' in current_url:
                print("❌ Sessão não está ativa (redirecionado para login)")
                return False
            
            # Verifica elementos que indicam usuário logado
            indicators = [
                (By.CLASS_NAME, 'dropdown-toggle'),
                (By.ID, 'ngFrame'),
                (By.CLASS_NAME, 'user-info'),
                (By.ID, 'menuPrincipal'),
                (By.CLASS_NAME, 'navbar-user')
            ]
            
            for locator in indicators:
                try:
                    element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located(locator)
                    )
                    if element:
                        print(f"✅ Sessão ativa detectada (encontrado: {locator[1]})")
                        return True
                except:
                    continue
            
            print("❌ Sessão não está ativa (nenhum indicador encontrado)")
            return False
            
        except Exception as e:
            print(f"⚠️ Erro ao verificar sessão: {e}")
            return False

    def restore_session(self) -> bool:
        """
        Tenta restaurar uma sessão salva anteriormente.
        
        Returns:
            bool: True se a sessão foi restaurada com sucesso
        """
        print("🔄 Tentando restaurar sessão salva...")
        
        # Verifica se a sessão salva ainda é válida (pelo tempo)
        if not self.session_manager.is_session_valid(self.session_max_age_hours):
            print("⚠️ Sessão salva expirada ou inexistente")
            return False
        
        # Carrega os cookies
        if not self.session_manager.load_cookies(self.driver):
            print("⚠️ Não foi possível carregar cookies")
            return False
        
        # Atualiza a página e verifica se está logado
        self.driver.refresh()
        time.sleep(3)
        
        if self.is_session_active():
            print("✅ Sessão restaurada com sucesso!")
            return True
        
        print("❌ Sessão não pôde ser restaurada (cookies inválidos ou expirados)")
        return False

    def save_current_session(self) -> bool:
        """
        Salva a sessão atual para uso posterior.
        
        Returns:
            bool: True se salvo com sucesso
        """
        return self.session_manager.save_cookies(self.driver)

    def clear_browser_cache(self):
        """
        Limpa cache do navegador (mas preserva cookies para manter sessão).
        """
        try:
            print("🧹 Iniciando limpeza de cache (preservando cookies)...")
            
            # Limpa apenas o cache, não os cookies
            try:
                self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
                print("✅ Cache do navegador limpo")
            except Exception as e:
                print(f"⚠️ Falha na limpeza de cache: {e}")
            
            # Limpa localStorage e sessionStorage (mas não cookies)
            try:
                self.driver.execute_script("window.localStorage.clear();")
                self.driver.execute_script("window.sessionStorage.clear();")
                print("✅ Storage local limpo")
            except Exception as e:
                print(f"⚠️ Falha na limpeza de storage: {e}")
                
            print("🎯 Limpeza de cache concluída (cookies preservados)")
            
        except Exception as e:
            print(f"❌ Erro durante limpeza de cache: {e}")

    def clear_all_data(self):
        """
        Limpa todos os dados incluindo cookies (logout completo).
        Use apenas quando quiser forçar um novo login.
        """
        try:
            print("🧹 Limpando TODOS os dados (incluindo sessão)...")
            
            # Limpa cache e cookies via DevTools
            try:
                self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
                self.driver.execute_cdp_cmd("Network.clearBrowserCookies", {})
                print("✅ Cache e cookies limpos via DevTools")
            except Exception as e:
                print(f"⚠️ Falha na limpeza via DevTools: {e}")
            
            # Limpa storage
            try:
                self.driver.execute_script("window.localStorage.clear();")
                self.driver.execute_script("window.sessionStorage.clear();")
            except:
                pass
            
            # Limpa arquivos de sessão salvos
            self.session_manager.clear_session()
            
            print("🎯 Todos os dados de sessão foram removidos")
            
        except Exception as e:
            print(f"❌ Erro durante limpeza completa: {e}")

    def clear_cache_and_restart_session(self):
        """
        Limpa cache e reinicia a sessão do navegador completamente.
        Use para casos onde a limpeza simples não resolve.
        """
        try:
            print("🔄 Reiniciando sessão completa do navegador...")
            
            # Fecha o navegador atual
            if hasattr(self, 'driver'):
                self.driver.quit()
                time.sleep(2)
            
            # Reinicializa (preservando o perfil)
            self.driver, self.wait = self.initialize_driver(clear_cache=True)
            
            print("✅ Sessão reiniciada")
                
        except Exception as e:
            print(f"❌ Erro ao reiniciar sessão: {e}")
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
            self.driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            
            self.driver.execute_script("""
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

    def login(self, user=None, password=None, force_new_login: bool = False):
        """
        Realiza login no sistema PJE com verificação de sessão existente.
        
        Args:
            user (str): CPF/CNPJ do usuário (usa variável de ambiente se não fornecido)
            password (str): Senha do usuário (usa variável de ambiente se não fornecida)
            force_new_login (bool): Se True, ignora sessão existente e faz novo login
            
        Returns:
            bool: True se login foi bem-sucedido
        """
        # Usa credenciais do .env se não fornecidas
        user = user or self.user
        password = password or self.password
        
        if not user or not password:
            print("❌ Credenciais não fornecidas e não encontradas no .env")
            return False
        
        # ============================================
        # VERIFICAÇÃO DE SESSÃO EXISTENTE
        # ============================================
        if not force_new_login:
            print("\n" + "="*50)
            print("🔐 VERIFICANDO SESSÃO EXISTENTE")
            print("="*50)
            
            # Primeiro, verifica se já está logado
            if self.is_session_active():
                print("✅ Usuário já está logado! Reutilizando sessão.")
                return True
            
            # Tenta restaurar sessão salva
            if self.restore_session():
                print("✅ Sessão restaurada com sucesso!")
                return True
            
            print("⚠️ Nenhuma sessão válida encontrada. Realizando novo login...")
        else:
            print("🔄 Forçando novo login (ignorando sessão existente)...")
            self.clear_all_data()
        
        # ============================================
        # PROCESSO DE LOGIN
        # ============================================
        print("\n" + "="*50)
        print("🔑 REALIZANDO LOGIN")
        print("="*50)
        
        try:
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
            self.wait_with_random_delay(0.5, 1.5)
            username_field.send_keys(user)
            print(f"CPF/CNPJ preenchido: {user}")

            # Aguarda e preenche o campo de senha
            password_field = self.wait.until(EC.presence_of_element_located((By.ID, 'password')))
            password_field.clear()
            self.wait_with_random_delay(0.5, 1.5)
            password_field.send_keys(password)
            print("Senha preenchida")

            # Aguarda antes de clicar no botão
            self.wait_with_random_delay(1, 2)
            
            # Clica no botão de entrar
            login_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'kc-login')))
            login_button.click()
            print("Botão de login clicado")

            # Aguarda o redirecionamento
            if self._detect_redirect_loop():
                print("Redirecionamento em excesso detectado após login. Recarregando...")
                self.driver.refresh()
                time.sleep(2)

            # Verifica se o login foi bem-sucedido
            login_success = self._verify_login_success()
            
            if login_success:
                # ============================================
                # SALVA SESSÃO APÓS LOGIN BEM-SUCEDIDO
                # ============================================
                print("\n💾 Salvando sessão para uso futuro...")
                self.save_current_session()
                print("✅ Login efetuado e sessão salva com sucesso!")
                return True
            else:
                print("❌ Login falhou. Verifique as credenciais.")
                return False

        except TimeoutException as e:
            print(f"Timeout durante o login: {e}")
            return False
        except Exception as e:
            print(f"Erro inesperado durante o login: {e}")
            if "429" in str(e) or "rate limit" in str(e).lower():
                print("🔄 Erro de rate limit detectado. Aguardando...")
                time.sleep(30)
                self.clear_cache_and_restart_session()
            return False

    def _verify_login_success(self) -> bool:
        """
        Verifica se o login foi bem-sucedido.
        
        Returns:
            bool: True se logado com sucesso
        """
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'dropdown-toggle'))
            )
            return True
            
        except TimeoutException:
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.ID, 'ngFrame')),
                        EC.presence_of_element_located((By.CLASS_NAME, 'user-info')),
                        EC.presence_of_element_located((By.ID, 'menuPrincipal'))
                    )
                )
                return True
                
            except TimeoutException:
                try:
                    error_message = self.driver.find_element(
                        By.CSS_SELECTOR, '.alert-danger, .error-message, .login-error'
                    )
                    print(f"Erro de login detectado: {error_message.text}")
                except:
                    print("Não foi possível detectar mensagem de erro específica.")
                
                return False

    def ensure_logged_in(self, user=None, password=None) -> bool:
        """
        Garante que o usuário está logado, fazendo login se necessário.
        Use este método antes de qualquer operação que requer autenticação.
        
        Args:
            user (str): CPF/CNPJ do usuário
            password (str): Senha do usuário
            
        Returns:
            bool: True se está logado
        """
        if self.is_session_active():
            print("✅ Sessão ativa confirmada")
            return True
        
        print("⚠️ Sessão expirada. Realizando novo login...")
        return self.login(user=user, password=password)

    def skip_token(self):
        self.wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(text(),'Prosseguir sem o Token')]"))).click()

    def select_profile(self, profile):
        try:
            # Verifica se está logado antes de selecionar perfil
            if not self.ensure_logged_in():
                print("❌ Não foi possível garantir login para seleção de perfil")
                return
            
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
        """
        Fecha o navegador salvando a sessão antes.
        """
        try:
            # Salva a sessão antes de fechar (se estiver logado)
            if self.is_session_active():
                print("💾 Salvando sessão antes de fechar...")
                self.save_current_session()
            
            self.driver.quit()
            print("✅ Navegador fechado")
        except Exception as e:
            print(f"Erro ao fechar navegador: {e}")

    def logout_and_close(self):
        """
        Faz logout, limpa a sessão e fecha o navegador.
        """
        try:
            print("🚪 Realizando logout e limpando sessão...")
            self.clear_all_data()
            self.driver.quit()
            print("✅ Logout realizado e navegador fechado")
        except Exception as e:
            print(f"Erro ao fazer logout: {e}")

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
        # Verifica se está logado antes de acessar área de download
        if not self.ensure_logged_in():
            print("❌ Não foi possível garantir login para acessar área de download")
            return None

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

        target_processes = set(process_numbers)
        downloaded_numbers = set()

        for row in rows:
            try:
                process_number_td = row.find_element(By.XPATH, "./td[1]")
                process_number = process_number_td.text.strip()

                if process_number in target_processes and process_number not in downloaded_numbers:
                    if tag_name:
                        self._log_info(f"Processo {process_number} da etiqueta '{tag_name}' encontrado. Baixando...")
                    else:
                        self._log_info(f"Processo {process_number} encontrado. Baixando...")

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
            self.wait_with_random_delay(0.5, 1.5)
            download_button.click()
            time.sleep(5)
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
        os.makedirs(".logs", exist_ok=True)

        tag_suffix = f"_{tag_name}" if tag_name else ""
        filename = f".logs/processos_download{tag_suffix}_completo.json"

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
        """Método auxiliar para logging."""
        print(message)

    def _log_error(self, message):
        """Método auxiliar para logging de erros."""
        print(f"[ERRO] {message}")

    def _save_exception_screenshot(self, filename):
        """Salva screenshot em caso de exceção."""
        directory = ".logs/exception"
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, filename)
        self.driver.save_screenshot(filepath)
        print(f"Screenshot de exceção salvo em: {filepath}")