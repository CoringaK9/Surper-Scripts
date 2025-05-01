# Surper Scripts de Tradução e Revisão de Jogos

## Introdução

Este pacote contém dois scripts Python poderosos projetados para auxiliar na tradução e revisão de arquivos de texto de jogos, utilizando a inteligência artificial do Google Gemini para garantir alta qualidade e adaptação cultural para o público brasileiro.

*   **`surper_tradutor.py`**: Focado em traduzir arquivos de texto de um idioma de origem para um idioma de destino, preservando códigos e formatação.
*   **`surper_revisor.py`**: Focado em revisar e aprimorar arquivos de texto já traduzidos, aplicando adaptações culturais, corrigindo inconsistências e melhorando a naturalidade do texto em Português Brasileiro.

Ambos os scripts são otimizados para lidar com arquivos grandes, oferecem gerenciamento de chaves de API, salvamento de progresso, capacidade de continuar processos interrompidos e uma interface interativa ou via linha de comando.

## Funcionalidades Principais (Comuns e Específicas)

**Ambos os Scripts:**

*   **Tradução/Revisão com IA (Google Gemini):** Utiliza os modelos `gemini-1.5-flash` (padrão, mais rápido e econômico) ou `gemini-1.5-pro` (opcional, melhor qualidade, mais lento/caro) para processar o texto.
*   **Gerenciamento de Chaves de API:**
    *   Salva múltiplas chaves de API do Google Gemini de forma segura.
    *   Permite adicionar, remover e selecionar qual chave usar.
    *   Alterna automaticamente para a próxima chave em caso de falha (quota, chave inválida, etc.).
*   **Preservação de Estrutura e Códigos:**
    *   Mantém a estrutura exata do arquivo original, incluindo quebras de linha e linhas em branco.
    *   Protege e restaura códigos entre `<>` e `{}` durante o processo.
    *   Ignora linhas que começam com o caractere `¬` (configurável para outros caracteres, se necessário no futuro).
    *   Ignora linhas que contêm apenas códigos ou que não possuem texto alfabético.
*   **Otimização para Arquivos Grandes:**
    *   Processa o arquivo em blocos (chunks) para evitar limites da API.
    *   Tamanho do bloco adaptativo com base no tamanho do arquivo (ou configurável via argumento).
    *   Salva o progresso e o arquivo de saída após cada bloco processado.
*   **Retomar Processos Interrompidos:**
    *   Cria arquivos de estado (`.state`) para salvar o progresso.
    *   Permite continuar a tradução/revisão exatamente de onde parou.
*   **Delay Configurável:**
    *   Opção de delay fixo (padrão: 3.0 segundos) ou adaptativo entre as chamadas de API para evitar sobrecarga.
    *   Delay pode ser definido via argumento de linha de comando.
*   **Interface Flexível:**
    *   Modo interativo com menus coloridos para facilitar o uso.
    *   Modo via linha de comando para automação e scripting.
*   **Contexto do Jogo:**
    *   Permite fornecer informações sobre o jogo (nome, gênero, estilo, tom, público-alvo, referências PT-BR, termos específicos) para melhorar a qualidade e a adaptação da tradução/revisão.
*   **Tratamento de Erros:**
    *   Sistema de retry para erros temporários da API.
    *   Fallback automático para outras chaves de API salvas.
    *   Pausa automática se todas as chaves de API falharem, salvando o progresso.
    *   Opções interativas em caso de erro persistente (tentar novamente, pular bloco, pausar, cancelar).
*   **Feedback Visual:**
    *   Uso de cores (se `colorama` estiver instalado) para melhor legibilidade.
    *   Barra de progresso (`tqdm`) com estimativa de tempo e velocidade (tokens/segundo).

**`surper_tradutor.py` (Específico):**

*   Traduz de um idioma de origem (padrão: Inglês) para um idioma de destino (padrão: Português Brasileiro).
*   Foco na tradução precisa, mantendo a estrutura e adaptando ao contexto fornecido.

**`super_revisor_v6.py` (Específico):**

