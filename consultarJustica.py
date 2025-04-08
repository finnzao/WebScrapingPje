import pandas as pd
import time
import json
from bs4 import BeautifulSoup
from urllib.parse import urlencode
import requests
from selenium import webdriver
from getDadosInfoLogin import PjeTjbaOC


URL_BASE_DO_PJE = "https://pje.tjba.jus.br/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam"
INTERVALO_REQUISICOES = 2


def atualizar_oc_e_sessao(config_path="config.json") -> str:
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    driver = webdriver.Chrome(options=options)

    try:
        pje = PjeTjbaOC(driver)
        oc = pje.obter_oc_e_salvar_config(config_path=config_path)
        print("OC atualizado com sucesso:", oc)
        return oc
    finally:
        driver.quit()


def carregar_config() -> dict:
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def carregar_sessao_requests(config: dict) -> requests.Session:
    session = requests.Session()

    # Adiciona cookies
    for cookie in config.get("LoginInfo", {}).get("cookies", []):
        session.cookies.set(cookie.get("name"), cookie.get("value"))

    # Adiciona headers
    session.headers.update({
        "User-Agent": config.get("LoginInfo", {}).get("userAgent", "Mozilla/5.0"),
        "Accept": "text/html"
    })

    return session


def carregar_planilha_processos(caminho_csv: str) -> pd.DataFrame:
    df = pd.read_csv(
        caminho_csv,
        sep=';',
        dtype=str,
        engine='python',
        on_bad_lines='skip'
    )
    return df[["numeroProcesso", "idProcesso"]]


def construir_url(oc: str, id_processo: str) -> str:
    params = {"oc": oc, "idProcesso": id_processo}
    return f"{URL_BASE_DO_PJE}?{urlencode(params)}"


def verificar_gratuidade_na_pagina(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Verifica se foi redirecionado para uma tela de login ou erro de sessão
    titulo_pagina = soup.title.string.strip().lower() if soup.title else ""
    if "login" in titulo_pagina or "autenticação" in titulo_pagina:
        return "Erro: não autenticado (redirecionado para tela de login)"

    # Mensagens genéricas de erro por falta de sessão ou token inválido
    if "sessão inválida" in html.lower() or "token inválido" in html.lower():
        return "Erro: sessão inválida ou token expirado"

    # Verifica se o bloco esperado de detalhes está presente
    detalhes = soup.select_one('#maisDetalhes')
    if not detalhes:
        return "Erro: bloco '#maisDetalhes' não encontrado (possível falha de carregamento ou acesso negado)"

    dt_tags = detalhes.select('dl dt')
    dd_tags = detalhes.select('dl dd')
    if not dt_tags or not dd_tags:
        return "Erro: elementos <dt>/<dd> ausentes no bloco '#maisDetalhes'"

    # Busca o campo específico de Justiça gratuita
    for dt, dd in zip(dt_tags, dd_tags):
        titulo = dt.text.strip().upper()
        valor = dd.text.strip().upper()
        if "JUSTIÇA GRATUITA" in titulo:
            if "SIM" in valor:
                return "Sim"
            elif "NÃO" in valor:
                return "Não"
            else:
                return f"Valor não reconhecido: {valor}"

    return "Erro: campo 'Justiça gratuita?' não encontrado no HTML"



def consultar_gratuidade(session: requests.Session, url: str) -> str:
    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            return "Erro"
        return verificar_gratuidade_na_pagina(response.text)
    except Exception as e:
        print(f"Erro ao acessar {url}: {e}")
        return "Erro"


def salvar_resultado(df: pd.DataFrame, caminho_csv: str):
    df.to_csv(caminho_csv, index=False, encoding="utf-8")


def executar_consulta_em_lote():
    oc_token = atualizar_oc_e_sessao()
    config = carregar_config()
    session = carregar_sessao_requests(config)
    df = carregar_planilha_processos("processos.csv")

    print("Iniciando consulta de gratuidade de justiça...")
    resultados = []

    for _, linha in df.iterrows():
        numero = linha["numeroProcesso"]
        id_proc = linha["idProcesso"]
        url = construir_url(oc_token, id_proc)
        print(f"Consultando processo {numero}...")
        resultado = consultar_gratuidade(session, url)
        resultados.append({
            "numeroProcesso": numero,
            "idProcesso": id_proc,
            "GratuidadeJustica": resultado
        })
        time.sleep(INTERVALO_REQUISICOES)

    df_resultado = pd.DataFrame(resultados)
    salvar_resultado(df_resultado, "resultadoGratuidade.csv")
    print("Consulta concluída. Resultado salvo em 'resultadoGratuidade.csv'.")


if __name__ == "__main__":
    executar_consulta_em_lote()
