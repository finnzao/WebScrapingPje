#!/usr/bin/env python3
"""
Exemplo de uso do PJE Automacao.
Execute de FORA do pacote: python -m pje_automacao.main
Ou use o script run_pje.py na raiz do projeto.
"""

from .client import PJEAutomacao


def main():
    # Inicializa o cliente
    pje = PJEAutomacao(
        download_dir="./downloads",
        debug=True
    )
    
    try:
        # Limpa sessao antiga e faz login novo
        # Isso resolve o problema de sessao com contexto de perfil perdido
        pje.limpar_sessao()
        
        if not pje.login():
            print("Falha no login!")
            return
        
        # Seleciona perfil
        perfil = "V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL / Assessoria / Assessor"
        
        print("\n" + "=" * 60)
        print("SELECIONANDO PERFIL")
        print("=" * 60)
        
        if not pje.selecionar_perfil(perfil):
            print("Falha ao selecionar perfil!")
            return
        
        # Lista tarefas
        print("\n" + "=" * 60)
        print("TAREFAS DISPONIVEIS")
        print("=" * 60)
        
        print("\nFavoritas:")
        for t in pje.listar_tarefas_favoritas():
            print(f"  [FAV] {t.nome}: {t.quantidade_pendente}")
        
        print("\nGerais:")
        for t in pje.listar_tarefas():
            print(f"  - {t.nome}: {t.quantidade_pendente}")
        
        # Processa tarefa
        relatorio = pje.processar_tarefa(
            nome_tarefa="Minutar sentenca extintiva",
            aguardar=True,
            tempo_espera=300,
            usar_favoritas=True,  # True = favoritas, False = gerais
        )
        
        print(f"\nRelatorio: {relatorio.get('diretorio')}")
        
    finally:
        pje.close()


if __name__ == "__main__":
    main()