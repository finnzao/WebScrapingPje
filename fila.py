"""
Fila de trabalho por processo, em SQLite.

Estados: pendente -> em_captura -> capturado -> extraido
                                -> sem_juntada (consulta OK, nada no filtro)
                                -> erro (erro_tipo categoriza; reprocessável)

Por que SQLite e não a planilha: transação atômica por linha com escritores
concorrentes (WAL), retomada nativa após queda, e reprocessamento seletivo
por categoria de erro via query. A planilha entra como carga inicial e sai
como relatório (ver capturarJuntadasPorPeriodo.py --exportar).

Concorrência: rode N instâncias do worker — o claim em pegar_proximo é
atômico, dois workers nunca recebem o mesmo processo.

O banco fica FORA do OneDrive por padrão (%LOCALAPPDATA%): SQLite em modo
WAL dentro de pasta sincronizada sofre lock/corrupção pelo cliente de sync.
"""

import os
import sqlite3
from pathlib import Path

DATA_DIR = Path(os.getenv("PJE_DATA_DIR", Path(os.getenv("LOCALAPPDATA", Path.home())) / "pje_pipeline"))
DB_PATH = DATA_DIR / "fila_processos.db"
MAX_TENTATIVAS = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS fila (
  npu           TEXT PRIMARY KEY,
  origem        TEXT NOT NULL DEFAULT 'painel' CHECK (origem IN ('datajud', 'painel')),
  id_processo   INTEGER,
  status        TEXT NOT NULL DEFAULT 'pendente'
                CHECK (status IN ('pendente','em_captura','capturado','extraido','sem_juntada','erro')),
  via           TEXT,
  tentativas    INTEGER NOT NULL DEFAULT 0,
  erro_tipo     TEXT,
  erro_msg      TEXT,
  arquivo       TEXT,
  atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_fila_status ON fila (status);
"""


def conectar(db_path: Path = None) -> sqlite3.Connection:
    db_path = db_path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    # migração: bancos criados antes da coluna id_processo
    colunas = [r[1] for r in con.execute("PRAGMA table_info(fila)")]
    if "id_processo" not in colunas:
        with con:
            con.execute("ALTER TABLE fila ADD COLUMN id_processo INTEGER")
    return con


def importar(con, linhas) -> int:
    """linhas: iterável de (npu, origem) ou (npu, origem, id_processo).
    Idempotente: reimportar não duplica nem reseta estado; se o id_processo
    chegar depois (ex.: re-varredura do painel), ele é preenchido."""
    normalizadas = [(l[0], l[1], l[2] if len(l) > 2 else None) for l in linhas]
    with con:
        cur = con.executemany(
            """INSERT INTO fila (npu, origem, id_processo) VALUES (?, ?, ?)
               ON CONFLICT(npu) DO UPDATE SET
                 id_processo = COALESCE(excluded.id_processo, id_processo)""",
            normalizadas)
    return cur.rowcount


def recuperar_orfaos(con, minutos: int = 30) -> int:
    """Na partida do worker: processos presos em 'em_captura' por queda de
    execução anterior voltam para a fila."""
    with con:
        cur = con.execute(
            """UPDATE fila SET status='pendente', atualizado_em=datetime('now','localtime')
               WHERE status='em_captura'
                 AND atualizado_em < datetime('now','localtime', ?)""",
            (f"-{minutos} minutes",))
    return cur.rowcount


def pegar_proximo(con):
    """Claim atômico do próximo pendente. Retorna (npu, origem, id_processo) ou None."""
    with con:
        return con.execute(
            """UPDATE fila SET status='em_captura', tentativas=tentativas+1,
                              atualizado_em=datetime('now','localtime')
               WHERE npu = (SELECT npu FROM fila
                            WHERE status='pendente' AND tentativas < ?
                            ORDER BY origem LIMIT 1)
               RETURNING npu, origem, id_processo""",
            (MAX_TENTATIVAS,)).fetchone()


def _mudar(con, npu, status, via=None, arquivo=None, erro_tipo=None, erro_msg=None):
    with con:
        con.execute(
            """UPDATE fila SET status=?, via=COALESCE(?, via), arquivo=COALESCE(?, arquivo),
                              erro_tipo=?, erro_msg=?,
                              atualizado_em=datetime('now','localtime')
               WHERE npu=?""",
            (status, via, arquivo, erro_tipo,
             erro_msg[:500] if erro_msg else None, npu))


def concluir(con, npu, arquivo=None, via="scraping"):
    _mudar(con, npu, "capturado", via=via, arquivo=arquivo)


def sem_juntada(con, npu, via="scraping"):
    _mudar(con, npu, "sem_juntada", via=via)


def falhar(con, npu, erro_tipo, erro_msg=""):
    _mudar(con, npu, "erro", erro_tipo=erro_tipo, erro_msg=erro_msg)


def marcar_extraido(con, npu):
    _mudar(con, npu, "extraido")


def reprocessar(con, erro_tipo: str = None) -> int:
    """Devolve erros à fila. Sem argumento, reprocessa todos os erros."""
    filtro = "AND erro_tipo = ?" if erro_tipo else ""
    args = (erro_tipo,) if erro_tipo else ()
    with con:
        cur = con.execute(
            f"""UPDATE fila SET status='pendente', tentativas=0,
                               atualizado_em=datetime('now','localtime')
                WHERE status='erro' {filtro}""", args)
    return cur.rowcount


def resumo(con) -> dict:
    linhas = con.execute(
        """SELECT status, COALESCE(erro_tipo, ''), COUNT(*)
           FROM fila GROUP BY status, erro_tipo ORDER BY status""").fetchall()
    return {f"{s}{('/' + e) if e else ''}": n for s, e, n in linhas}


def demo():
    """Self-check: claim atômico, transições e reprocessamento seletivo."""
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)

    def total():
        return con.execute("SELECT COUNT(*) FROM fila").fetchone()[0]

    def id_de(npu):
        return con.execute("SELECT id_processo FROM fila WHERE npu=?", (npu,)).fetchone()[0]

    importar(con, [("0001-a", "datajud", 11), ("0002-b", "painel"), ("0001-a", "datajud")])
    assert total() == 2                        # idempotente: duplicata não cria linha
    assert id_de("0001-a") == 11
    importar(con, [("0002-b", "painel", 22)])  # id chegando depois é preenchido
    assert id_de("0002-b") == 22
    importar(con, [("0001-a", "datajud")])     # reimportar sem id não apaga o id
    assert id_de("0001-a") == 11

    npu, origem, idp = pegar_proximo(con)
    assert (npu, origem, idp) == ("0001-a", "datajud", 11)  # datajud primeiro
    concluir(con, npu, arquivo="a.pdf")

    npu, _, _ = pegar_proximo(con)
    falhar(con, npu, "timeout", "read timeout 30s")
    assert pegar_proximo(con) is None  # fila vazia

    assert reprocessar(con, "sigilo") == 0     # categoria errada não reabre
    assert reprocessar(con, "timeout") == 1    # categoria certa reabre
    npu, _, _ = pegar_proximo(con)
    assert npu == "0002-b"
    sem_juntada(con, npu)

    r = resumo(con)
    assert r.get("capturado") == 1 and r.get("sem_juntada") == 1, r

    # órfãos: simula worker morto (em_captura antigo)
    con.execute("UPDATE fila SET status='em_captura', "
                "atualizado_em=datetime('now','localtime','-2 hours') WHERE npu='0002-b'")
    assert recuperar_orfaos(con, 30) == 1
    print("fila.py: self-check OK")


if __name__ == "__main__":
    demo()
