# ⚡ sxplug — Documentação e Especificação Técnica

O **sxplug** é um gerenciador modular e instalador de bots plug-and-play em arquivo único para a rede descentralizada **SimpleX Chat**.

---

## 1. Introdução & Visão Geral

### 1.1. O que é o `sxplug`?
O `sxplug` é uma camada de gerenciamento e orquestração de plugins desenvolvida em Python para a rede SimpleX Chat. Ele opera como um **Hub Central** que permite conectar e executar múltiplos bots independentes sob uma única conexão, endereço fixo e perfil SMP, sem necessidade de reconfiguração manual ou complexidade operacional.

### 1.2. Motivação: Por que o `sxplug` foi criado?
Na arquitetura padrão do SimpleX Chat, cada bot exige:
- Uma conexão websocket/IPC separada com o core do SimpleX.
- Um banco de dados de chaves criptográficas (`my_bot_chat.db`).
- Um endereço SMP próprio gerado para os contatos.
- Processos separados rodando no sistema operacional para cada funcionalidade.

Isso gerava atrito para usuários e desenvolvedores que queriam disponibilizar múltiplos serviços (gerenciadores, utilitários, automações) para seus contatos em um único perfil. Além disso, a instalação manual exigia clonar múltiplos repositórios, instalar dependências no mesmo ambiente (gerando conflitos de pacotes) e configurar portas/bancos. O `sxplug` resolve esse gargalo unificando o ecossistema.

### 1.3. Inspiração na Filosofia Modular (Estilo LazyVim / Neovim)
Inspirado na arquitetura do **LazyVim / packer.nvim**, o `sxplug` adota o paradigma declarativo:
- O usuário apenas lista os plugins desejados pelo padrão `usuario/repositorio` no array `PLUGINS`.
- Na inicialização, o gerenciador cuida de todo o ciclo: clonagem, preparação de ambiente isolado, instalação de dependências e registro transparente dos comandos.

### 1.4. Características Únicas & Diferenciais
- **Single-File Hub**: Todo o núcleo do gerenciador reside em um único script legível (`sxplug.py`).
- **Isolamento Total (`.venv` dedicado)**: Cada plugin possui seu próprio ambiente virtual, eliminando qualquer risco de conflito de versões de bibliotecas entre bots diferentes.
- **In-Process Dynamic Injection**: Não utiliza processos externos pesados ou IPC frágil; pacotes e comandos são agregados em tempo de execução via `site.addsitedir`.
- **Endereço e Perfil Únicos e Fixos**: Todos os bots respondem sob a mesma identidade e endereço SMP persistente em `./data/`.
- **Live Administration via Chat**: Permite atualizar todos os plugins via `git pull` diretamente por comandos nativos no chat (`/plugin-update`).

---

## 2. Arquitetura e Funcionamento do Sistema

### 2.1. Visão Geral da Arquitetura
```text
                  +-----------------------------------+
                  |      SimpleX Chat Network         |
                  +-----------------+-----------------+
                                    | (SMP Protocol)
                                    v
                  +-----------------+-----------------+
                  |          sxplug (Hub)             |
                  |     (./data/my_bot_chat.db)       |
                  +--------+-----------------+--------+
                           |                 |
            +--------------+                 +--------------+
            v                                               v
+-----------------------+                       +-----------------------+
|  Plugin 1 (Folder)    |                       |  Plugin 2 (Folder)    |
|  - .venv/ (Isolado)   |                       |  - .venv/ (Isolado)   |
|  - requirements.txt   |                       |  - requirements.txt   |
|  - Comandos & Handlers|                       |  - Comandos & Handlers|
+-----------------------+                       +-----------------------+
```

