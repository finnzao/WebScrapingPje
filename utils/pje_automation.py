from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
from typing import TypedDict,NotRequired,Any, Dict

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

    def __init__(self, driver: webdriver.Chrome = None):
        self.driver = driver or webdriver.Chrome()  
        self.wait = WebDriverWait(self.driver, 20)

    def login(self, user=user, password=password):
        login_url = 'https://pje.tjba.jus.br/pje/login.seam'
        self.driver.get(login_url)
        self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ssoFrame')))
        self.wait.until(EC.presence_of_element_located((By.ID, 'username'))).send_keys(user)
        self.wait.until(EC.presence_of_element_located((By.ID, 'password'))).send_keys(password)
        self.wait.until(EC.presence_of_element_located((By.ID, 'kc-login'))).click()
        self.driver.switch_to.default_content()

    def skip_token(self):
        self.wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(text(),'Prosseguir sem o Token')]"))).click()

    def select_profile(self, profile):
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'dropdown-toggle'))).click()
        btn = self.wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//a[contains(text(), '{profile}')]")))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
        self.driver.execute_script("arguments[0].click();", btn)

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
