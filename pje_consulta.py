#!/usr/bin/env python3
"""
Consulta geral de processos e informações do PJE.

Uso:
    python pje_consulta.py --listar-perfis
    python pje_consulta.py --listar-tarefas -p "Assessoria"
    python pje_consulta.py --help
"""

import argparse
from pje_lib import PJEClient


def main():
    parser = argparse.ArgumentParser(
        description="Consulta de informações do PJE",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python pje_consulta.py --listar-perfis
  python pje_consulta.py --listar-tarefas
  python pje_consulta.py --listar-tarefas -p "Assessoria"
  python pje_consulta.py --listar-etiquetas
  python pje_consulta.py --listar-downloads
  python pje_consulta.py --processos-tarefa "Minutar sentença"
  python pje_consulta.py --processos-etiqueta "Felipe"
        """
    )
    
    # Perfil
    parser.add_argument("-p", "--perfil", type=str, help="Nome do perfil a selecionar")
    
    # Comandos de listagem
    parser.add_argument("--listar-perfis", action="store_true", help="Listar perfis disponíveis")
    parser.add_argument("--listar-tarefas", action="store_true", help="Listar tarefas")
    parser.add_argument("--listar-etiquetas", action="store_true", help="Listar etiquetas")
    parser.add_argument("--listar-downloads", action="store_true", help="Listar downloads disponíveis")
    
    # Processos
    parser.add_argument("--processos-tarefa", type=str, help="Listar processos de uma tarefa")
    parser.add_argument("--processos-etiqueta", type=str, help="Listar processos de uma etiqueta")
    parser.add_argument("--favoritas", action="store_true", help="Usar tarefas favoritas")
    
    # Debug
    parser.add_argument("--debug", action="store_true", help="Modo debug")
    
    args = parser.parse_args()
    
    pje = PJEClient(debug=args.debug)
    
    try:
        if not pje.login():
            print("Falha no login! Verifique as credenciais no arquivo .env")
            print("O arquivo .env deve conter:")
            print("  PJE_USER=seu_cpf")
            print("  PJE_PASSWORD=sua_senha")
            return
        
        # Selecionar perfil
        if args.perfil:
            if not pje.select_profile(args.perfil):
                print(f"Falha ao selecionar perfil: {args.perfil}")
                return
        
        # Listar perfis
        if args.listar_perfis:
            print("\n=== PERFIS DISPONÍVEIS ===")
            for p in pje.listar_perfis():
                print(f"  [{p.index}] {p.nome_completo}")
        
        # Listar tarefas
        elif args.listar_tarefas:
            print("\n=== TAREFAS FAVORITAS ===")
            for t in pje.listar_tarefas_favoritas():
                print(f"  ★ {t.nome}: {t.quantidade_pendente} processos")
            
            print("\n=== TAREFAS GERAIS ===")
            for t in pje.listar_tarefas():
                print(f"  - {t.nome}: {t.quantidade_pendente} processos")
        
        # Listar etiquetas
        elif args.listar_etiquetas:
            print("\n=== ETIQUETAS ===")
            for e in pje.buscar_etiquetas():
                print(f"  - {e.nome} (ID: {e.id})")
        
        # Listar downloads
        elif args.listar_downloads:
            print("\n=== DOWNLOADS DISPONÍVEIS ===")
            downloads = pje.listar_downloads()
            if not downloads:
                print("  Nenhum download disponível")
            for d in downloads:
                print(f"  - {d.nome_arquivo} ({d.situacao})")
                for proc in d.get_numeros_processos():
                    print(f"      └── {proc}")
        
        # Processos de tarefa
        elif args.processos_tarefa:
            print(f"\n=== PROCESSOS DA TAREFA: {args.processos_tarefa} ===")
            processos = pje.listar_processos_tarefa(args.processos_tarefa, args.favoritas)
            print(f"Total: {len(processos)}\n")
            for p in processos[:20]:  # Limita a 20 para não poluir
                print(f"  - {p.numero_processo}")
                if p.polo_ativo:
                    print(f"    Ativo: {p.polo_ativo[:50]}")
                if p.polo_passivo:
                    print(f"    Passivo: {p.polo_passivo[:50]}")
            if len(processos) > 20:
                print(f"\n  ... e mais {len(processos) - 20} processos")
        
        # Processos de etiqueta
        elif args.processos_etiqueta:
            etiqueta = pje.buscar_etiqueta(args.processos_etiqueta)
            if etiqueta:
                print(f"\n=== PROCESSOS DA ETIQUETA: {etiqueta.nome} ===")
                processos = pje.listar_processos_etiqueta(etiqueta.id)
                print(f"Total: {len(processos)}\n")
                for p in processos[:20]:
                    print(f"  - {p.numero_processo}")
                    if p.polo_ativo:
                        print(f"    Ativo: {p.polo_ativo[:50]}")
                if len(processos) > 20:
                    print(f"\n  ... e mais {len(processos) - 20} processos")
            else:
                print(f"Etiqueta '{args.processos_etiqueta}' não encontrada")
        
        else:
            parser.print_help()
        
    finally:
        pje.close()


if __name__ == "__main__":
    main()
