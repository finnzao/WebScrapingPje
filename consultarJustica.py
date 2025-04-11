import os
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urlencode

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from dotenv import load_dotenv

URL_BASE_DO_PJE = "https://pje.tjba.jus.br/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam"
REQUEST_INTERVAL = 2

class PjeGratuidadeConsulta:
    def __init__(self):
        load_dotenv()
        self.user = os.getenv("USER")
        self.password = os.getenv("PASSWORD")
        self.driver = self._initialize_driver()
        self.wait = WebDriverWait(self.driver, 30)
        self.cookies = []
        self.user_agent = ""

    def _initialize_driver(self) -> webdriver.Chrome:
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        return webdriver.Chrome(options=options)

    def login(self) -> None:
        self.driver.get("https://pje.tjba.jus.br/pje/login.seam")
        try:
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'ssoFrame')))
            self.wait.until(EC.presence_of_element_located((By.ID, 'username'))).send_keys(self.user)
            self.wait.until(EC.presence_of_element_located((By.ID, 'password'))).send_keys(self.password)
            self.wait.until(EC.element_to_be_clickable((By.ID, 'kc-login'))).click()
            self.driver.switch_to.default_content()
            time.sleep(5)
        except Exception as e:
            raise RuntimeError(f"Login failed: {e}")

    def authenticate_and_capture_session(self) -> None:
        self.login()
        self.cookies = self.driver.get_cookies()
        self.user_agent = self.driver.execute_script("return navigator.userAgent;")

    def build_requests_session(self) -> requests.Session:
        session = requests.Session()
        for cookie in self.cookies:
            session.cookies.set(cookie.get("name"), cookie.get("value"), domain=cookie.get("domain"))
        session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html",
        })
        return session

    def build_url_with_task(self, process_id: str, task_instance_id: str) -> str:
        params = {"idProcesso": process_id, "idTaskInstance": task_instance_id}
        query_string = urlencode(params)
        final_url = f"{URL_BASE_DO_PJE}?{query_string}"
        print(f"ProcessID: {process_id} - TaskInstance: {task_instance_id}")
        print(f"Constructed URL: {final_url}\n")
        return final_url

    def verificar_gratuidade_na_pagina(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        title_text = soup.title.string.strip().lower() if soup.title else ""
        if "login" in title_text or "autenticação" in title_text:
            return "Error: not authenticated (redirected to login)"
        if "sessão inválida" in html.lower() or "token inválido" in html.lower():
            return "Error: invalid session or expired token"

        details = soup.select_one('#maisDetalhes')
        if not details:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            os.makedirs("./errosHtml", exist_ok=True)
            error_file = f"./errosHtml/error_details_{timestamp}.html"
            try:
                with open(error_file, "w", encoding="utf-8") as f:
                    f.write(soup.prettify())
            except Exception:
                pass
            return "Error: '#maisDetalhes' block not found"

        for dt, dd in zip(details.select('dl dt'), details.select('dl dd')):
            if "JUSTIÇA GRATUITA" in dt.text.strip().upper():
                value = dd.text.strip().upper()
                if "SIM" in value:
                    return "Sim"
                elif "NÃO" in value:
                    return "Não"
                return f"Unrecognized value: {value}"

        return "Error: 'Justiça gratuita?' field not found"

    def consultar_gratuidade(self, session: requests.Session, url: str) -> str:
        for tentativa in range(3):
            try:
                response = session.get(url, timeout=15)
                resultado = self.verificar_gratuidade_na_pagina(response.text)

                if "Error: '#maisDetalhes'" in resultado:
                    print(f"Tentativa {tentativa+1} via requests falhou. Retentando...")
                    time.sleep(2)
                    continue

                return resultado

            except Exception as e:
                print(f"Erro (requests) tentativa {tentativa+1}: {e}")
                time.sleep(2)

        print("Tentando fallback via Selenium...")
        try:
            self.driver.get(url)
            time.sleep(3)
            html = self.driver.page_source
            return self.verificar_gratuidade_na_pagina(html)
        except Exception as e:
            return f"Erro final via Selenium: {e}"

    def run_batch_check(self, csv_path: str = "processos.csv", output_csv: str = "resultadoGratuidade.csv"):
        print("Logging in and capturing cookies...")
        self.authenticate_and_capture_session()
        session = self.build_requests_session()
        try:
            df = pd.read_csv(csv_path, sep=";", dtype=str, on_bad_lines="skip", engine="python")
        except Exception as e:
            print(f"Error reading {csv_path}: {e}")
            return

        required_cols = ["numeroProcesso", "idProcesso", "idTaskInstance"]
        for c in required_cols:
            if c not in df.columns:
                print(f"Error: column '{c}' is missing in the CSV.")
                return
        df = df[required_cols]
        results = []
        print("Starting 'Justiça gratuita' check...")
        for _, row in df.iterrows():
            process_number = row["numeroProcesso"]
            process_id = row["idProcesso"]
            task_id = row["idTaskInstance"]
            if not task_id:
                results.append({
                    "numeroProcesso": process_number,
                    "idProcesso": process_id,
                    "GratuidadeJustica": "Error: idTaskInstance not provided"
                })
                continue
            final_url = self.build_url_with_task(process_id, task_id)
            print(f"Checking process {process_number} with task={task_id}...")
            result = self.consultar_gratuidade(session, final_url)
            results.append({
                "numeroProcesso": process_number,
                "idProcesso": process_id,
                "idTaskInstance": task_id,
                "GratuidadeJustica": result
            })
            time.sleep(REQUEST_INTERVAL)
        pd.DataFrame(results).to_csv(output_csv, index=False, encoding="utf-8")
        print(f"Finished. Results saved to '{output_csv}'.")

    def close(self) -> None:
        if self.driver:
            self.driver.quit()


if __name__ == "__main__":
    pje = PjeGratuidadeConsulta()
    try:
        pje.run_batch_check()
    finally:
        input("Finished - press Enter to close...")
        pje.close()
