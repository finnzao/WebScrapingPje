"""
Configuracoes e constantes do sistema PJE.
"""

# URLs do sistema
BASE_URL = "https://pje.tjba.jus.br"
SSO_URL = "https://sso.cloud.pje.jus.br"
API_BASE = f"{BASE_URL}/pje/seam/resource/rest/pje-legacy"

# Tipos de documento disponiveis para download
TIPO_DOCUMENTO = {
    "Selecione": "0",
    "Peticao Inicial": "12",
    "Peticao": "36",
    "Documento de Identificacao": "52",
    "Documento de Comprovacao": "53",
    "Certidao": "57",
    "Decisao": "64",
    "Procuracao": "161",
    "Despacho": "63",
    "Sentenca": "62",
    "Acordao": "74",
    "Outros documentos": "93",
}

# Configuracoes padrao
DEFAULT_TIMEOUT = 30
DEFAULT_DELAY_MIN = 1.0
DEFAULT_DELAY_MAX = 3.0
DEFAULT_SESSION_MAX_AGE_HOURS = 8

# Headers padrao para requisicoes
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
}
