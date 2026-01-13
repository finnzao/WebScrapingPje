#!/usr/bin/env python3
"""
Consulta geral de processos e informações.

Uso:
    python consultarJustica.py
"""

from pje_lib import PJEClient


def main():
    pje = PJEClient(debug=True)
    
    try:
        if not pje.login():
            print("Falha no login!")
            return
        
        # Listar perfis
        print("\n=== PERFIS DISPONÍVEIS ===")
        for p in pje.listar_perfis():
            print(f"  [{p.index}] {p.nome_completo}")
        
        # Selecionar perfil
        pje.select_profile("V DOS FEITOS DE REL DE CONS CIV E COMERCIAIS DE RIO REAL")
        
        # Listar tarefas
        print("\n=== TAREFAS ===")
        for t in pje.listar_tarefas():
            print(f"  - {t.nome}: {t.quantidade_pendente} processos")
        
        # Buscar etiquetas
        print("\n=== ETIQUETAS ===")
        for e in pje.buscar_etiquetas():
            print(f"  - {e.nome}")
        
    finally:
        pje.close()


if __name__ == "__main__":
    main()
