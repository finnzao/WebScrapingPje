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
        wait_timeout: int = 50
    ) -> tuple[webdriver.Chrome, WebDriverWait]:
        chrome_options = webdriver.ChromeOptions()

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

        prefs = prefs or default_prefs
        chrome_options.add_experimental_option("prefs", prefs)

        driver = webdriver.Chrome(options=chrome_options)
        wait = WebDriverWait(driver, wait_timeout)

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
            dropdown = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "dropdown-toggle")))
            dropdown.click()
            opt = self.wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[contains(text(),'{profile}')]")))
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
