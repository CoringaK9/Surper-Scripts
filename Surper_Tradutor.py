#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# SUPER TRADUTOR DE JOGOS - v7 (Error Handling, Cache, Projects)

# Desenvolvido para traduzir arquivos de texto de jogos com máxima precisão,
# utilizando IA (Google Gemini), preservando códigos e estrutura.

# Funcionalidades v7:
# - Tratamento de erro API melhorado (mensagens concisas + log detalhado)
# - Cache para tradução consistente de frases repetidas
# - Sistema de gerenciamento de projetos (salvar/carregar contexto)
# - Ignora linhas iniciadas com ¬
# - Gerenciamento de múltiplas chaves API com fallback
# - Preservação de códigos <tag> e {variáveis}
# - Retoma traduções interrompidas
# - Otimização para arquivos grandes (blocos adaptativos)
# - Delay configurável (fixo ou adaptativo)
# - Interface interativa ou via linha de comando
# - Contexto do jogo para melhor qualidade

import os
import sys
import re
import time
import json
import argparse
import random
import hashlib
import logging
import traceback
from datetime import datetime

# --- Configurações Globais --- #

# Tenta importar bibliotecas opcionais
try:
    import google.generativeai as genai
except ImportError:
    print("Erro: Biblioteca 'google-generativeai' não encontrada. Instale com: pip install google-generativeai")
    sys.exit(1)
try:
    from tqdm import tqdm
except ImportError:
    print("Aviso: Biblioteca 'tqdm' não encontrada. Barras de progresso não serão exibidas. Instale com: pip install tqdm")
    tqdm = None # Define tqdm como None se não estiver disponível
try:
    import tiktoken
    # Tenta carregar um codificador comum, pode falhar se offline ou com problemas
    try:
        ENCODING = tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        print(f"Aviso: Falha ao carregar encoding tiktoken 'cl100k_base': {e}. Contagem de tokens pode ser imprecisa.")
        ENCODING = None
except ImportError:
    print("Aviso: Biblioteca 'tiktoken' não encontrada. Contagem de tokens será baseada em palavras. Instale com: pip install tiktoken")
    ENCODING = None
try:
    import colorama
    colorama.init()
    COR_ERRO = colorama.Fore.RED
    COR_AVISO = colorama.Fore.YELLOW
    COR_SUCESSO = colorama.Fore.GREEN
    COR_INFO = colorama.Fore.CYAN
    COR_PROMPT = colorama.Fore.BLUE
    COR_DESTAQUE = colorama.Fore.MAGENTA
    COR_TITULO = colorama.Fore.LIGHTYELLOW_EX
    COR_SUBTITULO = colorama.Fore.LIGHTCYAN_EX
    COR_RESET = colorama.Style.RESET_ALL
except ImportError:
    # Define cores como strings vazias se colorama não estiver disponível
    COR_ERRO, COR_AVISO, COR_SUCESSO, COR_INFO, COR_PROMPT, COR_DESTAQUE, COR_TITULO, COR_SUBTITULO, COR_RESET = "", "", "", "", "", "", "", "", ""

# Modelos Gemini
DEFAULT_MODEL = "gemini-1.5-flash"
PRO_MODEL = "gemini-1.5-pro"

# Configurações Padrão
DEFAULT_DELAY = 3.0
DEFAULT_MAX_TOKENS_PER_BLOCK = 1000 # Valor inicial, pode ser adaptativo
HOME_DIR = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME_DIR, ".SuperScripts")
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LOG_FILE = os.path.join(CONFIG_DIR, "error.log")
PROJECTS_DIR = os.path.join(CONFIG_DIR, "Projetos")
os.makedirs(PROJECTS_DIR, exist_ok=True)
NOPROJECTS_DIR = os.path.join(CONFIG_DIR, "Sem Projetos")

# Variáveis Globais de Estado
API_KEYS = []
CURRENT_API_KEY_INDEX = 0
INTERRUPTED = False
PAUSED = False
INFO_JOGO = {
    "nome": "",
    "genero": "",
    "estilo": "",
    "tom": "",
    "publico": "",
    "referencias": "",
    "termos_especificos": {}
}
CACHE_FRASES = {}

# --- Configuração do Logging --- #
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=LOG_FILE,
    filemode='a' # 'a' para append, 'w' para overwrite a cada execução
)

# --- Funções Auxiliares --- #

def limpar_tela():
    """Limpa a tela do console."""
    os.system('cls' if os.name == 'nt' else 'clear')

def mostrar_banner():
    """Exibe o banner do script."""
    print(f"""{COR_TITULO}
================================================================================
    SUPER TRADUTOR DE JOGOS - v7 (Error Handling, Cache, Projects)
    Desenvolvido para traduzir arquivos de texto de jogos com máxima precisão
================================================================================{COR_RESET}""")

def log_error_detalhado(exception, context="Erro durante execução"):
    """Registra um erro detalhado no arquivo de log, incluindo traceback."""
    error_type = type(exception).__name__
    error_msg = str(exception)
    tb_str = traceback.format_exc()
    logging.error(f"{context} - {error_type}: {error_msg}\nTraceback:\n{tb_str}")

def mostrar_erro(mensagem, exception=None, context="Erro"):
    """Exibe uma mensagem de erro concisa e registra detalhes no log se uma exceção for fornecida."""
    msg_concisa = mensagem
    if exception:
        log_error_detalhado(exception, context)
        erro_str = str(exception).lower()
        # Tenta criar mensagens mais amigáveis para erros comuns da API
        if any(term in erro_str for term in ["quota", "limit", "rate limit"]):
            msg_concisa = f"Erro de API: Limite de cota/requisições atingido. Tentando próxima chave ou aguarde." 
            if "minute" in erro_str:
                 msg_concisa += " (Limite por minuto)"
        elif any(term in erro_str for term in ["api key not valid", "invalid api key", "permission denied"]):
            msg_concisa = f"Erro de API: Chave inválida ou sem permissão." 
            if "expired" in erro_str:
                 msg_concisa += " (Chave expirada?)"
        elif "model not found" in erro_str:
             msg_concisa = f"Erro de API: Modelo '{DEFAULT_MODEL}' ou '{PRO_MODEL}' não encontrado ou indisponível."
        elif "deadline exceeded" in erro_str or "timeout" in erro_str:
             msg_concisa = f"Erro de API: Tempo limite excedido. Verifique a conexão ou tente novamente."
        elif "resource exhausted" in erro_str:
             msg_concisa = f"Erro de API: Recursos esgotados. Tente novamente mais tarde."
        else:
            # Para outros erros, mantém a mensagem original ou uma genérica
            msg_concisa = f"Erro inesperado: {mensagem}. Verifique {LOG_FILE} para detalhes."

    print(f"{COR_ERRO}ERRO: {msg_concisa}{COR_RESET}")

def mostrar_aviso(mensagem):
    """Exibe uma mensagem de aviso."""
    print(f"{COR_AVISO}AVISO: {mensagem}{COR_RESET}")

def mostrar_sucesso(mensagem):
    """Exibe uma mensagem de sucesso."""
    print(f"{COR_SUCESSO}SUCESSO: {mensagem}{COR_RESET}")

def mostrar_info(mensagem):
    """Exibe uma mensagem informativa."""
    print(f"{COR_INFO}INFO: {mensagem}{COR_RESET}")

def obter_entrada(prompt_msg, validacao=None, padrao=None, exemplos=None):
    """Solicita entrada do usuário com validação opcional."""
    prompt_completo = f"{COR_PROMPT}{prompt_msg}{COR_RESET}"
    if exemplos:
        prompt_completo += f" {COR_INFO}(Ex: {exemplos}){COR_RESET}"
    if padrao is not None:
        prompt_completo += f" [{padrao}]: "
    else:
        prompt_completo += ": "

    while True:
        try:
            entrada = input(prompt_completo)
            if not entrada and padrao is not None:
                return padrao
            if validacao:
                if callable(validacao):
                    if validacao(entrada):
                        return entrada
                    else:
                        # A função de validação pode imprimir sua própria mensagem de erro
                        # ou podemos adicionar uma genérica aqui.
                        pass # Assume que a validação imprime o erro
                elif entrada in validacao:
                    return entrada
                else:
                    print(f"{COR_ERRO}Entrada inválida. Opções válidas: {', '.join(validacao)}{COR_RESET}")
            else:
                return entrada # Sem validação, retorna diretamente
        except EOFError:
            mostrar_aviso("\nEntrada cancelada.")
            return None # Ou raise uma exceção específica
        except KeyboardInterrupt:
            mostrar_aviso("\nOperação interrompida pelo usuário.")
            global INTERRUPTED
            INTERRUPTED = True
            raise # Propaga a interrupção

def validar_opcao_menu(opcoes_validas):
    """Função de validação para menus."""
    def validar(entrada):
        if entrada in opcoes_validas:
            return True
        else:
            print(f"{COR_ERRO}Opção inválida. Escolha entre {', '.join(opcoes_validas)}.{COR_RESET}")
            return False
    return validar

def validar_sim_nao(entrada):
    """Valida entrada sim/não."""
    if entrada.lower() in ['s', 'sim', 'n', 'nao', 'não']:
        return True
    else:
        print(f"{COR_ERRO}Resposta inválida. Digite 's' para sim ou 'n' para não.{COR_RESET}")
        return False

def carregar_config():
    """Carrega as configurações (chaves API) do arquivo JSON."""
    global API_KEYS
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                API_KEYS = config.get("api_keys", [])
                if API_KEYS:
                    mostrar_info(f"{len(API_KEYS)} chave(s) de API carregada(s).")
        else:
            API_KEYS = []
    except Exception as e:
        mostrar_erro(f"Falha ao carregar arquivo de configuração '{CONFIG_FILE}'.", e, context="Carregar Config")
        API_KEYS = []