### 2.2. Ciclo de Vida: Do Startup à Execução
1. **Leitura da Lista `PLUGINS`**: O `sxplug` lê a lista declarada no arquivo principal.
2. **Normalização da URL**: Converte nomes abreviados em links de clone do Git.
3. **Auto-Clone**: Clona repositórios ausentes diretamente na pasta `./plugins/<NomeDoRepo>`.
4. **Setup de `.venv` Dedicado**: Verifica se `./plugins/<NomeDoRepo>/.venv` existe; se não, cria via `python -m venv`.
5. **Instalação Isolada de Dependências**: Se houver `requirements.txt`, executa o `pip` exclusivo do `.venv` daquele plugin.
6. **Injeção de Pacotes & Resolução de Módulo**: Adiciona o `site-packages` do plugin ao runtime e importa o arquivo principal.
7. **Descoberta de Comandos**: Registra todos os manipuladores de comando (`/comando`) no Hub.
8. **Início do Event Loop**: O Hub conecta à rede SimpleX e começa a processar mensagens.

### 2.3. Sintaxe Simplificada (*Shorthand GitHub Syntax*)
O `sxplug` aceita declarações concisas:
```python
PLUGINS: list[str] = [
    "autor/meu-bot",             # Shorthand -> https://github.com/autor/meu-bot.git
    "https://github.com/user/bot", # URL HTTPS tradicional
    "git@github.com:user/bot.git", # URL SSH
]
```

### 2.4. Isolamento Completo com Ambientes Virtuais Dedicados (`.venv`)
Diferente de instaladores comuns que instalam tudo no Python global do sistema (causando colisões entre bibliotecas de versões conflitantes), o `sxplug` cria um `.venv` isolado para cada bot.

Além disso, para garantir máxima performance de boot, o `sxplug` calcula o hash SHA-256 de `requirements.txt` (`.requirements.hash`). Se as dependências já foram instaladas anteriormente e o arquivo não foi alterado, **a invocação do processo do pip é ignorada**, reduzindo o tempo de boot de ~1.3s para menos de **0.2ms** (inicialização instantânea).

### 2.5. Injeção Dinâmica em Tempo de Execução (*Dynamic Runtime Injection*)
Para que o processo central do `sxplug` acesse os pacotes do ambiente virtual do plugin sem necessitar de processos paralelos separados, o gerenciador localiza o diretório:
```text
./plugins/<NomeDoPlugin>/.venv/lib/python*/site-packages
```
E registra dinamicamente através de `site.addsitedir(sp_path)`. Isso carrega módulos, dependências binárias e arquivos `.pth` em tempo real.

### 2.6. Captura e Roteamento de Mensagens no SimpleX Chat
- **Mensagens com Comandos (`/exemplo-comando`)**:
  Quando uma mensagem chega iniciando por barra (`/`), o Hub consulta o catálogo unificado de comandos. O handler específico registrado pelo plugin é acionado com contexto completo (`Message` e `ParsedCommand`).
- **Mensagens de Texto Livre**:
  O `sxplug` possui um manipulador padrão `@hub.on_message(content_type="text")` configurado para ignorar conversas livres genéricas, impedindo respostas concorrentes ou ruído nas conversas.

---

## 3. Guia do Desenvolvedor: Criando Plugins Compatíveis

Qualquer bot SimpleX escrito em Python pode ser transformado em um plugin compatível com o `sxplug` seguindo padrões simples.

### 3.1. Requisitos Mínimos de um Plugin
1. Estar hospedado em um repositório Git (ex: GitHub).
2. Conter um arquivo principal executável (`plugin.py`, `main.py`, `bot.py` ou `<NomeDoRepo>.py`).
3. (Opcional) Conter um `requirements.txt` com suas bibliotecas.

### 3.2. Estrutura Recomendada do Repositório
```text
MeuBotSimplex/
├── requirements.txt            # Dependências necessárias do seu bot
├── README.md                   # Documentação das funcionalidades e comandos
├── .gitignore                  # Ignorar .venv/, *.db, __pycache__/
├── plugin.py                   # Ponto de entrada (Entrypoint)
├── assets/                     # Imagens, mídias ou arquivos estáticos
└── data/                       # (Opcional) Armazenamento de dados do plugin
```

### 3.3. Gerenciamento de Dependências com `requirements.txt`
Declare apenas as bibliotecas que seu bot precisa. Exemplo:
```text
simplex-chat>=7.1.3
pillow>=10.0.0
requests>=2.31.0
```