*   Revisa um arquivo já traduzido (presumivelmente para Português Brasileiro).
*   Oferece diferentes **Estilos de Revisão** pré-definidos para guiar a IA:
    *   `casual`: Linguagem informal, próxima do dia a dia.
    *   `formal`: Linguagem mais culta e polida.
    *   `epico`: Tom grandioso, comum em RPGs de fantasia.
    *   `humoristico`: Foco em piadas, trocadilhos e tom cômico.
    *   `sombrio`: Tom mais pesado, melancólico ou de terror.
    *   `tecnico`: Precisão terminológica (menos comum em jogos, mas disponível).
    *   `adaptacao_cultural`: Foco principal em adaptar expressões e referências para o Brasil.
    *   `consistencia`: Verifica e corrige termos específicos e nomes.
    *   `naturalidade`: Prioriza fluidez e como o texto soa em Português.
*   O prompt de revisão instrui a IA a focar na melhoria da tradução existente, aplicando o estilo e contexto fornecidos.

## Requisitos

*   Python 3.7 ou superior.
*   Bibliotecas Python: `google-generativeai`, `tqdm`, `tiktoken`, `colorama` (opcional, para cores).
*   Uma ou mais chaves de API do Google Gemini.

## Instalação das Dependências

Você pode instalar as bibliotecas necessárias usando o pip:

```bash
pip install google-generativeai tqdm tiktoken colorama
```

## Obtendo uma Chave de API do Google Gemini

