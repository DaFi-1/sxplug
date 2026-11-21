# ⚡ sxplug

Gerenciador modular e instalador de bots plug-and-play para a rede **SimpleX Chat** em um único arquivo.

Inspirado na arquitetura do **LazyVim**, o **sxplug** permite adicionar múltiplos bots a um único endereço fixo do SimpleX Chat apenas listando os repositórios do GitHub.

---

## 🚀 Como Usar (Zero Setup)

1. **Clone o repositório:**
```bash
git clone <url-do-repositorio-sxplug>
cd sxplug
```

2. **Configure seus bots em `sxplug.py`:**
Basta declarar os bots pelo formato simplificado `usuario/repositorio`:

```python
PLUGINS: list[str] = [
    "DaFi-1/DinoBot",
    # "usuario/outro-bot",
]
```

3. **Inicie o gerenciador com um único comando:**
```bash
python3 sxplug.py
```

> **✨ Auto-Bootstrap**: O `sxplug` detecta automaticamente se o ambiente virtual raiz existe. Se não existir, ele cria o `.venv`, instala as dependências base e se auto-executa sozinho. Nos próximos inícios, ele pula direto para o boot instantâneo!

### O que o `sxplug` faz automaticamente:
1. **Auto-Clone**: Clona os repositórios listados para a pasta `./plugins/<NomeDoRepo>`.
2. **Ambiente Virtual Isolado**: Cria um `.venv` dedicado dentro da pasta de cada plugin e instala as dependências do `requirements.txt` sem conflitos de versão.
3. **Auto-Discovery**: Descobre os comandos e manipuladores do bot e conecta-os ao SimpleX.
4. **Endereço Fixo e Persistente**: Mantém o mesmo endereço SMP e perfil em `./data/my_bot_chat.db`.
5. **Comandos Nativos no Chat**:
   - `/plugin-list`: Lista todos os bots instalados em uma tabela Markdown.
   - `/plugin-help`: Exibe guia e ajuda do sxplug.

---

## 📁 Estrutura de Diretórios

```text
sxplug/
├── sxplug.py                   # Gerenciador central de plugins
├── requirements.txt            # Dependências básicas do hub
├── README.md                   # Documentação
├── assets/                     # Avatar padrão do hub
├── data/                       # Chaves e banco de dados persistentes do SimpleX
└── plugins/                    # Repositórios clonados (cada um com seu próprio .venv)
    └── DinoBot/                # Plugin #1: Gerenciador de rotinas e tarefas
        ├── .venv/              # Ambiente virtual isolado do plugin
        ├── DinoBot.py
        ├── DinoBot.db
        ├── assets/
        └── tests/
```