### 3.4. Localização do Arquivo Principal (Ordem de Resolução de Entrypoints)
Ao carregar o diretório do plugin, o `sxplug` busca automaticamente o ponto de entrada na seguinte ordem de prioridade:
1. `plugin.py` (Recomendado)
2. `<NomeDoRepositório>.py` (Ex: `MeuBot.py`)
3. `bot.py`
4. `main.py`
5. Qualquer arquivo `.py` na raiz que não inicie por sublinhado (`__`).

### 3.5. Padrões de Compatibilidade e Integração

O `sxplug` oferece suporte nativo a dois padrões:

#### 3.5.1. Padrão A: Instância `bot = Bot(...)` (Descoberta Automática)
É o padrão mais comum. Seu bot pode ser desenvolvido e testado de forma independente como um bot SimpleX normal. O `sxplug` detecta a variável `bot` e importa seus comandos automaticamente:

```python
# plugin.py
from simplex_chat import Bot, BotCommand, Message, ParsedCommand

bot = Bot(
    commands=[
        BotCommand(keyword="meubot-ola", label="Envia uma mensagem de boas-vindas"),
    ]
)

@bot.on_command("meubot-ola")
async def ola_handler(msg: Message, cmd: ParsedCommand) -> None:
    await msg.client.api.api_send_text_message(
        msg.chat_info, 
        "👋 Olá! Resposta vinda diretamente do plugin MeuBot!"
    )

if __name__ == "__main__":
    # Permite rodar sozinho fora do sxplug se desejar
    bot.run()
```

#### 3.5.2. Padrão B: Função Hook `setup(hub)` (Injeção Direta)
Ideal para plugins criados especificamente para rodar sob o `sxplug`:

```python
# plugin.py
from simplex_chat import BotCommand, Message, ParsedCommand

def setup(hub):
    # Registra comando na lista de comandos visíveis do Hub
    hub._commands.append(BotCommand("meubot-info", "Exibe informações do MeuBot"))
    
    # Registra o manipulador
    @hub.on_command("meubot-info")
    async def info_handler(msg: Message, cmd: ParsedCommand) -> None:
        await msg.client.api.api_send_text_message(
            msg.chat_info, 
            "ℹ️ Informações fornecidas pelo plugin via setup(hub)."
        )
```

### 3.6. Boas Práticas e Regras de Convivência

#### 3.6.1. Prefixo e Namespacing de Comandos (Obrigatório)
Como múltiplos plugins compartilham o mesmo perfil e conexão SimpleX:
- **Nunca utilize comandos genéricos** como `/help`, `/add`, `/list` ou `/start`.
- Todos os comandos do plugin devem conter obrigatoriamente um prefixo identificador exclusivo do bot.
  - ❌ **Proibido:** `/help`, `/add <texto>`, `/delete <id>`, `/reset`
  - ✅ **Obrigatório:** `/meubot-help`, `/meubot-add <texto>`, `/meubot-del <id>`, `/meubot-reset`

#### 3.6.2. Armazenamento, Bancos de Dados e Caminhos Relativos
Se o plugin mantiver estado ou banco de dados persistente (como SQLite):
- Os caminhos devem ser **estritamente relativos à pasta do próprio plugin**:
  ```python
  BASE_DIR = os.path.dirname(os.path.abspath(__file__))
  DB_PATH = os.path.join(BASE_DIR, "meubot.db")
  ```
- **Nunca grave arquivos na pasta raiz do `sxplug` ou em `data/`** (essa pasta é de uso exclusivo das chaves e identidade SMP do Hub).
- Mantenha `*.db` e `*.sqlite` declarados no `.gitignore` do repositório para evitar versionamento acidental de dados privados de usuários.

#### 3.6.3. Isolamento Total de Dependências
- Declare todas as bibliotecas externas necessárias exclusivamente em `requirements.txt`.
- O `sxplug` cria automaticamente um `.venv` isolado para o seu plugin e injeta suas bibliotecas em tempo de execução. O plugin não deve tentar gerenciar ambientes virtuais manualmente.