def salvar_config():
    """Salva as configurações (chaves API) no arquivo JSON."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"api_keys": API_KEYS}, f, indent=2)
    except Exception as e:
        mostrar_erro(f"Falha ao salvar arquivo de configuração '{CONFIG_FILE}'.", e, context="Salvar Config")

def gerenciar_api_keys():
    """Permite ao usuário adicionar, remover ou visualizar chaves de API."""
    global API_KEYS
    while True:
        limpar_tela()
        mostrar_banner()
        print(f"\n{COR_SUBTITULO}=== GERENCIAR CHAVES DE API ==={COR_RESET}")
        if API_KEYS:
            print(f"{COR_INFO}Chaves salvas:{COR_RESET}")
            for i, key in enumerate(API_KEYS):
                print(f"  [{i+1}] {key[:4]}...{key[-4:]}")
        else:
            print(f"{COR_INFO}Nenhuma chave de API salva.{COR_RESET}")

        print("\nOpções:")
        print(f"  {COR_PROMPT}[1]{COR_RESET} Adicionar nova chave")
        print(f"  {COR_PROMPT}[2]{COR_RESET} Remover chave")
        print(f"  {COR_PROMPT}[3]{COR_RESET} Voltar ao menu principal")

        escolha = obter_entrada("Escolha uma opção", validar_opcao_menu(["1", "2", "3"]), "3")

        if escolha == "1":
            nova_chave = obter_entrada("Digite a nova chave de API do Google Gemini")
            if nova_chave and nova_chave not in API_KEYS:
                API_KEYS.append(nova_chave)
                salvar_config()
                mostrar_sucesso("Chave API adicionada.")
            elif nova_chave in API_KEYS:
                mostrar_aviso("Essa chave já está salva.")
            else:
                mostrar_aviso("Nenhuma chave digitada.")
        elif escolha == "2":
            if not API_KEYS:
                mostrar_aviso("Nenhuma chave para remover.")
                time.sleep(2)
                continue
            try:
                indice_str = obter_entrada(f"Digite o número da chave a remover (1-{len(API_KEYS)})", [str(i) for i in range(1, len(API_KEYS) + 1)])
                if indice_str:
                    indice = int(indice_str) - 1
                    chave_removida = API_KEYS.pop(indice)
                    salvar_config()
                    mostrar_sucesso(f"Chave {chave_removida[:4]}...{chave_removida[-4:]} removida.")
            except (ValueError, IndexError):
                mostrar_erro("Número inválido.")
            except Exception as e:
                 mostrar_erro("Erro ao remover chave.", e, context="Remover Chave API")
        elif escolha == "3":
            break
        time.sleep(1.5)

def configurar_gemini(api_key, modelo_nome=DEFAULT_MODEL):
    """Configura a API do Gemini com a chave fornecida."""
    try:
        genai.configure(api_key=api_key)
        # Verifica se o modelo existe (opcional, mas bom para feedback rápido)
        # model_info = genai.get_model(f"models/{modelo_nome}") # Pode causar erro se a chave for inválida
        modelo = genai.GenerativeModel(modelo_nome)
        mostrar_sucesso(f"Modelo {modelo_nome} configurado com a chave {api_key[:4]}...{api_key[-4:]}.")
        return modelo
    except Exception as e:
        mostrar_erro(f"Falha ao configurar API Gemini com a chave {api_key[:4]}...{api_key[-4:]}. Verifique a chave e a conexão.", e, context="Configurar Gemini")
        return None

def tentar_proxima_api_key():
    """Tenta usar a próxima chave de API da lista."""
    global CURRENT_API_KEY_INDEX
    if not API_KEYS or len(API_KEYS) <= 1:
        return None # Não há outras chaves para tentar

    CURRENT_API_KEY_INDEX = (CURRENT_API_KEY_INDEX + 1) % len(API_KEYS)
    nova_chave = API_KEYS[CURRENT_API_KEY_INDEX]
    mostrar_info(f"Tentando usar a próxima chave de API: {nova_chave[:4]}...{nova_chave[-4:]}")
    return nova_chave

def configurar_gemini_com_fallback(chave_inicial=None, modelo_nome=DEFAULT_MODEL):
    """Tenta configurar o Gemini, usando fallback para outras chaves se necessário."""
    global CURRENT_API_KEY_INDEX

    if chave_inicial:
        modelo = configurar_gemini(chave_inicial, modelo_nome)
        if modelo: return modelo
        # Se a chave inicial falhar, tenta a próxima
        chave_nova = tentar_proxima_api_key()
        if not chave_nova or chave_nova == chave_inicial: # Evita loop infinito se só tiver 1 chave
            return None
        return configurar_gemini(chave_nova, modelo_nome)
    else:
        # Se nenhuma chave inicial foi dada, tenta a partir do índice atual
        if not API_KEYS:
            mostrar_erro("Nenhuma chave de API configurada.")
            return None
        
        chave_atual = API_KEYS[CURRENT_API_KEY_INDEX]
        modelo = configurar_gemini(chave_atual, modelo_nome)
        if modelo: return modelo

        # Tenta as outras chaves em sequência
        indice_inicial = CURRENT_API_KEY_INDEX
        while True:
            chave_nova = tentar_proxima_api_key()
            if not chave_nova or CURRENT_API_KEY_INDEX == indice_inicial: # Voltou ao início?
                break
            modelo = configurar_gemini(chave_nova, modelo_nome)
            if modelo: return modelo
        
        mostrar_erro("Falha ao configurar o Gemini com todas as chaves de API disponíveis.")
        return None

def contar_tokens(texto):
    """Conta tokens usando tiktoken se disponível, senão usa contagem de palavras."""
    if ENCODING:
        try:
            return len(ENCODING.encode(texto))
        except Exception as e:
            # Fallback em caso de erro inesperado com tiktoken
            # print(f"Aviso: Erro ao codificar com tiktoken: {e}. Usando contagem de palavras.")
            return len(texto.split())
    else:
        # Fallback para contagem de palavras
        return len(texto.split())

def extrair_codigos_e_chaves(texto):
    """Extrai códigos <...> e {...} e os substitui por marcadores [[n]]."""
    elementos_protegidos = []
    
    def substituir(match):
        elemento = match.group(0)
        # Evita adicionar duplicados exatos (embora raro com regex)
        # if elemento not in elementos_protegidos:
        elementos_protegidos.append(elemento)
        return f"[[{len(elementos_protegidos)-1}]]"

    # Regex para encontrar <...> ou {...} (não aninhados)
    # Prioriza encontrar o menor match possível com `?`
    texto_modificado = re.sub(r"(<[^>]*?>|\{[^\}]*?\})", substituir, texto)
    
    return texto_modificado, elementos_protegidos

def restaurar_codigos_e_chaves(texto_modificado, elementos_protegidos):
    """Restaura os códigos <...> e {...} a partir dos marcadores [[n]]."""
    texto_restaurado = texto_modificado
    # Itera de trás para frente para evitar problemas com índices menores ao substituir
    for i in range(len(elementos_protegidos) - 1, -1, -1):
        marcador = f"[[{i}]]"
        # Usa replace simples, pois o marcador deve ser único
        # Adiciona tratamento para caso o marcador não seja encontrado (embora não devesse acontecer)
        if marcador in texto_restaurado:
             texto_restaurado = texto_restaurado.replace(marcador, elementos_protegidos[i])
        else:
             # Log ou aviso se um marcador esperado não for encontrado
             mostrar_aviso(f"Marcador {marcador} não encontrado no texto processado pela IA. Pode indicar problema na resposta da IA.")
             log_error_detalhado(Exception(f"Marcador {marcador} ausente"), context="Restaurar Códigos")

    # Remove quaisquer marcadores [[n]] remanescentes que a IA possa ter gerado ou deixado
    # Usa regex para ser mais robusto contra espaços extras
    texto_restaurado_final, num_subs = re.subn(r"\s*\[\[\d+\]\]\s*", " ", texto_restaurado)
    if num_subs > 0:
        mostrar_aviso(f"{num_subs} marcador(es) [[n]] inesperado(s) removido(s) do texto final.")
        log_error_detalhado(Exception(f"{num_subs} marcadores inesperados removidos"), context="Limpeza Final Marcadores")
        
    return texto_restaurado_final.strip() # Remove espaços extras no início/fim

def calcular_tamanho_bloco_adaptativo(tamanho_arquivo, num_linhas):
    """Calcula o tamanho ideal de bloco com base no tamanho do arquivo."""
    # Ajusta a lógica para ser mais granular e talvez considerar número de linhas
    if tamanho_arquivo > 50 * 1024 * 1024: return 500 # Arquivos muito grandes, blocos menores
    if tamanho_arquivo > 10 * 1024 * 1024: return 700
    if tamanho_arquivo > 5 * 1024 * 1024: return 900
    if tamanho_arquivo > 1 * 1024 * 1024: return 1200
    return 1500 # Arquivos menores, blocos maiores

def calcular_delay_adaptativo(tamanho_arquivo, tamanho_bloco):
    """Calcula o delay ideal entre traduções com base no tamanho do arquivo."""
    base_delay = 1.0
    if tamanho_arquivo > 10 * 1024 * 1024: base_delay = 2.5
    elif tamanho_arquivo > 5 * 1024 * 1024: base_delay = 2.0
    elif tamanho_arquivo > 1 * 1024 * 1024: base_delay = 1.5
    # Adiciona um pequeno fator aleatório para evitar padrões muito rígidos
    # Considera também o tamanho do bloco (blocos maiores podem precisar de mais tempo?)
    return max(1.0, (base_delay + (tamanho_bloco / 2000)) * (0.9 + 0.2 * random.random())) # Garante delay mínimo de 1s

def linha_precisa_processamento(linha):
    """Verifica se uma linha precisa ser traduzida/revisada."""
    linha_strip = linha.strip()
    if not linha_strip: return False
    # Verifica se a linha começa com ¬
    if linha_strip.startswith("¬"): return False
    # Verifica se a linha contém APENAS códigos <> ou chaves {}
    if re.fullmatch(r"\s*([<\{][^>\}]*[>\}]\s*)+\s*", linha): return False
    # Verifica se há pelo menos uma letra (ignora linhas só com números/pontuação)
    if not re.search(r"[a-zA-ZÀ-ÖØ-öø-ÿ]", linha): return False
    return True

def agrupar_linhas_para_processamento(linhas, max_tokens):
    """
    Agrupa linhas para tradução/revisão, preservando a estrutura exata.
    Retorna uma lista de dicionários, onde cada dicionário representa um bloco.
    Blocos podem ser:
    - Processáveis pela API: {'texto_para_processar': str, 'indices_linhas': list, 'mapa_linhas': dict}
    - Não processáveis (linhas vazias, ignoradas, só código): {'texto_para_processar': None, 'indices_linhas': list, 'linha_original': str}
    """
    blocos = []
    bloco_atual = []
    indices_linhas_bloco_atual = []
    mapa_linhas_bloco_atual = {}
    tokens_bloco_atual = 0
    contador_linhas_no_bloco = 0

    def finalizar_bloco_atual():
        nonlocal bloco_atual, indices_linhas_bloco_atual, mapa_linhas_bloco_atual, tokens_bloco_atual, contador_linhas_no_bloco
        if bloco_atual:
            blocos.append({
                "texto_para_processar": "\n".join(bloco_atual),
                "indices_linhas": list(indices_linhas_bloco_atual),
                "mapa_linhas": mapa_linhas_bloco_atual.copy()
            })
            # Reseta para o próximo bloco
            bloco_atual = []
            indices_linhas_bloco_atual = []
            mapa_linhas_bloco_atual = {}
            tokens_bloco_atual = 0
            contador_linhas_no_bloco = 0

    for i, linha in enumerate(linhas):
        precisa_proc = linha_precisa_processamento(linha)

        if not precisa_proc:
            # Finaliza o bloco processável atual antes de adicionar a linha não processável
            finalizar_bloco_atual()
            # Adiciona a linha não processável como um bloco separado
            blocos.append({
                "texto_para_processar": None, # Indica que não precisa de API
                "indices_linhas": [i],
                "linha_original": linha
            })
            continue

        # Linha precisa de processamento
        # Remove quebra de linha final para evitar duplicar ao juntar
        linha_proc = linha.rstrip("\n") 
        tokens_linha = contar_tokens(linha_proc)

        # Verifica se a linha sozinha excede o limite (caso raro)
        if tokens_linha > max_tokens:
            mostrar_aviso(f"Linha {i+1} excede o limite de tokens ({tokens_linha}/{max_tokens}). Será processada separadamente.")
            # Finaliza o bloco atual se houver
            finalizar_bloco_atual()
            # Adiciona a linha grande como um bloco próprio
            blocos.append({
                "texto_para_processar": linha_proc,
                "indices_linhas": [i],
                "mapa_linhas": {0: i} # Mapa simples para bloco de linha única
            })
            continue

        # Verifica se adicionar a linha excede o limite do bloco atual
        # Adiciona +1 token para a quebra de linha que será inserida entre as linhas
        if tokens_bloco_atual + tokens_linha + (1 if bloco_atual else 0) > max_tokens and bloco_atual:
            # Finaliza o bloco atual
            finalizar_bloco_atual()
            # Inicia um novo bloco com a linha atual
            bloco_atual = [linha_proc]
            indices_linhas_bloco_atual = [i]
            mapa_linhas_bloco_atual = {0: i}
            tokens_bloco_atual = tokens_linha
            contador_linhas_no_bloco = 1
        else:
            # Adiciona a linha ao bloco atual
            bloco_atual.append(linha_proc)
            indices_linhas_bloco_atual.append(i)
            mapa_linhas_bloco_atual[contador_linhas_no_bloco] = i
            # Adiciona token da quebra de linha se não for a primeira linha do bloco
            tokens_bloco_atual += tokens_linha + (1 if len(bloco_atual) > 1 else 0)
            contador_linhas_no_bloco += 1

    # Adiciona o último bloco se houver linhas nele
    finalizar_bloco_atual()

    return blocos

def processar_texto_com_gemini(modelo, texto_original, prompt_base, retry_count=3, retry_delay=5):
    """
    Processa (traduz ou revisa) o texto usando o modelo Gemini com sistema de retry,
    fallback de API key, tratamento de erro melhorado e log.
    """
    global INTERRUPTED, PAUSED, API_KEYS, CURRENT_API_KEY_INDEX, genai

    if not texto_original or not texto_original.strip():
        return texto_original

    texto_modificado, elementos_protegidos = extrair_codigos_e_chaves(texto_original)

    prompt_completo = prompt_base + "\n\n" + texto_modificado

    tentativas_chave_api = 0
    max_tentativas_chave_api = len(API_KEYS) if API_KEYS else 1

    while tentativas_chave_api < max_tentativas_chave_api:
        if INTERRUPTED:
            raise KeyboardInterrupt("Processamento interrompido pelo usuário")

        modelo_atual = modelo # Começa com o modelo configurado inicialmente
        api_key_usada = API_KEYS[CURRENT_API_KEY_INDEX] if API_KEYS else None
        chave_atual_str = api_key_usada[:4] + "..." + api_key_usada[-4:] if api_key_usada else "N/A"

        # Verifica se a chave e o modelo estão configurados
        if not modelo_atual or not api_key_usada:
             mostrar_erro("Modelo Gemini ou chave API não configurados corretamente.")
             log_error_detalhado(Exception("Configuração inválida de modelo/chave"), context="Pré-processamento Gemini")
             api_key_nova = tentar_proxima_api_key()
             if not api_key_nova:
                 PAUSED = True # Pausa se não houver mais chaves
                 raise Exception("Falha ao configurar o modelo Gemini: Nenhuma chave de API válida encontrada.")
             # Tenta reconfigurar com a nova chave
             modelo_atual = configurar_gemini_com_fallback(api_key_nova, modelo.model_name if modelo else DEFAULT_MODEL)
             if not modelo_atual:
                 PAUSED = True # Pausa se a reconfiguração falhar
                 raise Exception("Falha ao configurar o modelo Gemini com todas as chaves.")
             modelo = modelo_atual # Atualiza o modelo global se a reconfiguração funcionou
             api_key_usada = api_key_nova
             chave_atual_str = api_key_usada[:4] + "..." + api_key_usada[-4:]
             tentativas_chave_api += 1
             continue # Tenta processar com a nova configuração

        # Loop de tentativas para a chave atual
        for attempt in range(retry_count + 1):
            if INTERRUPTED:
                raise KeyboardInterrupt("Processamento interrompido pelo usuário")

            try:
                # Garante que a API está configurada com a chave atual antes de cada chamada
                # (Pode ser redundante se configurar_gemini_com_fallback já fez isso, mas garante)
                genai.configure(api_key=api_key_usada)
                # Recria o objeto do modelo para garantir que está usando a configuração correta
                modelo_gemini_instancia = genai.GenerativeModel(modelo_atual.model_name)

                resposta = modelo_gemini_instancia.generate_content(prompt_completo)
                
                # Verifica se a resposta tem conteúdo antes de acessar .text
                if not resposta.parts:
                    raise Exception("Resposta da API vazia ou bloqueada (possivelmente por filtros de segurança). Verifique o prompt ou o conteúdo.")
                
                texto_processado = resposta.text
                texto_final = restaurar_codigos_e_chaves(texto_processado, elementos_protegidos)

                # Verificação e ajuste de linhas
                linhas_originais = texto_original.split("\n")
                linhas_processadas = texto_final.split("\n")
                if len(linhas_originais) != len(linhas_processadas):
                    mostrar_aviso(f"Número de linhas ({len(linhas_processadas)}) não corresponde ao original ({len(linhas_originais)}). Ajustando...")
                    log_error_detalhado(Exception(f"Inconsistência no número de linhas: {len(linhas_processadas)} vs {len(linhas_originais)}"), context="Ajuste de Linhas")
                    if len(linhas_processadas) < len(linhas_originais):
                        linhas_processadas.extend(["" for _ in range(len(linhas_originais) - len(linhas_processadas))])
                    else:
                        linhas_processadas = linhas_processadas[:len(linhas_originais)]
                    texto_final = "\n".join(linhas_processadas)

                return texto_final # Sucesso

            except Exception as e:
                # Mostra erro conciso e loga detalhes
                mostrar_erro(f"Erro ao processar com chave {chave_atual_str}", e, context="Processamento Gemini")
                erro_str = str(e).lower()

                # Erro de cota, chave inválida, permissão, etc. -> Tenta próxima chave
                if any(term in erro_str for term in ["quota", "limit", "rate limit", "api key not valid", "invalid api key", "permission denied", "resource exhausted"]):
                    api_key_nova = tentar_proxima_api_key()
                    if api_key_nova:
                        # Tenta reconfigurar o modelo com a nova chave
                        modelo_novo = configurar_gemini_com_fallback(api_key_nova, modelo.model_name if modelo else DEFAULT_MODEL)
                        if modelo_novo:
                            modelo = modelo_novo # Atualiza o modelo global
                            tentativas_chave_api += 1
                            break # Sai do loop de retry para tentar com a nova chave no próximo ciclo do while
                        else:
                            # Se a configuração falhar, continua tentando outras chaves (o loop while fará isso)
                            tentativas_chave_api += 1 # Incrementa para evitar loop infinito se configurar_gemini falhar sempre
                            continue # Próxima iteração do while (se houver mais chaves)
                    else:
                        # Nenhuma outra chave disponível
                        mostrar_erro("Todas as chaves de API falharam ou não há mais chaves.")
                        PAUSED = True
                        raise Exception(f"Erro de API: {e}. Nenhuma chave válida restante.")

                # Outros erros (timeout, erro de servidor, etc.) -> Retry
                elif attempt < retry_count:
                    tempo_espera = retry_delay * (attempt + 1)
                    mostrar_info(f"Tentativa {attempt+1}/{retry_count+1} falhou. Aguardando {tempo_espera}s antes de tentar novamente...")
                    try:
                        time.sleep(tempo_espera)
                    except KeyboardInterrupt:
                        mostrar_aviso("Interrupção durante a espera.")
                        INTERRUPTED = True
                        raise KeyboardInterrupt("Processamento interrompido pelo usuário durante espera")
                else:
                    # Erro persistente após retries com a mesma chave
                    mostrar_erro(f"Erro persistente no processamento após {retry_count+1} tentativas com a chave {chave_atual_str}. Verifique {LOG_FILE}.")
                    opcoes = [
                        "Tentar novamente este bloco (com a mesma chave)",
                        "Tentar com a próxima chave de API (se disponível)",
                        "Pular este bloco e continuar",
                        "Pausar e tentar mais tarde (salva o progresso)",
                        "Cancelar tudo"
                    ]
                    print("\nOpções:")
                    for i, opcao in enumerate(opcoes, 1):
                        print(f"  {COR_PROMPT}[{i}] {opcao}{COR_RESET}")

                    resposta = obter_entrada("Escolha uma opção", validar_opcao_menu([str(i) for i in range(1, len(opcoes) + 1)]), "4")

                    if resposta == "1":
                        mostrar_info("Tentando novamente o bloco...")
                        # Reinicia as tentativas para este bloco com a mesma chave
                        continue # Volta para o início do loop de retry (for attempt...)
                    elif resposta == "2":
                        api_key_nova = tentar_proxima_api_key()
                        if api_key_nova:
                             modelo_novo = configurar_gemini_com_fallback(api_key_nova, modelo.model_name if modelo else DEFAULT_MODEL)
                             if modelo_novo:
                                 modelo = modelo_novo
                                 tentativas_chave_api += 1
                                 break # Sai do loop de retry para tentar com a nova chave no próximo ciclo do while
                             else:
                                 mostrar_erro("Falha ao configurar com a próxima chave. Escolha outra opção.")
                                 # Permanece no loop de opções
                                 continue # Volta a mostrar as opções
                        else:
                            mostrar_aviso("Não há mais chaves de API para tentar. Escolha outra opção.")
                            continue # Volta a mostrar as opções
                    elif resposta == "3":
                        mostrar_aviso("Pulando este bloco.")
                        return texto_original # Retorna o texto original para este bloco
                    elif resposta == "4":
                        PAUSED = True
                        raise Exception("Processamento pausado pelo usuário para continuar mais tarde")
                    else: # resposta == "5"
                        INTERRUPTED = True
                        raise KeyboardInterrupt("Processamento cancelado pelo usuário")

            # Se o break interno (troca de chave) foi acionado, sai do loop de retry
            # para que o loop while possa tentar com a nova chave.
            if 'api_key_nova' in locals() and api_key_nova: 
                break 

        # Se o loop de retry (for attempt...) terminou sem sucesso para a chave atual,
        # o loop while continuará para a próxima chave (se houver e se 'break' não foi chamado antes).
        # Se 'break' foi chamado devido à troca de chave, o while tentará com a nova.
        if tentativas_chave_api >= max_tentativas_chave_api and attempt == retry_count:
             # Se todas as chaves falharam após todos os retries
             mostrar_erro(f"Falha no processamento do bloco após tentar todas as chaves e retries. Verifique {LOG_FILE}.")
             PAUSED = True # Pausa para intervenção manual
             raise Exception("Falha crítica no processamento do bloco.")

# --- Funções de Gerenciamento de Estado e Projeto --- #

def criar_arquivo_estado(arquivo_entrada, arquivo_saida, tipo_processo, projeto_nome=None, **kwargs):
    """Cria um arquivo de estado para rastrear o progresso, associado a um projeto se fornecido."""
    try:
        # Diretório de estado dentro do diretório do projeto ou diretório padrão
        if projeto_nome:
            diretorio_base = os.path.join(PROJECTS_DIR, projeto_nome)
        else:
            diretorio_base = os.path.dirname(arquivo_saida) if arquivo_saida else "."
        diretorio_estado = os.path.join(NOPROJECTS_DIR)
        os.makedirs(diretorio_estado, exist_ok=True)

        hash_arquivo = hashlib.md5(os.path.abspath(arquivo_entrada).encode()).hexdigest()[:10]
        nome_arquivo_saida_base = os.path.basename(arquivo_saida) if arquivo_saida else "output"
        # Nome do arquivo de estado inclui tipo e hash para evitar conflitos
        arquivo_estado = os.path.join(diretorio_estado, f"{nome_arquivo_saida_base}.{hash_arquivo}.{tipo_processo}.state")

        # Cria o arquivo apenas se não existir, para não sobrescrever um estado existente ao iniciar
        if not os.path.exists(arquivo_estado):
            estado = {
                "arquivo_entrada": os.path.abspath(arquivo_entrada),
                "arquivo_saida": os.path.abspath(arquivo_saida) if arquivo_saida else None,
                "tipo_processo": tipo_processo,
                "projeto_nome": projeto_nome,
                "info_jogo": INFO_JOGO, # Salva o contexto atual
                "ultima_linha_processada": -1,
                "blocos_processados": 0,
                "total_blocos": 0,
                "timestamp_criacao": datetime.now().isoformat(),
                "timestamp_atualizacao": datetime.now().isoformat(),
                "concluido": False
            }
            estado.update(kwargs) # Adiciona argumentos específicos (idioma, estilo)

            with open(arquivo_estado, "w", encoding="utf-8") as f:
                json.dump(estado, f, indent=2)
            mostrar_info(f"Arquivo de estado criado: {arquivo_estado}")

        return arquivo_estado
    except Exception as e:
        mostrar_erro(f"Erro ao criar arquivo de estado", e, context="Criar Estado")
        return None

def atualizar_arquivo_estado(arquivo_estado, ultima_linha, blocos_processados, total_blocos, concluido=False):
    """Atualiza o arquivo de estado com o progresso atual."""
    if not arquivo_estado or not os.path.exists(arquivo_estado): return False # Verifica se existe antes de tentar ler
    try:
        with open(arquivo_estado, "r", encoding="utf-8") as f:
            estado = json.load(f)

        estado["ultima_linha_processada"] = ultima_linha
        estado["blocos_processados"] = blocos_processados
        # Atualiza total_blocos apenas se for maior que o anterior (pode mudar com blocos adaptativos?)
        estado["total_blocos"] = max(estado.get("total_blocos", 0), total_blocos)
        estado["timestamp_atualizacao"] = datetime.now().isoformat()
        estado["concluido"] = concluido

        # Salva atomicamente (renomeando) para evitar corrupção
        arquivo_temp = arquivo_estado + ".tmp"
        with open(arquivo_temp, "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=2)
        os.replace(arquivo_temp, arquivo_estado)
        return True
    except FileNotFoundError:
        mostrar_erro(f"Arquivo de estado não encontrado para atualização: {arquivo_estado}")
        return False
    except Exception as e:
        mostrar_erro(f"Erro ao atualizar arquivo de estado", e, context="Atualizar Estado")
        return False

def carregar_estado(arquivo_estado):
    """Carrega o estado de um processo anterior."""
    if not arquivo_estado or not os.path.exists(arquivo_estado):
        return None
    try:
        with open(arquivo_estado, "r", encoding="utf-8") as f:
            estado = json.load(f)
        # Carrega INFO_JOGO do estado
        global INFO_JOGO
        if "info_jogo" in estado:
            INFO_JOGO = estado["info_jogo"]
            mostrar_info("Contexto do jogo carregado do estado anterior.")
        return estado
    except Exception as e:
        mostrar_erro(f"Erro ao carregar arquivo de estado", e, context="Carregar Estado")
        return None

def listar_estados_salvos(diretorio_base=None):
    if diretorio_base is None:
        diretorio_base = NOPROJECTS_DIR
    """Lista arquivos de estado encontrados."""
    estados_encontrados = []
    try:
        # Procura no diretório de projetos
        if os.path.exists(PROJECTS_DIR):
            for nome_projeto in os.listdir(PROJECTS_DIR):
                proj_path = os.path.join(PROJECTS_DIR, nome_projeto)
                if os.path.isdir(proj_path):
                    estado_dir = os.path.join(proj_path, ".process_state")
                    if os.path.exists(estado_dir):
                        for filename in os.listdir(estado_dir):
                            if filename.endswith(".state"):
                                estados_encontrados.append(os.path.join(estado_dir, filename))
        
        # Procura no diretório atual (para processos fora de projetos)
        estado_dir_local = os.path.join(NOPROJECTS_DIR)
        if os.path.exists(estado_dir_local):
             for filename in os.listdir(estado_dir_local):
                 if filename.endswith(".state"):
                     path_estado = os.path.join(estado_dir_local, filename)
                     if path_estado not in estados_encontrados: # Evita duplicados se diretório base for um projeto
                         estados_encontrados.append(path_estado)
                         
    except Exception as e:
        mostrar_erro("Erro ao listar estados salvos.", e, context="Listar Estados")
    return estados_encontrados

def selecionar_estado_para_continuar():
    """Permite ao usuário selecionar um estado salvo para continuar."""
    estados = listar_estados_salvos()
    if not estados:
        mostrar_aviso("Nenhum processo anterior encontrado para continuar.")
        return None, None

    print(f"\n{COR_SUBTITULO}=== CONTINUAR PROCESSO ANTERIOR ==={COR_RESET}")
    print(f"{COR_INFO}Processos encontrados:{COR_RESET}")
    estados_info = []
    for i, path_estado in enumerate(estados):
        try:
            with open(path_estado, 'r', encoding='utf-8') as f:
                estado = json.load(f)
            nome_proj = estado.get("projeto_nome", "(Sem Projeto)")
            arquivo_out = os.path.basename(estado.get("arquivo_saida", "N/A"))
            tipo_proc = estado.get("tipo_processo", "N/A").capitalize()
            progresso = estado.get("blocos_processados", 0)
            total = estado.get("total_blocos", 0)
            percentual = (progresso / total * 100) if total > 0 else 0
            concluido = estado.get("concluido", False)
            status = f"{COR_SUCESSO}Concluído{COR_RESET}" if concluido else f"{percentual:.1f}%" 
            info_str = f"[{i+1}] {COR_DESTAQUE}{nome_proj}{COR_RESET} - {tipo_proc}: {arquivo_out} ({status})"
            print(info_str)
            estados_info.append({"path": path_estado, "estado": estado})
        except Exception as e:
            mostrar_erro(f"Erro ao ler estado {path_estado}", e, context="Selecionar Estado")
            print(f"  [{i+1}] Erro ao carregar estado: {os.path.basename(path_estado)}")
            estados_info.append(None) # Marcador para opção inválida

    print(f"  {COR_PROMPT}[{len(estados)+1}]{COR_RESET} Voltar")

    while True:
        escolha_str = obter_entrada("Escolha o processo a continuar", [str(i) for i in range(1, len(estados) + 2)], str(len(estados)+1))
        if not escolha_str: continue
        escolha_idx = int(escolha_str) - 1

        if escolha_idx == len(estados): # Voltar
            return None, None
        
        if 0 <= escolha_idx < len(estados) and estados_info[escolha_idx] is not None:
            estado_selecionado = estados_info[escolha_idx]["estado"]
            if estado_selecionado.get("concluido", False):
                mostrar_aviso("Este processo já foi concluído. Para reprocessar, inicie um novo.")
                # Poderia oferecer opção de reprocessar, mas por segurança, melhor iniciar novo
                continue
            
            # Verifica se o arquivo de entrada ainda existe
            if not os.path.exists(estado_selecionado.get("arquivo_entrada", "")):
                 mostrar_erro(f"Arquivo de entrada original '{estado_selecionado.get('arquivo_entrada')}' não encontrado. Não é possível continuar.")
                 continue
                 
            return estados_info[escolha_idx]["path"], estado_selecionado
        else:
            mostrar_erro("Opção inválida ou estado corrompido.")

def carregar_projeto(nome_projeto):
    """Carrega as informações de um projeto (contexto do jogo)."""
    global INFO_JOGO
    try:
        arquivo_projeto = os.path.join(PROJECTS_DIR, nome_projeto, "projeto.json")
        if os.path.exists(arquivo_projeto):
            with open(arquivo_projeto, 'r', encoding='utf-8') as f:
                dados_projeto = json.load(f)
                INFO_JOGO = dados_projeto.get("info_jogo", INFO_JOGO) # Carrega info_jogo
                mostrar_sucesso(f"Projeto '{nome_projeto}' carregado.")
                # Exibe resumo?
                print("\nResumo do Projeto Carregado:")
                print(f"- Nome: {COR_DESTAQUE}{INFO_JOGO.get('nome', 'N/A')}{COR_RESET}")
                print(f"- Gênero: {COR_DESTAQUE}{INFO_JOGO.get('genero', 'N/A')}{COR_RESET}")
                # ... (outros campos)
                if INFO_JOGO.get("termos_especificos"): print(f"- Termos: {COR_DESTAQUE}{len(INFO_JOGO['termos_especificos'])} definidos{COR_RESET}")
                time.sleep(2) # Pausa para ver o resumo
                return True
        else:
            mostrar_erro(f"Arquivo de projeto '{arquivo_projeto}' não encontrado.")
            return False
    except Exception as e:
        mostrar_erro(f"Erro ao carregar projeto '{nome_projeto}'", e, context="Carregar Projeto")
        return False

def salvar_projeto(nome_projeto):
    """Salva as informações do contexto atual como um projeto."""
    try:
        diretorio_projeto = os.path.join(PROJECTS_DIR, nome_projeto)
        os.makedirs(diretorio_projeto, exist_ok=True)
        arquivo_projeto = os.path.join(diretorio_projeto, "projeto.json")
        
        dados_projeto = {
            "nome_projeto": nome_projeto,
            "info_jogo": INFO_JOGO,
            "timestamp_criacao": datetime.now().isoformat(),
            "timestamp_atualizacao": datetime.now().isoformat()
        }
        
        # Atualiza timestamp se o arquivo já existe
        if os.path.exists(arquivo_projeto):
             try:
                 with open(arquivo_projeto, 'r', encoding='utf-8') as f:
                     dados_existentes = json.load(f)
                     dados_projeto["timestamp_criacao"] = dados_existentes.get("timestamp_criacao", dados_projeto["timestamp_criacao"])
             except Exception:
                 pass # Ignora erro ao ler arquivo antigo, sobrescreve
                 
        with open(arquivo_projeto, "w", encoding="utf-8") as f:
            json.dump(dados_projeto, f, indent=2)
        mostrar_sucesso(f"Projeto '{nome_projeto}' salvo/atualizado.")
        return True
    except Exception as e:
        mostrar_erro(f"Erro ao salvar projeto '{nome_projeto}'", e, context="Salvar Projeto")
        return False

def listar_projetos():
    """Lista os projetos salvos."""
    projetos = []
    if not os.path.exists(PROJECTS_DIR):
        return projetos
    try:
        for nome in os.listdir(PROJECTS_DIR):
            if os.path.isdir(os.path.join(PROJECTS_DIR, nome)):
                # Verifica se existe o arquivo projeto.json para confirmar que é um projeto válido
                if os.path.exists(os.path.join(PROJECTS_DIR, nome, "projeto.json")):
                    projetos.append(nome)
    except Exception as e:
        mostrar_erro("Erro ao listar projetos.", e, context="Listar Projetos")
    return sorted(projetos)

def selecionar_projeto():
    """Permite ao usuário selecionar um projeto existente ou criar um novo."""
    projetos = listar_projetos()
    
    print(f"\n{COR_SUBTITULO}=== GERENCIAMENTO DE PROJETOS ==={COR_RESET}")
    if projetos:
        print(f"{COR_INFO}Projetos existentes:{COR_RESET}")
        for i, nome in enumerate(projetos):
            print(f"  [{i+1}] {COR_DESTAQUE}{nome}{COR_RESET}")
        print(f"  {COR_PROMPT}[{len(projetos)+1}]{COR_RESET} Criar novo projeto")
        print(f"  {COR_PROMPT}[{len(projetos)+2}]{COR_RESET} Processar arquivo sem projeto")
        print(f"  {COR_PROMPT}[{len(projetos)+3}]{COR_RESET} Voltar")
        max_opcao = len(projetos) + 3
        prompt_escolha = "Escolha um projeto, crie um novo, ou processe sem projeto"
    else:
        print(f"{COR_INFO}Nenhum projeto encontrado.{COR_RESET}")
        print(f"  {COR_PROMPT}[1]{COR_RESET} Criar novo projeto")
        print(f"  {COR_PROMPT}[2]{COR_RESET} Processar arquivo sem projeto")
        print(f"  {COR_PROMPT}[3]{COR_RESET} Voltar")
        max_opcao = 3
        prompt_escolha = "Crie um novo projeto ou processe sem projeto"

    while True:
        escolha_str = obter_entrada(prompt_escolha, [str(i) for i in range(1, max_opcao + 1)], str(max_opcao))
        if not escolha_str: continue
        escolha_idx = int(escolha_str) - 1

        if projetos:
            if 0 <= escolha_idx < len(projetos):
                nome_proj = projetos[escolha_idx]
                if carregar_projeto(nome_proj):
                    return nome_proj # Retorna nome do projeto carregado
                else:
                    continue # Erro ao carregar, pede para escolher de novo
            elif escolha_idx == len(projetos): # Criar novo
                return criar_novo_projeto()
            elif escolha_idx == len(projetos) + 1: # Sem projeto
                mostrar_info("Processando arquivo sem associar a um projeto.")
                # Coleta informações do jogo do zero
                obter_informacoes_jogo()
                return None # Retorna None para indicar sem projeto
            elif escolha_idx == len(projetos) + 2: # Voltar
                return "--voltar--" # Sinaliza para voltar ao menu anterior
        else:
            if escolha_idx == 0: # Criar novo
                return criar_novo_projeto()
            elif escolha_idx == 1: # Sem projeto
                mostrar_info("Processando arquivo sem associar a um projeto.")
                obter_informacoes_jogo()
                return None
            elif escolha_idx == 2: # Voltar
                return "--voltar--"

def criar_novo_projeto():
    """Solicita nome e informações para um novo projeto."""
    while True:
        nome_novo_projeto = obter_entrada("Digite um nome para o novo projeto (sem espaços ou caracteres especiais)")
        if not nome_novo_projeto:
            mostrar_aviso("Nome do projeto não pode ser vazio.")
            continue
        # Validação simples do nome (pode ser melhorada)
        if not re.match(r"^[a-zA-Z0-9_\-]+$", nome_novo_projeto):
            mostrar_erro("Nome inválido. Use apenas letras, números, _ ou -.")
            continue
            
        # Verifica se já existe
        if nome_novo_projeto in listar_projetos():
             resposta_sobrescrever = obter_entrada(f"Projeto '{nome_novo_projeto}' já existe. Deseja sobrescrever/atualizar as informações? (s/n)", validar_sim_nao, "n")
             if resposta_sobrescrever.lower() not in ['s', 'sim']:
                 continue # Pede outro nome
        
        # Coleta informações do jogo para o novo projeto
        obter_informacoes_jogo()
        # Salva o novo projeto
        if salvar_projeto(nome_novo_projeto):
            return nome_novo_projeto # Retorna o nome do projeto criado/atualizado
        else:
            # Se salvar falhar, permite tentar novamente
            resposta_tentar = obter_entrada("Falha ao salvar o projeto. Tentar novamente? (s/n)", validar_sim_nao, "s")
            if resposta_tentar.lower() not in ['s', 'sim']:
                 return None # Desiste de criar projeto
            # Se tentar novamente, o loop while recomeça

# --- Funções Principais de Processamento --- #

def obter_informacoes_jogo():
    """Solicita informações detalhadas sobre o jogo."""
    global INFO_JOGO
    # Reseta INFO_JOGO se estivermos coletando do zero (não carregando de estado/projeto)
    INFO_JOGO = {
        "nome": "", "genero": "", "estilo": "", "tom": "",
        "publico": "", "referencias": "", "termos_especificos": {}
    }
    
    limpar_tela()
    mostrar_banner()
    
    print(f"\n{COR_SUBTITULO}=== INFORMAÇÕES SOBRE O JOGO ==={COR_RESET}")
    print(f"{COR_INFO}Fornecer detalhes sobre o jogo melhora a qualidade da tradução.{COR_RESET}\n")
    
    INFO_JOGO["nome"] = obter_entrada("Nome do jogo")
    if not INFO_JOGO["nome"]:
        mostrar_aviso("Nome do jogo não fornecido. A qualidade pode ser afetada.")
        
    INFO_JOGO["genero"] = obter_entrada("Gênero do jogo", exemplos="RPG, Aventura, FPS, Estratégia, Simulação, Visual Novel")
    INFO_JOGO["estilo"] = obter_entrada("Estilo de escrita predominante", exemplos="Formal, Casual, Humorístico, Sombrio, Épico")
    INFO_JOGO["tom"] = obter_entrada("Tom geral do jogo", exemplos="Sério, Cômico, Misterioso, Dramático")
    INFO_JOGO["publico"] = obter_entrada("Público-alvo", exemplos="Infantil, Adolescente, Adulto, Todas as idades")
    INFO_JOGO["referencias"] = obter_entrada("Referências (jogos, séries, livros PT-BR similares)", exemplos="Final Fantasy VII Remake (PT-BR), The Witcher 3 (PT-BR), Arcane (dublado)")
    
    # Termos específicos
    print(f"\n{COR_SUBTITULO}=== TERMOS ESPECÍFICOS DO JOGO ==={COR_RESET}")
    print(f"{COR_INFO}Adicione termos que devem ser traduzidos/mantidos de forma consistente.{COR_RESET}")
    print(f"{COR_INFO}Ex: Nomes próprios, locais, itens, habilidades.{COR_RESET}")
    print(f"{COR_INFO}Digite 'fim' para terminar.{COR_RESET}\n")
    
    termos_temp = {} # Usar dict temporário para evitar modificar INFO_JOGO diretamente no loop
    while True:
        termo_original = obter_entrada("Termo original (ou 'fim')")
        if not termo_original: continue # Ignora entrada vazia
        if termo_original.lower() == 'fim': break
        termo_traduzido = obter_entrada(f"Tradução/Forma a ser mantida para '{COR_DESTAQUE}{termo_original}{COR_RESET}'")
        termos_temp[termo_original] = termo_traduzido
    INFO_JOGO["termos_especificos"] = termos_temp
    
    mostrar_sucesso("Informações sobre o jogo coletadas!")
    # Mostra resumo...
    print("\nResumo:")
    print(f"- Nome: {COR_DESTAQUE}{INFO_JOGO.get('nome', 'N/A')}{COR_RESET}")
    print(f"- Gênero: {COR_DESTAQUE}{INFO_JOGO.get('genero', 'N/A')}{COR_RESET}")
    print(f"- Estilo: {COR_DESTAQUE}{INFO_JOGO.get('estilo', 'N/A')}{COR_RESET}")
    print(f"- Tom: {COR_DESTAQUE}{INFO_JOGO.get('tom', 'N/A')}{COR_RESET}")
    print(f"- Público: {COR_DESTAQUE}{INFO_JOGO.get('publico', 'N/A')}{COR_RESET}")
    if INFO_JOGO.get("referencias"): print(f"- Referências: {COR_DESTAQUE}{INFO_JOGO['referencias']}{COR_RESET}")
    if INFO_JOGO.get("termos_especificos"): print(f"- Termos: {COR_DESTAQUE}{len(INFO_JOGO['termos_especificos'])} definidos{COR_RESET}")
    
    input(f"\n{COR_PROMPT}Pressione Enter para continuar...{COR_RESET}")

def criar_prompt_traducao(idioma_origem="Inglês", idioma_destino="Português Brasileiro"):
    """Cria o prompt base para a tradução, incluindo contexto do jogo."""
    prompt = f"""Você é um tradutor especializado em textos de jogos do {idioma_origem} para o {idioma_destino}.
