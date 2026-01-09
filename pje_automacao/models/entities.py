"""
Modelos de dados do sistema PJE.
Utiliza dataclasses para representar entidades do sistema.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Usuario:
    """Representa um usuario do sistema PJE."""
    id_usuario: int
    nome: str
    login: str
    id_orgao_julgador: int
    id_papel: int
    id_localizacao_fisica: int
    id_usuario_localizacao: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "Usuario":
        return cls(
            id_usuario=data.get("idUsuario", 0),
            nome=data.get("nomeUsuario", ""),
            login=data.get("login", ""),
            id_orgao_julgador=data.get("idOrgaoJulgador", 0),
            id_papel=data.get("idPapel", 0),
            id_localizacao_fisica=data.get("idLocalizacaoFisica", 0),
            id_usuario_localizacao=data.get("idUsuarioLocalizacaoMagistradoServidor", 0)
        )


@dataclass
class Perfil:
    """Representa um perfil/papel do usuario."""
    index: int
    nome: str
    orgao: str = ""
    cargo: str = ""

    @property
    def nome_completo(self) -> str:
        partes = [p for p in [self.nome, self.orgao, self.cargo] if p]
        return " / ".join(partes)


@dataclass
class Tarefa:
    """Representa uma tarefa no painel do PJE."""
    id: int
    nome: str
    quantidade_pendente: int = 0
    favorita: bool = False

    @classmethod
    def from_dict(cls, data: dict, favorita: bool = False) -> "Tarefa":
        return cls(
            id=data.get("id", 0),
            nome=data.get("nome", ""),
            quantidade_pendente=data.get("quantidadePendente", 0),
            favorita=favorita
        )


@dataclass
class ProcessoTarefa:
    """Representa um processo dentro de uma tarefa."""
    id_processo: int
    numero_processo: str
    id_task_instance: int
    polo_ativo: str = ""
    polo_passivo: str = ""
    classe_judicial: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "ProcessoTarefa":
        return cls(
            id_processo=data.get("idProcesso", 0),
            numero_processo=data.get("numeroProcesso", ""),
            id_task_instance=data.get("idTaskInstance", 0),
            polo_ativo=data.get("poloAtivo", ""),
            polo_passivo=data.get("poloPassivo", ""),
            classe_judicial=data.get("classeJudicial", "")
        )


@dataclass
class DownloadDisponivel:
    """Representa um download disponivel na area de downloads."""
    id_usuario: int
    nome_arquivo: str
    hash_download: str
    data_expiracao: int
    situacao: str
    sistema_origem: str
    itens: List[Dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "DownloadDisponivel":
        return cls(
            id_usuario=data.get("idUsuario", 0),
            nome_arquivo=data.get("nomeArquivo", ""),
            hash_download=data.get("hashDownload", ""),
            data_expiracao=data.get("dataExpiracao", 0),
            situacao=data.get("situacaoDownload", ""),
            sistema_origem=data.get("sistemaOrigem", ""),
            itens=data.get("itens", [])
        )

    def get_numeros_processos(self) -> List[str]:
        return list(set(
            item.get("numeroProcesso", "") 
            for item in self.itens 
            if item.get("numeroProcesso")
        ))

    def contem_processo(self, numero_processo: str) -> bool:
        return numero_processo in self.get_numeros_processos()


@dataclass
class DiagnosticoDownload:
    """Armazena informacoes de diagnostico sobre tentativa de download."""
    numero_processo: str
    id_processo: int
    timestamp: float
    etapa: str
    sucesso: bool
    mensagem: str
    detalhes: Dict = field(default_factory=dict)
