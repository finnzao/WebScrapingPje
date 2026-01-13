"""
Modelos de dados compartilhados do sistema PJE.
Todas as dataclasses usadas pelas automações.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Usuario:
    """Usuário do sistema PJE."""
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
    """Perfil de acesso do usuário."""
    index: int
    nome: str
    orgao: str = ""
    cargo: str = ""
    
    @property
    def nome_completo(self) -> str:
        partes = [self.nome]
        if self.orgao:
            partes.append(self.orgao)
        if self.cargo:
            partes.append(self.cargo)
        return " / ".join(partes)


@dataclass
class Tarefa:
    """Tarefa no painel do usuário."""
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
    """Processo dentro de uma tarefa."""
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
class Etiqueta:
    """Etiqueta para organização de processos."""
    id: int
    nome: str
    nome_completo: str = ""
    favorita: bool = False
    possui_filhos: bool = False
    
    @classmethod
    def from_dict(cls, data: dict) -> "Etiqueta":
        return cls(
            id=data.get("id", 0),
            nome=data.get("nomeTag", ""),
            nome_completo=data.get("nomeTagCompleto", ""),
            favorita=data.get("favorita", False),
            possui_filhos=data.get("possuiFilhos", False)
        )


@dataclass
class Processo:
    """Processo judicial completo."""
    id_processo: int
    numero_processo: str
    polo_ativo: str = ""
    polo_passivo: str = ""
    classe_judicial: str = ""
    orgao_julgador: str = ""
    id_orgao_julgador: int = 0
    assunto_principal: str = ""
    sigiloso: bool = False
    prioridade: bool = False
    data_chegada: int = 0
    ultimo_movimento: int = 0
    descricao_ultimo_movimento: str = ""
    tags: List[Dict] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Processo":
        return cls(
            id_processo=data.get("idProcesso", 0),
            numero_processo=data.get("numeroProcesso", ""),
            polo_ativo=data.get("poloAtivo", ""),
            polo_passivo=data.get("poloPassivo", ""),
            classe_judicial=data.get("classeJudicial", ""),
            orgao_julgador=data.get("orgaoJulgador", ""),
            id_orgao_julgador=data.get("idOrgaoJulgador", 0),
            assunto_principal=data.get("assuntoPrincipal", ""),
            sigiloso=data.get("sigiloso", False),
            prioridade=data.get("prioridade", False),
            data_chegada=data.get("dataChegada", 0),
            ultimo_movimento=data.get("ultimoMovimento", 0),
            descricao_ultimo_movimento=data.get("descricaoUltimoMovimento", ""),
            tags=data.get("tagsProcessoList", [])
        )


@dataclass
class DownloadDisponivel:
    """Download disponível na área de downloads."""
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
        return list(set([
            item.get("numeroProcesso", "") 
            for item in self.itens 
            if item.get("numeroProcesso")
        ]))
    
    def contem_processo(self, numero_processo: str) -> bool:
        return numero_processo in self.get_numeros_processos()


@dataclass
class DiagnosticoDownload:
    """Diagnóstico de tentativa de download."""
    numero_processo: str
    id_processo: int
    timestamp: float
    etapa: str
    sucesso: bool
    mensagem: str
    detalhes: Dict = field(default_factory=dict)