#### 3.6.4. Envio de Arquivos, Mídias e Mensagens Formatadas
O `sxplug` já configura as permissões do perfil SimpleX com `files: allow: yes`. Seus plugins podem enviar tabelas, imagens geradas em tempo de execução ou relatórios binários utilizando a API nativa (`msg.client.api.api_send_text_message`, etc.).

---

### 3.7. As 4 Regras de Ouro da Arquitetura do Plugin

| Regra | Requisito | Motivação |
| :--- | :--- | :--- |
| **1. Autonomia Total** | O plugin deve ser um repositório Git independente com `requirements.txt`. | Permite testar e versionar o bot individualmente fora do Hub. |
| **2. Ponto de Entrada Padrão** | Conter `plugin.py` (ou `<NomeDoRepo>.py`). | O `sxplug` descobre e executa o entrypoint de forma transparente. |
| **3. Namespacing Estrito** | Comandos obrigatoriamente prefixados (`/<nome>-comando`). | Evita que dois plugins interceptem o mesmo comando no chat. |
| **4. Dados Confinados** | Bancos de dados e arquivos gravados dentro da pasta do plugin. | Garante que deletar ou atualizar a pasta do plugin não afete outros bots. |

---

## 4. Operação e Gerenciamento do Hub

### 4.1. Como Instalar e Rodar o `sxplug` (Zero Setup)
O `sxplug` possui capacidade de **Auto-Bootstrap**:
1. Clone o repositório ou baixe o arquivo `sxplug.py`.
2. Declare os plugins desejados no array `PLUGINS` em `sxplug.py`.
3. Execute diretamente no terminal:
   ```bash
   python3 sxplug.py
   ```
O `sxplug` verifica se o ambiente virtual raiz existe. Se for a primeira execução com o Python do sistema, ele cria o `.venv`, instala o `requirements.txt` e se reinicia automaticamente dentro do ambiente isolado. Nas próximas execuções, ele pula direto para o boot instantâneo.

### 4.2. Comandos Nativos de Administração
O `sxplug` disponibiliza comandos internos automáticos disponíveis para qualquer contato no chat:
- `/plugin-list`: Lista todos os plugins instalados e seus respectivos repositórios em formato de tabela Markdown.
- `/plugin-help`: Exibe mensagem explicativa e lista de comandos do gerenciador.

> **Nota:** A adição, remoção e configuração de plugins é centralizada exclusivamente de forma limpa e declarativa no arquivo de configuração `PLUGINS = [...]` em `sxplug.py`.

### 4.3. Atualizações Automáticas via Chat
Ao enviar `/plugin-update` no chat do SimpleX:
1. O `sxplug` executa `git pull` de forma segura (sem travamentos de prompt de terminal).
2. Verifica se o `requirements.txt` de algum plugin foi alterado e atualiza o `.venv` respectivo.
3. Devolve um relatório resumido no chat com o status de cada plugin atualizado.

### 4.4. Execução em Produção e Background (Daemon)
Para manter o `sxplug` rodando continuamente em um servidor ou máquina local:
```bash
nohup /caminho/para/.venv/bin/python3 sxplug.py > sxplug.log 2>&1 &
```
Ou configure uma unidade de serviço no `systemd` para inicialização automática com o sistema.

---

## 5. Resolução de Problemas (Troubleshooting) & FAQ

### 5.1. O que acontece se dois plugins usarem o mesmo comando?
O `sxplug` registrará ambos os manipuladores na lista de execução. Para evitar respostas duplicadas ou comportamento inesperado, **sempre adote o prefixo exclusivo do seu bot** nos comandos (Namespacing).

### 5.2. Como o `sxplug` lida com falhas em um plugin individual?
Se um plugin apresentar erro de sintaxe, dependência corrompida ou falha no `setup()`:
- O `sxplug` captura a exceção, registra o erro no log (`logging.error`) e **continua inicializando os demais plugins normalmente**.
- O Hub nunca cai por causa de uma falha em um plugin individual.

### 5.3. Atualização de dependências após novos commits no repositório
O método `update_all()` do gerenciador automaticamente reavalia o `requirements.txt` de cada plugin após realizar o `git pull`, instalando quaisquer novas bibliotecas que o autor do plugin tenha adicionado.
