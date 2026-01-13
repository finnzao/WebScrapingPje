# WebScrapingPje

## Configuração Inicial

### 1. Arquivo .env

Crie um arquivo `.env` na raiz do projeto com suas credenciais:

```env
PJE_USER=seu_cpf
PJE_PASSWORD=sua_senha
```


### 2. Dependências

```bash
pip install requests python-dotenv
```

## Uso via Linha de Comando (CLI)

### Download por Tarefa

```bash
# Ver ajuda
python downloadProcessByTask.py --help

# Listar perfis disponíveis
python downloadProcessByTask.py --listar-perfis

# Listar tarefas (após selecionar perfil)
python downloadProcessByTask.py -p "Assessoria" --listar-tarefas

# Processar uma tarefa
python downloadProcessByTask.py -t "Minutar sentença" -p "Assessoria"

# Processar tarefa favorita com limite
python downloadProcessByTask.py -t "Minutar sentença" --favoritas --limite 5

# Processar sem aguardar download
python downloadProcessByTask.py -t "Minutar sentença" --sem-download
```

### Download por Etiqueta

```bash
# Ver ajuda
python downloadProcessByTag.py --help

# Listar etiquetas
python downloadProcessByTag.py --listar-etiquetas

# Buscar etiquetas
python downloadProcessByTag.py --buscar-etiqueta "Fel"

# Processar uma etiqueta
python downloadProcessByTag.py -e "Felipe" -p "Assessoria"
```

### Consultas Gerais

```bash
# Ver ajuda
python pje_consulta.py --help

# Listar perfis
python pje_consulta.py --listar-perfis

# Listar tarefas
python pje_consulta.py --listar-tarefas -p "Assessoria"

# Listar downloads disponíveis
python pje_consulta.py --listar-downloads

# Ver processos de uma tarefa
python pje_consulta.py --processos-tarefa "Minutar sentença"

# Ver processos de uma etiqueta
python pje_consulta.py --processos-etiqueta "Felipe"
```

## Estrutura do Projeto

```
WebScrapingPje/
├── pje_lib/                    # 📦 BIBLIOTECA COMPARTILHADA
│   ├── __init__.py             # Exports principais
│   ├── client.py               # PJEClient - interface unificada
│   ├── config.py               # Configurações e constantes
│   ├── core/                   # Componentes base
│   │   ├── http_client.py      # Cliente HTTP
│   │   └── session_manager.py  # Gerenciador de sessão
│   ├── models/                 # Dataclasses
│   │   └── __init__.py         # Usuario, Tarefa, Processo, etc.
│   ├── services/               # Lógica de negócio
│   │   ├── auth_service.py     # Autenticação e perfil
│   │   ├── task_service.py     # Tarefas
│   │   ├── tag_service.py      # Etiquetas
│   │   └── download_service.py # Downloads
│   └── utils/                  # Utilitários
│       └── __init__.py         # delay, logger, helpers
│
├── downloadProcessByTask.py    # 📝 Script: download por TAREFA
├── downloadProcessByTag.py     # 📝 Script: download por ETIQUETA
├── consultarJustica.py         # 📝 Script: consultas gerais
├── getDadosInfoLogin.py        # 📝 Seus outros scripts...
├── infoProcessByGeneralSearch.py
├── ...
│
├── .env                        # Credenciais
├── downloads/                  # Arquivos baixados
├── .logs/                      # Logs
└── .session/                   # Sessão persistente
```

## Como Usar

### 1. Uso Básico (PJEClient)

```python
from pje_lib import PJEClient

pje = PJEClient()
pje.login()
pje.select_profile("Assessoria")

# Processar por tarefa
pje.processar_tarefa("Minutar sentença", usar_favoritas=True)

# OU processar por etiqueta
pje.processar_etiqueta("Felipe")

pje.close()
```

### 2. Uso Intermediário (Acesso aos métodos)

```python
from pje_lib import PJEClient

pje = PJEClient()
pje.login()
pje.select_profile("Assessoria")

# Listar tarefas
for tarefa in pje.listar_tarefas():
    print(f"{tarefa.nome}: {tarefa.quantidade_pendente}")

# Listar processos de uma tarefa
processos = pje.listar_processos_tarefa("Minutar sentença")
for p in processos:
    print(p.numero_processo)

# Buscar etiquetas
etiquetas = pje.buscar_etiquetas("Felipe")
for e in etiquetas:
    print(e.nome)

pje.close()
```

### 3. Uso Avançado (Serviços individuais)

```python
from pje_lib import PJEClient
from pje_lib.services import DownloadService, TaskService
from pje_lib.models import Processo, Tarefa

pje = PJEClient()
pje.login()

# Acessar serviços diretamente
# pje._auth     -> AuthService
# pje._tasks    -> TaskService
# pje._tags     -> TagService
# pje._downloads -> DownloadService

# Exemplo: solicitar download manual
pje._downloads.solicitar_download(
    id_processo=12345,
    numero_processo="0001234-56.2024.8.05.0001",
    tipo_documento="Sentenca"
)

pje.close()
```

## Migração dos Scripts Antigos

Para migrar seus scripts existentes, basta trocar:

**ANTES:**
```python
# Código duplicado em cada arquivo
import requests
# ... centenas de linhas repetidas ...

class PJEAutomation:
    # ... implementação completa ...
```

**DEPOIS:**
```python
from pje_lib import PJEClient

pje = PJEClient()
# usar os métodos prontos
```

## Configuração (.env)

```env
USER=seu_cpf
PASSWORD=sua_senha
```

## Tipos de Documento Disponíveis

- `Selecione` (todos)
- `Peticao Inicial`
- `Peticao`
- `Sentenca`
- `Decisao`
- `Despacho`
- `Acordao`
- `Certidao`
- `Procuracao`
- `Documento de Identificacao`
- `Documento de Comprovacao`
- `Outros documentos`

## Vantagens da Nova Estrutura

1. **Código reutilizável**: A biblioteca `pje_lib` pode ser importada por qualquer script
2. **Sem duplicação**: Toda lógica está em um só lugar
3. **Fácil manutenção**: Correções em `pje_lib` afetam todos os scripts
4. **Modular**: Cada serviço tem sua responsabilidade
5. **Testável**: Serviços podem ser testados isoladamente
