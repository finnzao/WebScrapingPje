"""
Exceções tipadas do pipeline PJE.

erro_tipo é a categoria acionável que vai para a fila de trabalho
(permite reprocessar só uma categoria depois).
"""


class PJEError(Exception):
    """Base. erro_tipo identifica a categoria para a fila."""
    erro_tipo = "erro_generico"

    def __init__(self, mensagem: str = "", erro_tipo: str = None):
        super().__init__(mensagem or self.__class__.erro_tipo)
        if erro_tipo:
            self.erro_tipo = erro_tipo


class SessaoExpirada(PJEError):
    """Resposta redirecionou para o SSO/login no meio da execução."""
    erro_tipo = "sessao_expirada"


class ErroCaptura(PJEError):
    """Falha na captura de um processo. Não derruba o lote."""
    erro_tipo = "erro_captura"


class ProcessoNaoEncontrado(ErroCaptura):
    erro_tipo = "nao_encontrado"


class AcessoNegado(ErroCaptura):
    """Sigilo ou perfil sem permissão."""
    erro_tipo = "sigilo"


class PdfInvalido(ErroCaptura):
    """Arquivo baixado não é um PDF/ZIP válido."""
    erro_tipo = "pdf_invalido"


class RespostaDesconhecida(ErroCaptura):
    """Resposta do PJE não casou com nenhum padrão conhecido.

    NUNCA tratar como sucesso: o payload é salvo em disco para análise
    e o processo fica reprocessável na categoria 'resposta_desconhecida'.
    """
    erro_tipo = "resposta_desconhecida"