1.  **Acesse o Google AI Studio:** Vá para [https://aistudio.google.com/](https://aistudio.google.com/).
2.  **Faça login:** Use sua conta do Google.
3.  **Crie uma Chave de API:** No menu lateral esquerdo, clique em "Get API key" (Obter chave de API).
4.  **Crie um novo projeto:** Se ainda não tiver um, pode ser necessário criar um projeto no Google Cloud associado à sua conta.
5.  **Gere a chave:** Clique em "Create API key in new project" (Criar chave de API em novo projeto) ou "Create API key in existing project" (Criar chave de API em projeto existente).
6.  **Copie a chave:** Uma nova chave será gerada. Copie-a imediatamente e guarde-a em um local seguro. **Importante:** Trate sua chave de API como uma senha; não a compartilhe publicamente.

*Observação: Pode haver um nível gratuito generoso para começar a usar a API, mas verifique os [preços do Google Gemini](https://ai.google.dev/pricing) para entender os custos associados ao uso intensivo.*

## Como Usar

Existem duas maneiras principais de usar os scripts: modo interativo ou via linha de comando.

### Modo Interativo (Recomendado para Iniciantes)

Simplesmente execute o script desejado sem argumentos (ou com o argumento `-i`):

```bash
python surper_tradutor.py
```

ou

```bash
python surper_revisor.py
```

O script apresentará um menu principal:

1.  **Traduzir/Revisar novo arquivo:** Guia você passo a passo:
    *   Seleção do arquivo de entrada.
    *   Definição dos idiomas (apenas tradutor).
    *   Definição do arquivo de saída (sugere um nome padrão).
    *   Seleção/Gerenciamento da chave de API.
    *   Seleção do modelo Gemini (Flash ou Pro).
    *   Seleção do modo de delay (Fixo ou Adaptativo).
    *   Coleta de informações sobre o jogo (contexto).
    *   Seleção do estilo de revisão (apenas revisor).
    *   Início do processo com barra de progresso.
2.  **Continuar tradução/revisão anterior:** Lista os processos salvos (arquivos `.state`) e permite escolher qual retomar.
3.  **Gerenciar Chaves de API:** Adiciona, remove ou visualiza as chaves salvas.
4.  **Sobre:** Exibe informações sobre o script.
5.  **Sair:** Encerra o programa.

### Modo Linha de Comando

Permite executar o script com todas as configurações definidas por argumentos. Use `-h` ou `--help` para ver todas as opções disponíveis.

**Exemplo (Tradutor):**

```bash
python surper_tradutor.py "meu_jogo.txt" -o "meu_jogo_ptbr.txt" -s "English" -d "Portuguese (Brazil)" --pro --delay-mode adaptativo -k 1
```

*   `"meu_jogo.txt"`: Arquivo de entrada.
*   `-o "meu_jogo_ptbr.txt"`: Arquivo de saída.
*   `-s "English"`: Idioma de origem.
*   `-d "Portuguese (Brazil)"`: Idioma de destino.
*   `--pro`: Usa o modelo Gemini Pro.
*   `--delay-mode adaptativo`: Usa delay adaptativo.
*   `-k 1`: Usa a primeira chave de API salva.

**Exemplo (Revisor):**

```bash
python surper_revisor.py "meu_jogo_traduzido.txt" -e adaptacao_cultural --max-tokens 800 -t 2.5
```

*   `"meu_jogo_traduzido.txt"`: Arquivo de entrada (já traduzido).
*   `-e adaptacao_cultural`: Usa o estilo de revisão "adaptação cultural".
*   `--max-tokens 800`: Define o máximo de tokens por bloco como 800.
*   `-t 2.5`: Define um delay fixo de 2.5 segundos.

**Argumentos Comuns:**

*   `arquivo`: Arquivo de entrada.
*   `-o`, `--output`: Arquivo de saída.
*   `-t`, `--delay`: Define um delay fixo (sobrescreve `--delay-mode`).
*   `--delay-mode`: Define o modo de delay (`fixo` ou `adaptativo`). Padrão: `fixo`.
*   `-m`, `--max-tokens`: Máximo de tokens por bloco (padrão é adaptativo).
*   `-k`, `--api-key-index`: Índice da chave de API salva a usar (começa em 1).
*   `-p`, `--pro`: Usa o modelo Gemini Pro em vez do Flash.
*   `-c`, `--continuar`: Tenta continuar um processo anterior para o arquivo de entrada/saída.
*   `-i`, `--interface`: Força o uso do modo interativo.

**Argumentos Específicos (Tradutor):**

*   `-s`, `--source-lang`: Idioma de origem (padrão: Inglês).
*   `-d`, `--dest-lang`: Idioma de destino (padrão: Português Brasileiro).

**Argumentos Específicos (Revisor):**

*   `-e`, `--estilo`: Estilo de revisão (padrão: `casual`). Use `--listar-estilos` para ver as opções.
*   `--listar-estilos`: Lista os estilos de revisão disponíveis e sai.

### Arquivos de Estado (`.state`)

*   Os scripts criam arquivos `.state` em um subdiretório oculto (`.process_state`) no mesmo local do arquivo de saída.
*   Esses arquivos armazenam o progresso (última linha processada, blocos concluídos), informações do jogo, idiomas/estilos usados, etc.
*   São essenciais para a funcionalidade de "Continuar".
*   São nomeados usando o nome do arquivo de saída e um hash do nome do arquivo de entrada para evitar conflitos.

### Informações de Contexto do Jogo

*   Fornecer detalhes como nome, gênero, estilo, tom, público, referências e termos específicos melhora significativamente a qualidade da tradução/revisão.
*   No modo interativo, o script pergunta por essas informações ao iniciar um novo processo.
*   No modo linha de comando, se não estiver continuando um processo, o script também solicitará essas informações interativamente antes de começar.
*   As informações são salvas no arquivo `.state` para serem reutilizadas ao continuar.

### Ignorando Linhas com `¬`

*   Qualquer linha no arquivo de entrada que, após remover espaços em branco no início e no fim, começar com o caractere `¬`, será completamente ignorada pelo processo de tradução/revisão. A linha original será mantida no arquivo de saída.

## Tratamento de Erros e Interrupções

*   **Interrupção (Ctrl+C):** Pressionar Ctrl+C durante o processo pausará a execução, salvará o progresso atual no arquivo `.state` e permitirá continuar mais tarde.
*   **Erros de API:** O script tenta usar a próxima chave de API salva. Se todas falharem, ele pausa automaticamente, salva o progresso e informa o usuário.
*   **Outros Erros:** Para erros persistentes durante o processamento de um bloco, o script oferece opções interativas (tentar novamente, pular, pausar, cancelar).

## Contribuições

Sugestões e contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou pull requests no repositório (se aplicável).

## Créditos

*   **Desenvolvimento:** CoringaK.
*   **APIs:** Google Gemini.
*   **Bibliotecas:** google-generativeai, tqdm, tiktoken, colorama.

## Licença

Este projeto é distribuído sob a licença MIT.

Copyright (c) 2025 CoringaK.
