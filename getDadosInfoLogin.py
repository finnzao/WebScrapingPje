import os
import time
import json
import logging
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
from utils.pje_automation import PjeConsultaAutomator

class PjeTjbaOC:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, 30)
        self.logger = logging.getLogger(self.__class__.__name__)

    def login(self, user, password):
        login_url = 'https://pje.tjba.jus.br/pje/login.seam'
        self.driver.get(login_url)
        self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ssoFrame')))
        self.wait.until(EC.presence_of_element_located((By.ID, 'username'))).send_keys(user)
        self.wait.until(EC.presence_of_element_located((By.ID, 'password'))).send_keys(password)
        self.wait.until(EC.element_to_be_clickable((By.ID, 'kc-login'))).click()
        self.driver.switch_to.default_content()

    def abrir_primeiro_processo(self):
        self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ngFrame")))
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "menuItem")))
        elementos = self.wait.until(EC.presence_of_all_elements_located((
            By.XPATH, "//div[contains(@class, 'menuItem')]//a[contains(@href, 'lista-processos-tarefa')]"
        )))
        for elemento in elementos:
            if elemento.is_displayed() and elemento.is_enabled():
                elemento.click()
                return
        raise Exception("Nenhum processo clicável encontrado")


    def abrir_autos_do_processo(self):
        try:
            #self.logger.info("Aguardando iframe 'ngFrame' e entrando...")
            #self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ngFrame")))

            xpath_botao = "/html/body/app-root/selector/div/div/div[2]/right-panel/div/processos-tarefa/div[1]/div[2]/div/div[1]/p-datalist/div/div/ul/li[1]/processo-datalist-card/div/div[1]/div[2]/pje-link-autos-digitais/button"
            self.logger.info("Aguardando presença do botão do primeiro processo via XPath...")
            botoes = self.wait.until(EC.presence_of_all_elements_located((By.XPATH, xpath_botao)))
            print(botoes)
            for botao in botoes:
                if botao.is_displayed() and botao.is_enabled():
                    self.wait.until(EC.element_to_be_clickable(botao))
                    self.logger.info("Botão encontrado. Aguardando 2 segundos antes de clicar...")
                    time.sleep(2)
                    botao.click()
                    self.logger.info("Botão clicado com sucesso.")
                    return

            raise Exception("Nenhum botão 'Abrir autos' visível e clicável encontrado")

        except Exception as e:
            self.driver.save_screenshot("erro_abrir_autos_xpath.png")
            self.logger.exception("Erro ao abrir autos do processo via XPath")
            raise

        finally:
            self.driver.switch_to.default_content()


    def capturar_url_com_oc(self):
        time.sleep(3)
        abas = self.driver.window_handles
        if len(abas) > 1:
            self.driver.switch_to.window(abas[-1])
        return self.driver.current_url

    def extrair_oc_ou_ca(self, url):
        time.sleep(2)
        query = urlparse(url).query
        params = parse_qs(query)
        oc = params.get('oc', [None])[0] or params.get('ca', [None])[0]
        return oc

    def obter_oc_e_salvar_config(self, config_path="config.json"):
        load_dotenv()
        user = os.getenv("USER")
        password = os.getenv("PASSWORD")
        automator = PjeConsultaAutomator(self.driver)

        self.login(user, password)
        self.abrir_primeiro_processo()
        self.abrir_autos_do_processo()
        url = self.capturar_url_com_oc()
        oc = self.extrair_oc_ou_ca(url)

        cookies = self.driver.get_cookies()
        user_agent = self.driver.execute_script("return navigator.userAgent;")

        automator.update_config({
            "LoginInfo": {
                "oc": oc,
                "cookies": cookies,
                "userAgent": user_agent
            }
        }, file=config_path)

        self.logger.info("Token OC e informações de sessão capturadas.")
        return oc