OBJETIVO: Traduzir o texto a seguir, mantendo o significado original, adaptando culturalmente para jogadores brasileiros e preservando a formatação e códigos internos.
REGRAS FUNDAMENTAIS:
1. PRESERVE A FORMATAÇÃO EXATA: Mantenha EXATAMENTE as mesmas quebras de linha, espaços iniciais/finais e estrutura do texto original.
2. NÃO MODIFIQUE MARCADORES: Os marcadores [[número]] representam códigos internos do jogo (como <tags> ou {{variáveis}}). Deixe-os EXATAMENTE como estão no texto original, sem adicionar espaços antes ou depois deles.
3. TRADUZA O TEXTO AO REDOR DOS MARCADORES: Traduza o texto que aparece antes, depois ou entre os marcadores [[número]] para o {idioma_destino}.
4. CONTEXTO DO JOGO: Adapte a tradução ao gênero, estilo, tom e público do jogo, conforme informações abaixo.
5. REFERÊNCIAS CULTURAIS PT-BR: Use equivalentes culturais brasileiros para piadas, expressões idiomáticas e referências, buscando inspiração em dublagens e traduções PT-BR de obras similares (listadas abaixo).
6. TERMOS ESPECÍFICOS: Use as traduções fornecidas para os termos específicos do jogo (listados abaixo).
7. NATURALIDADE: Priorize uma tradução que soe natural em {idioma_destino}.\n"""
    # Adiciona contexto do jogo ao prompt
    contexto_str = "\n--- CONTEXTO DO JOGO ---\n"
    contexto_adicionado = False
    if INFO_JOGO.get("nome"): contexto_str += f"- Nome: {INFO_JOGO['nome']}\n"; contexto_adicionado = True
    if INFO_JOGO.get("genero"): contexto_str += f"- Gênero: {INFO_JOGO['genero']}\n"; contexto_adicionado = True
    if INFO_JOGO.get("estilo"): contexto_str += f"- Estilo de Escrita Original: {INFO_JOGO['estilo']}\n"; contexto_adicionado = True
    if INFO_JOGO.get("tom"): contexto_str += f"- Tom Geral: {INFO_JOGO['tom']}\n"; contexto_adicionado = True
    if INFO_JOGO.get("publico"): contexto_str += f"- Público-Alvo: {INFO_JOGO['publico']}\n"; contexto_adicionado = True
    if INFO_JOGO.get("referencias"): contexto_str += f"- Referências PT-BR: {INFO_JOGO['referencias']}\n"; contexto_adicionado = True
    if INFO_JOGO.get("termos_especificos"):
        contexto_str += "- Termos Específicos (Original -> Tradução PT-BR):\n"
        for t_orig, t_trad in INFO_JOGO["termos_especificos"].items():
            contexto_str += f"  - '{t_orig}' -> '{t_trad}'\n"
        contexto_adicionado = True
        
    if contexto_adicionado:
        prompt += contexto_str
    else:
        prompt += "\n(Nenhum contexto adicional fornecido sobre o jogo.)\n"
        
    prompt += "\n--- TEXTO PARA TRADUZIR ---"
    # O texto real será adicionado depois
    return prompt

def traduzir_arquivo(
    arquivo_entrada,
    arquivo_saida=None,
    idioma_origem="Inglês",
    idioma_destino="Português Brasileiro",
    max_tokens_bloco=None,
    delay=DEFAULT_DELAY,
    delay_mode='fixo',
    modelo_gemini=None,
    continuar_de=None,
    projeto_nome=None
):
# Função principal para traduzir um arquivo.
    global INTERRUPTED, PAUSED, CACHE_FRASES
    INTERRUPTED = False
    PAUSED = False
    CACHE_FRASES = {} # Limpa cache para cada novo processo

    try:
        with open(arquivo_entrada, 'r', encoding='utf-8') as f:
            linhas = f.readlines()
    except FileNotFoundError:
        mostrar_erro(f"Arquivo de entrada '{arquivo_entrada}' não encontrado.")
        return
    except Exception as e:
        mostrar_erro(f"Erro ao ler arquivo de entrada '{arquivo_entrada}'.", e, context="Ler Arquivo Entrada")
        return

    if not arquivo_saida:
        base, ext = os.path.splitext(arquivo_entrada)
        arquivo_saida = f"{base}_traduzido{ext}"
        mostrar_info(f"Arquivo de saída não especificado, usando: {arquivo_saida}")

    # Cria diretório de saída se não existir
    try:
        os.makedirs(os.path.dirname(arquivo_saida) or ".", exist_ok=True)
    except Exception as e:
        mostrar_erro(f"Erro ao criar diretório de saída para '{arquivo_saida}'.", e, context="Criar Diretório Saída")
        return

    # Configurações de bloco e delay
    tamanho_arquivo = os.path.getsize(arquivo_entrada)
    num_linhas_total = len(linhas)
    if max_tokens_bloco is None:
        max_tokens_bloco = calcular_tamanho_bloco_adaptativo(tamanho_arquivo, num_linhas_total)
        mostrar_info(f"Usando tamanho de bloco adaptativo: {max_tokens_bloco} tokens.")
    else:
         mostrar_info(f"Usando tamanho de bloco fixo: {max_tokens_bloco} tokens.")

    if delay_mode == 'adaptativo':
        # O delay adaptativo real será calculado por bloco
        mostrar_info("Usando delay adaptativo entre blocos.")
    else:
        mostrar_info(f"Usando delay fixo: {delay:.2f}s entre blocos.")

    # Gerenciamento de Estado
    linha_inicial = 0
    blocos_processados_antes = 0
    linhas_traduzidas_buffer = {}
    arquivo_estado = None

    if continuar_de:
        estado_path, estado = selecionar_estado_para_continuar()
        if estado:
            # Verifica compatibilidade básica
            if (estado.get("arquivo_entrada") != os.path.abspath(arquivo_entrada) or 
               estado.get("tipo_processo") != "traducao"):
                mostrar_erro("Estado selecionado não corresponde a este arquivo/processo. Iniciando do zero.")
            else:
                arquivo_estado = estado_path
                linha_inicial = estado.get("ultima_linha_processada", -1) + 1
                blocos_processados_antes = estado.get("blocos_processados", 0)
                # Carrega INFO_JOGO do estado (já feito em selecionar_estado_para_continuar)
                # Carrega traduções já feitas se o arquivo de saída existe
                if os.path.exists(arquivo_saida):
                    try:
                        with open(arquivo_saida, 'r', encoding='utf-8') as f_out:
                            linhas_out = f_out.readlines()
                        # Assume que as linhas no arquivo de saída correspondem às linhas processadas
                        # Armazena no buffer para escrita posterior
                        for i in range(min(linha_inicial, len(linhas_out))):
                            linhas_traduzidas_buffer[i] = linhas_out[i]
                        mostrar_info(f"Continuando da linha {linha_inicial + 1}. {len(linhas_traduzidas_buffer)} linhas carregadas do arquivo de saída existente.")
                    except Exception as e:
                        mostrar_erro("Erro ao ler arquivo de saída existente para continuar. Reiniciando do zero.", e, context="Continuar - Ler Saída")
                        linha_inicial = 0
                        blocos_processados_antes = 0
                        linhas_traduzidas_buffer = {}
                        arquivo_estado = None # Reseta estado se não puder ler saída
                else:
                     mostrar_info(f"Continuando da linha {linha_inicial + 1}. Arquivo de saída não encontrado, será criado.")
        else:
             mostrar_info("Nenhum estado válido selecionado. Iniciando do zero.")

    # Cria arquivo de estado se não estiver continuando ou se falhou ao carregar
    if not arquivo_estado:
        arquivo_estado = criar_arquivo_estado(arquivo_entrada, arquivo_saida, "traducao", projeto_nome,
                                              idioma_origem=idioma_origem, idioma_destino=idioma_destino)
        # Abre o arquivo de saída no modo 'w' para começar do zero
        try:
            with open(arquivo_saida, 'w', encoding='utf-8') as f_out:
                pass # Apenas cria/limpa o arquivo
            mostrar_info(f"Criando/Recriando arquivo de saída: {arquivo_saida}")
        except Exception as e:
            mostrar_erro(f"Não foi possível criar/limpar o arquivo de saída '{arquivo_saida}'.", e, context="Criar Arquivo Saída")
            return

    # Agrupa as linhas restantes
    linhas_para_processar = linhas[linha_inicial:]
    blocos = agrupar_linhas_para_processamento(linhas_para_processar, max_tokens_bloco)
    total_blocos_atuais = len(blocos)
    total_blocos_geral = blocos_processados_antes + total_blocos_atuais

    # Atualiza o total de blocos no arquivo de estado
    atualizar_arquivo_estado(arquivo_estado, linha_inicial -1, blocos_processados_antes, total_blocos_geral)

    mostrar_info(f"Total de blocos a processar nesta execução: {total_blocos_atuais}")
    print(f"\n{COR_SUBTITULO}=== INICIANDO TRADUÇÃO ({idioma_origem} -> {idioma_destino}) ==={COR_RESET}")

    prompt_base = criar_prompt_traducao(idioma_origem, idioma_destino)
    
    # Configura barra de progresso se tqdm estiver disponível
    pbar_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
    pbar = tqdm(total=total_blocos_atuais, unit="bloco", desc="Traduzindo", bar_format=pbar_format, initial=0) if tqdm else None
    tokens_processados_total = 0
    tempo_inicio_total = time.time()

    try:
        # Abre o arquivo de saída no modo append ('a') para adicionar novas linhas
        with open(arquivo_saida, 'a', encoding='utf-8') as f_out:
            # Escreve linhas carregadas do buffer (se estiver continuando)
            if linhas_traduzidas_buffer:
                 mostrar_info("Restaurando linhas já processadas...")
                 for i in sorted(linhas_traduzidas_buffer.keys()):
                     # Garante que a linha termine com quebra de linha
                     linha_out = linhas_traduzidas_buffer[i].rstrip("\n") + "\n"
                     f_out.write(linha_out)
                 f_out.flush()

            for i, bloco in enumerate(blocos):
                if INTERRUPTED or PAUSED:
                    break

                texto_bloco_original = bloco["texto_para_processar"]
                indices_linhas_bloco = bloco["indices_linhas"]
                # Ajusta índices para serem relativos ao arquivo original
                indices_reais = [idx + linha_inicial for idx in indices_linhas_bloco]
                ultima_linha_bloco = indices_reais[-1]

                texto_bloco_traduzido = None
                tokens_bloco = 0
                tempo_inicio_bloco = time.time()

                if texto_bloco_original is not None:
                    # Verifica cache antes de chamar API
                    if texto_bloco_original in CACHE_FRASES:
                        texto_bloco_traduzido = CACHE_FRASES[texto_bloco_original]
                        if pbar: pbar.set_postfix_str("Cache hit", refresh=True)
                    else:
                        if pbar: pbar.set_postfix_str("API call", refresh=True)
                        try:
                            texto_bloco_traduzido = processar_texto_com_gemini(modelo_gemini, texto_bloco_original, prompt_base)
                            # Adiciona ao cache se a tradução foi bem sucedida
                            if texto_bloco_traduzido != texto_bloco_original: # Evita cache se pulou bloco
                                CACHE_FRASES[texto_bloco_original] = texto_bloco_traduzido
                        except KeyboardInterrupt:
                            INTERRUPTED = True
                            mostrar_aviso("\nInterrupção detectada. Salvando progresso...")
                            break
                        except Exception as e:
                            # Erros críticos (sem chaves, etc.) ou pausa do usuário já levantam exceção
                            # Se chegou aqui, pode ser um erro que permitiu pular o bloco
                            mostrar_erro(f"Erro ao processar bloco {i+1} (linhas {indices_reais[0]+1}-{ultima_linha_bloco+1}). Bloco será pulado.", e, context="Loop Principal - Processar Bloco")
                            texto_bloco_traduzido = texto_bloco_original # Mantém original se falhou
                    
                    tokens_bloco = contar_tokens(texto_bloco_original)
                    tokens_processados_total += tokens_bloco
                else:
                    # Bloco não processável (linha vazia, ignorada, etc.)
                    texto_bloco_traduzido = bloco["linha_original"].rstrip("\n")
                    if pbar: pbar.set_postfix_str("Ignorado", refresh=True)

                # Escreve o resultado no arquivo (mesmo se for o original em caso de erro/skip)
                # Garante que termine com uma única quebra de linha
                linha_out = texto_bloco_traduzido.rstrip("\n") + "\n"
                f_out.write(linha_out)
                f_out.flush() # Garante que seja escrito imediatamente

                # Atualiza estado
                blocos_processados_atuais = i + 1
                atualizar_arquivo_estado(arquivo_estado, ultima_linha_bloco, blocos_processados_antes + blocos_processados_atuais, total_blocos_geral)

                # Calcula e aplica delay
                delay_atual = 0
                if i < total_blocos_atuais - 1: # Não aplica delay após o último bloco
                    if delay_mode == 'adaptativo':
                        delay_atual = calcular_delay_adaptativo(tamanho_arquivo, tokens_bloco)
                    else:
                        delay_atual = delay
                    
                    if delay_atual > 0.1:
                        # Pausa curta para permitir interrupção
                        try:
                            if pbar: pbar.set_postfix_str(f"Delay {delay_atual:.1f}s", refresh=True)
                            time.sleep(delay_atual)
                        except KeyboardInterrupt:
                            INTERRUPTED = True
                            mostrar_aviso("\nInterrupção detectada durante delay. Salvando progresso...")
                            break
                
                # Atualiza barra de progresso
                if pbar:
                    tempo_decorrido_total = time.time() - tempo_inicio_total
                    tokens_por_segundo = tokens_processados_total / tempo_decorrido_total if tempo_decorrido_total > 0 else 0
                    pbar.set_postfix_str(f"{tokens_por_segundo:.1f} t/s", refresh=True)
                    pbar.update(1)

    except Exception as e:
        # Captura erros inesperados fora do loop de blocos
        mostrar_erro("Erro inesperado durante o processo de tradução.", e, context="Loop Principal - Erro Externo")
        INTERRUPTED = True # Marca como interrompido para indicar falha

    finally:
        if pbar:
            pbar.close()
        
        # Mensagem final
        if INTERRUPTED:
            mostrar_aviso(f"Tradução INTERROMPIDA na linha {ultima_linha_bloco + 1}. Progresso salvo.")
            atualizar_arquivo_estado(arquivo_estado, ultima_linha_bloco, blocos_processados_antes + blocos_processados_atuais, total_blocos_geral, concluido=False)
        elif PAUSED:
             mostrar_aviso(f"Tradução PAUSADA na linha {ultima_linha_bloco + 1}. Progresso salvo. Use a opção 'Continuar' para retomar.")
             atualizar_arquivo_estado(arquivo_estado, ultima_linha_bloco, blocos_processados_antes + blocos_processados_atuais, total_blocos_geral, concluido=False)
        else:
            mostrar_sucesso(f"Tradução concluída! Arquivo salvo em: {arquivo_saida}")
            atualizar_arquivo_estado(arquivo_estado, num_linhas_total - 1, total_blocos_geral, total_blocos_geral, concluido=True)
            # Opcional: Remover arquivo de estado após conclusão bem-sucedida?
            # try:
            #     os.remove(arquivo_estado)
            # except Exception as e:
            #     mostrar_aviso(f"Não foi possível remover o arquivo de estado {arquivo_estado}: {e}")

        input(f"\n{COR_PROMPT}Pressione Enter para voltar ao menu...{COR_RESET}")

# --- Funções de Interface e Menu --- #

def menu_principal():
# Exibe o menu principal e gerencia as opções.
    carregar_config()
    modelo_gemini = None # Será configurado quando necessário
    
    while True:
        limpar_tela()
        mostrar_banner()
        print(f"\n{COR_SUBTITULO}=== MENU PRINCIPAL ==={COR_RESET}")
        print(f"  {COR_PROMPT}[1]{COR_RESET} Traduzir novo arquivo")
        print(f"  {COR_PROMPT}[2]{COR_RESET} Continuar tradução anterior")
        print(f"  {COR_PROMPT}[3]{COR_RESET} Gerenciar Chaves de API")
        print(f"  {COR_PROMPT}[4]{COR_RESET} Gerenciar Projetos") # Nova opção
        print(f"  {COR_PROMPT}[5]{COR_RESET} Sobre")
        print(f"  {COR_PROMPT}[6]{COR_RESET} Sair")

        escolha = obter_entrada("Escolha uma opção", validar_opcao_menu(["1", "2", "3", "4", "5", "6"]), "1")

        if escolha == "1":
            # Selecionar/Criar Projeto
            nome_projeto = selecionar_projeto()
            if nome_projeto == "--voltar--": continue
            # Se nome_projeto for None, significa que o usuário escolheu processar sem projeto
            # e as informações já foram coletadas por obter_informacoes_jogo().
            # Se nome_projeto tiver um valor, o projeto foi carregado e INFO_JOGO atualizado.
            
            # Configurações da Tradução
            arquivo_in = obter_entrada("Arquivo original a traduzir")
            if not arquivo_in or not os.path.exists(arquivo_in):
                mostrar_erro(f"Arquivo '{arquivo_in}' não encontrado.")
                time.sleep(2)
                continue
                
            idioma_orig = obter_entrada("Idioma de origem", padrao="Inglês")
            idioma_dest = obter_entrada("Idioma de destino", padrao="Português Brasileiro")
            arquivo_out_base, ext = os.path.splitext(os.path.basename(arquivo_in))
            arquivo_out_sug = f"{arquivo_out_base}_traduzido{ext}"
            arquivo_out = obter_entrada("Arquivo de saída", padrao=arquivo_out_sug)

            # Configurar API Key e Modelo
            if not API_KEYS:
                mostrar_aviso("Nenhuma chave de API salva. Você precisará digitar uma.")
                nova_chave = obter_entrada("Digite sua chave de API do Google (Gemini)")
                if nova_chave:
                    API_KEYS.append(nova_chave)
                    salvar_config()
                    CURRENT_API_KEY_INDEX = len(API_KEYS) - 1
                else:
                    mostrar_erro("Nenhuma chave de API fornecida. Não é possível continuar.")
                    time.sleep(2)
                    continue
            elif len(API_KEYS) > 1:
                print(f"{COR_INFO}Chaves de API disponíveis:{COR_RESET}")
                for i, key in enumerate(API_KEYS):
                    print(f"  [{i+1}] {key[:4]}...{key[-4:]}")
                indice_str = obter_entrada("Escolha a chave a usar", [str(i) for i in range(1, len(API_KEYS) + 1)], "1")
                CURRENT_API_KEY_INDEX = int(indice_str) - 1
            else:
                 CURRENT_API_KEY_INDEX = 0 # Usa a única chave disponível
                 
            modelo_nome_escolhido = DEFAULT_MODEL
            usar_pro = obter_entrada("Usar modelo Gemini Pro (mais lento/caro, melhor qualidade)? (s/n)", validar_sim_nao, "n")
            if usar_pro.lower() in ['s', 'sim']:
                modelo_nome_escolhido = PRO_MODEL
                
            modelo_gemini = configurar_gemini_com_fallback(API_KEYS[CURRENT_API_KEY_INDEX], modelo_nome_escolhido)
            if not modelo_gemini:
                # Erro já foi mostrado por configurar_gemini_com_fallback
                time.sleep(3)
                continue

            # Configurar Delay
            delay_mode = obter_entrada("Usar delay adaptativo ou fixo (3.0s)? (adaptativo/fixo)", ["adaptativo", "fixo"], "fixo")
            delay_valor = DEFAULT_DELAY
            if delay_mode == 'fixo':
                try:
                    delay_str = obter_entrada(f"Digite o valor do delay fixo em segundos", padrao=str(DEFAULT_DELAY))
                    delay_valor = float(delay_str)
                    if delay_valor < 0:
                         mostrar_aviso("Delay não pode ser negativo. Usando 0."); delay_valor = 0
                except ValueError:
                    mostrar_erro("Valor de delay inválido. Usando padrão 3.0s.")
                    delay_valor = DEFAULT_DELAY
            
            # Iniciar Tradução
            traduzir_arquivo(arquivo_in, arquivo_out, idioma_orig, idioma_dest,
                             delay=delay_valor, delay_mode=delay_mode, modelo_gemini=modelo_gemini,
                             projeto_nome=nome_projeto)

        elif escolha == "2":
            estado_path, estado = selecionar_estado_para_continuar()
            if estado:
                # Carrega configurações do estado
                arquivo_in = estado.get("arquivo_entrada")
                arquivo_out = estado.get("arquivo_saida")
                idioma_orig = estado.get("idioma_origem", "Inglês")
                idioma_dest = estado.get("idioma_destino", "Português Brasileiro")
                nome_projeto = estado.get("projeto_nome")
                # INFO_JOGO já carregado por selecionar_estado_para_continuar
                
                # Tenta configurar API e Modelo (pode precisar selecionar chave se houver várias)
                if not API_KEYS:
                     mostrar_erro("Nenhuma chave de API salva. Adicione uma chave antes de continuar.")
                     time.sleep(2); continue
                elif len(API_KEYS) > 1:
                    print(f"{COR_INFO}Chaves de API disponíveis:{COR_RESET}")
                    for i, key in enumerate(API_KEYS):
                        print(f"  [{i+1}] {key[:4]}...{key[-4:]}")
                    indice_str = obter_entrada("Escolha a chave a usar para continuar", [str(i) for i in range(1, len(API_KEYS) + 1)], "1")
                    CURRENT_API_KEY_INDEX = int(indice_str) - 1
                else:
                    CURRENT_API_KEY_INDEX = 0
                
                # Assume o modelo usado anteriormente se não estiver no estado (melhorar: salvar modelo no estado)
                modelo_nome_escolhido = DEFAULT_MODEL # Ou carregar do estado se salvo
                modelo_gemini = configurar_gemini_com_fallback(API_KEYS[CURRENT_API_KEY_INDEX], modelo_nome_escolhido)
                if not modelo_gemini:
                    time.sleep(3); continue
                    
                # Delay e Max Tokens (carregar do estado se salvos, senão usar padrão/adaptativo)
                delay_mode = estado.get("delay_mode", "fixo")
                delay_valor = estado.get("delay", DEFAULT_DELAY)
                max_tokens = estado.get("max_tokens_bloco") # None para adaptativo

                mostrar_info(f"Continuando tradução de '{os.path.basename(arquivo_in)}'...")
                traduzir_arquivo(arquivo_in, arquivo_out, idioma_orig, idioma_dest,
                                 max_tokens_bloco=max_tokens, delay=delay_valor, delay_mode=delay_mode,
                                 modelo_gemini=modelo_gemini, continuar_de=estado_path, # Passa o path do estado
                                 projeto_nome=nome_projeto)
            else:
                 # Usuário escolheu voltar ou nenhum estado válido
                 pass 

        elif escolha == "3":
            gerenciar_api_keys()
            
        elif escolha == "4":
            # Menu Gerenciar Projetos (Simplificado por enquanto)
            while True:
                limpar_tela()
                mostrar_banner()
                print(f"\n{COR_SUBTITULO}=== GERENCIAR PROJETOS ==={COR_RESET}")
                projetos = listar_projetos()
                if projetos:
                    print(f"{COR_INFO}Projetos existentes:{COR_RESET}")
                    for i, nome in enumerate(projetos):
                        print(f"  [{i+1}] {COR_DESTAQUE}{nome}{COR_RESET}")
                    print(f"\n  {COR_PROMPT}[{len(projetos)+1}]{COR_RESET} Criar novo projeto")
                    print(f"  {COR_PROMPT}[{len(projetos)+2}]{COR_RESET} Excluir projeto")
                    print(f"  {COR_PROMPT}[{len(projetos)+3}]{COR_RESET} Voltar")
                    max_opcao_proj = len(projetos) + 3
                else:
                    print(f"{COR_INFO}Nenhum projeto encontrado.{COR_RESET}")
                    print(f"\n  {COR_PROMPT}[1]{COR_RESET} Criar novo projeto")
                    print(f"  {COR_PROMPT}[2]{COR_RESET} Voltar")
                    max_opcao_proj = 2
                
                escolha_proj_str = obter_entrada("Escolha uma opção", [str(i) for i in range(1, max_opcao_proj + 1)], str(max_opcao_proj))
                if not escolha_proj_str: continue
                escolha_proj_idx = int(escolha_proj_str) - 1
                
                if projetos:
                    if 0 <= escolha_proj_idx < len(projetos):
                         mostrar_info(f"Carregando projeto '{projetos[escolha_proj_idx]}' para visualização/edição (funcionalidade futura). Por enquanto, apenas lista.")
                         # Futuro: Opção para editar informações do projeto
                         time.sleep(2)
                    elif escolha_proj_idx == len(projetos): # Criar novo
                        criar_novo_projeto()
                        time.sleep(1.5) # Pausa após criar
                    elif escolha_proj_idx == len(projetos) + 1: # Excluir
                        if not projetos: continue # Nao deveria acontecer
                        print("\nSelecione o projeto a excluir:")
                        for i, nome in enumerate(projetos):
                            print(f"  [{i+1}] {nome}")
                        print(f"  [{len(projetos)+1}] Cancelar")
                        escolha_excluir_str = obter_entrada("Projeto a excluir", [str(i) for i in range(1, len(projetos)+2)], str(len(projetos)+1))
                        if escolha_excluir_str:
                             escolha_excluir_idx = int(escolha_excluir_str) - 1
                             if 0 <= escolha_excluir_idx < len(projetos):
                                 nome_excluir = projetos[escolha_excluir_idx]
                                 confirmar = obter_entrada(f"Tem certeza que deseja excluir o projeto '{nome_excluir}' e TODOS os seus arquivos de estado? (s/n)", validar_sim_nao, "n")
                                 if confirmar.lower() in ['s', 'sim']:
                                     try:
                                         import shutil
                                         shutil.rmtree(os.path.join(PROJECTS_DIR, nome_excluir))
                                         mostrar_sucesso(f"Projeto '{nome_excluir}' excluído.")
                                     except Exception as e:
                                         mostrar_erro(f"Erro ao excluir projeto '{nome_excluir}'.", e, context="Excluir Projeto")
                                     time.sleep(2)
                    elif escolha_proj_idx == len(projetos) + 2: # Voltar
                        break
                else: # Sem projetos existentes
                     if escolha_proj_idx == 0: # Criar novo
                         criar_novo_projeto()
                         time.sleep(1.5)
                     elif escolha_proj_idx == 1: # Voltar
                         break

        elif escolha == "5":
            limpar_tela()
            mostrar_banner()
            print(f"\n{COR_SUBTITULO}=== SOBRE ==={COR_RESET}")
            print("Script para tradução de arquivos de texto de jogos usando Google Gemini.")
            print("Versão: 7.0")
            print("Desenvolvido com auxílio de IA.")
            print(f"\n{COR_INFO}Funcionalidades:{COR_RESET}")
            print("- Tradução via API Gemini (Flash/Pro)")
            print("- Gerenciamento de chaves API e fallback")
            print("- Preservação de códigos <tag> e {chaves}")
            print("- Ignora linhas iniciadas com ¬")
            print("- Cache para frases repetidas")
            print("- Gerenciamento de Projetos (contexto)")
            print("- Retoma processos interrompidos")
            print("- Otimização para arquivos grandes")
            print("- Delay configurável")
            print("- Interface interativa / Linha de comando")
            print("- Tratamento de erro API melhorado com log")
            input(f"\n{COR_PROMPT}Pressione Enter para voltar...{COR_RESET}")

        elif escolha == "6":
            mostrar_info("Saindo...")
            break

# --- Execução Principal --- #

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Super Tradutor de Jogos v7 usando Google Gemini.")
    parser.add_argument("arquivo", nargs='?', help="Arquivo de texto original a ser traduzido.")
    parser.add_argument("-o", "--output", help="Arquivo de saída para a tradução.")
    parser.add_argument("-s", "--source-lang", default="Inglês", help="Idioma de origem (padrão: Inglês)")
    parser.add_argument("-d", "--dest-lang", default="Português Brasileiro", help="Idioma de destino (padrão: Português Brasileiro)")
    parser.add_argument("-t", "--delay", type=float, default=DEFAULT_DELAY, help=f"Delay fixo em segundos entre chamadas de API (padrão: {DEFAULT_DELAY})")
    parser.add_argument("--delay-mode", choices=['fixo', 'adaptativo'], default='fixo', help="Modo de delay: 'fixo' ou 'adaptativo' (padrão: fixo)")
    parser.add_argument("-m", "--max-tokens", type=int, help="Máximo de tokens por bloco (padrão: adaptativo)")
    parser.add_argument("-k", "--api-key-index", type=int, default=1, help="Índice (começando em 1) da chave de API salva a usar.")
    parser.add_argument("-p", "--pro", action="store_true", help="Usar modelo Gemini Pro (melhor qualidade, mais lento/caro). Padrão: Gemini Flash.")
    parser.add_argument("-c", "--continuar", action="store_true", help="Tentar continuar um processo anterior para o arquivo de entrada/saída.")
    parser.add_argument("-i", "--interface", action="store_true", help="Forçar modo interativo (ignora outros argumentos exceto -c).")
    parser.add_argument("--projeto", help="Nome do projeto para carregar/associar.")

    args = parser.parse_args()

    carregar_config() # Carrega chaves API

    if not args.arquivo or args.interface:
        # Entra no modo interativo se nenhum arquivo for fornecido ou -i for usado
        menu_principal()
    else:
        # Modo linha de comando
        if not os.path.exists(args.arquivo):
            mostrar_erro(f"Arquivo de entrada '{args.arquivo}' não encontrado.")
            sys.exit(1)

        # Carrega projeto se especificado
        nome_projeto_cli = args.projeto
        if nome_projeto_cli:
            if not carregar_projeto(nome_projeto_cli):
                 # Tenta criar se não existir?
                 confirmar_criar = obter_entrada(f"Projeto '{nome_projeto_cli}' não encontrado. Deseja criá-lo agora? (s/n)", validar_sim_nao, "s")
                 if confirmar_criar.lower() in ['s', 'sim']:
                     obter_informacoes_jogo() # Coleta info
                     if not salvar_projeto(nome_projeto_cli):
                         mostrar_erro("Falha ao criar projeto. Saindo."); sys.exit(1)
                 else:
                     mostrar_erro("Projeto não carregado. Saindo."); sys.exit(1)
        else:
            # Se não especificou projeto, coleta info (a menos que esteja continuando)
            if not args.continuar:
                 obter_informacoes_jogo()
            # Se estiver continuando, as infos serão carregadas do estado

        # Configura API Key
        if not API_KEYS:
            mostrar_erro("Nenhuma chave de API salva. Use o modo interativo para adicionar uma.")
            sys.exit(1)
        if not (1 <= args.api_key_index <= len(API_KEYS)):
            mostrar_erro(f"Índice de chave API inválido: {args.api_key_index}. Válido: 1-{len(API_KEYS)}.")
            sys.exit(1)
        CURRENT_API_KEY_INDEX = args.api_key_index - 1

        # Configura Modelo
        modelo_nome = PRO_MODEL if args.pro else DEFAULT_MODEL
        modelo_g = configurar_gemini_com_fallback(API_KEYS[CURRENT_API_KEY_INDEX], modelo_nome)
        if not modelo_g:
            sys.exit(1)

        # Define arquivo de saída padrão se não fornecido
        arquivo_saida_cli = args.output
        if not arquivo_saida_cli:
            base, ext = os.path.splitext(args.arquivo)
            arquivo_saida_cli = f"{base}_traduzido{ext}"

        # Encontra estado para continuar, se solicitado
        estado_path_cli = None
        if args.continuar:
            estados_possiveis = listar_estados_salvos()
            for p in estados_possiveis:
                try:
                    with open(p, 'r', encoding='utf-8') as f_st:
                        st = json.load(f_st)
                    # Compara caminhos absolutos
                    if st.get("arquivo_entrada") == os.path.abspath(args.arquivo) and \
                       st.get("arquivo_saida") == os.path.abspath(arquivo_saida_cli) and \
                       st.get("tipo_processo") == "traducao" and \
                       not st.get("concluido", False):
                        estado_path_cli = p
                        mostrar_info(f"Encontrado estado anterior para continuar: {p}")
                        # Carrega INFO_JOGO do estado encontrado
                        if "info_jogo" in st:

                            INFO_JOGO = st["info_jogo"]
                            mostrar_info("Contexto do jogo carregado do estado.")
                        break # Usa o primeiro estado compatível encontrado
                except Exception:
                    continue # Ignora estados inválidos
            if not estado_path_cli:
                mostrar_aviso("Nenhum estado anterior compatível encontrado para continuar. Iniciando do zero.")

        # Executa a tradução
        traduzir_arquivo(
            args.arquivo,
            arquivo_saida_cli,
            args.source_lang,
            args.dest_lang,
            args.max_tokens,
            args.delay,
            args.delay_mode,
            modelo_g,
            continuar_de=estado_path_cli,
            projeto_nome=nome_projeto_cli
        )

