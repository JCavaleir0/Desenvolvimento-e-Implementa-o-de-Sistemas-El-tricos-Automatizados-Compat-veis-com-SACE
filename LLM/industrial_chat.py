import json
import requests
from datetime import datetime, date


# =========================
# CONFIG
# =========================

OLLAMA_URL = "http://localhost:11434/api/generate"

MODEL = "qwen2.5:14b"


#MODEL = "llama3.1:8b"

RESULTADOS_FILE = "resultados.json"


# =========================
# NOMES EQUIPAMENTOS
# =========================

NOMES_EQUIPAMENTOS = {

    "Escadas": {
        "nome": "Stairs",
        "aliases": [
            "stairs", "escadas", "escada", "stair",
            "escadas principais", "main stairs"
        ]
    },

    "Luz2": {
        "nome": "Living room",
        "aliases": [
            "living room", "living", "sala", "sala de estar", "estar",
            "livingroom", "room 1", "sala principal", "main room",
            "main living room", "zona de estar", "zona principal"
        ]
    },

    "Luz3": {
        "nome": "Kitchen",
        "aliases": [
            "kitchen", "cozinha", "cook room", "cooking room",
            "food room", "meal room", "zona de cozinha"
        ]
    },

    "Luz4": {
        "nome": "Living Area",
        "aliases": [
            "living area", "hall", "zona de estar", "hall area",
            "open area", "common area", "area comum", "zona comum"
        ]
    },

    "Luz5": {
        "nome": "Machinery Room",
        "aliases": [
            "machinery room", "machine room", "engine room",
            "sala das maquinas", "sala de maquinas", "technical room",
            "maintenance room", "motor room", "equipment room", "utility room"
        ]
    },

    "Luz6": {
        "nome": "Bathroom 0",
        "aliases": [
            "bathroom 0", "bathroom", "wc", "casa de banho",
            "toilet", "lavatory", "washroom", "restroom",
            "banheiro", "bath"
        ]
    },

    "Luz7": {
        "nome": "Garage",
        "aliases": [
            "garage", "garagem", "car room",
            "parking", "car park", "vehicle room"
        ]
    },

    "Luz8": {
        "nome": "Bedroom 1",
        "aliases": [
            "bedroom 1", "quarto 1", "room 1",
            "master bedroom", "bedroom",
            "sleep room", "main bedroom"
        ]
    },

    "Luz9": {
        "nome": "Bedroom 2",
        "aliases": [
            "bedroom 2", "quarto 2", "room 2",
            "second bedroom", "guest room", "sleep room 2"
        ]
    },

    "Luz10": {
        "nome": "Bedroom 3",
        "aliases": [
            "bedroom 3", "quarto 3", "room 3",
            "third bedroom", "extra bedroom", "secondary room"
        ]
    },

    "Luz11": {
        "nome": "Bathroom 1",
        "aliases": [
            "bathroom 1", "wc 1", "casa de banho 1",
            "toilet 1", "washroom 1", "restroom 1", "guest bathroom"
        ]
    },

    "Luz12": {
        "nome": "Hallway",
        "aliases": [
            "hallway", "hall", "corredor",
            "passage", "corridor",
            "entry hall", "entrance hall"
        ]
    }
}


# =========================
# UTILITÁRIOS
# =========================

def carregar_resultados():
    try:
        with open(RESULTADOS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"Erro ao carregar resultados: {exc}")
        return {}


def nome_amigavel(sensor):
    return NOMES_EQUIPAMENTOS.get(
        sensor,
        {}
    ).get(
        "nome",
        sensor
    )


def detectar_equipamento(pergunta):
    pergunta = normalizar_texto(pergunta)

    todos_aliases = []

    for equipamento, info in NOMES_EQUIPAMENTOS.items():
        todos_aliases.append(
            (normalizar_texto(equipamento), equipamento)
        )

        todos_aliases.append(
            (normalizar_texto(info["nome"]), equipamento)
        )

        for alias in info["aliases"]:
            todos_aliases.append(
                (normalizar_texto(alias), equipamento)
            )

    todos_aliases.sort(
        key=lambda x: len(x[0]),
        reverse=True
    )

    for alias, equipamento in todos_aliases:
        if alias in pergunta:
            return equipamento

    return None


def obter_lista_iluminacao(dados):
    if isinstance(dados, dict):
        return dados.get("iluminacao", [])

    if isinstance(dados, list):
        return dados

    return []


def obter_motores(dados):
    if isinstance(dados, dict):
        return dados.get("motores", [])

    return []


def obter_bombas(dados):
    if isinstance(dados, dict):
        return dados.get("bombas", [])

    return []


def normalizar_numero(valor, default=0):
    try:
        if valor is None:
            return default
        return float(valor)
    except Exception:
        return default


def formatar_minutos(minutos):
    minutos = normalizar_numero(minutos, 0)

    horas = int(minutos // 60)
    mins = int(round(minutos % 60))

    if horas > 0:
        return f"{horas}h {mins:02d}min"

    return f"{mins} min"


def formatar_horas(horas):
    horas = normalizar_numero(horas, 0)
    return f"{round(horas, 2)} h"


def obter_data_mais_recente(dicionario):
    if not isinstance(dicionario, dict) or not dicionario:
        return None

    try:
        return sorted(dicionario.keys())[-1]
    except Exception:
        return None


def preparar_luzes_resumidas(luzes):
    resumo = []

    for item in luzes:

        sensor_original = item.get("sensor", "Desconhecido")
        nome = nome_amigavel(sensor_original)

        tempo_por_dia_horas = item.get(
            "tempo_em_horas_das_luzes_ligadas_por_dia",
            {}
        )

        events_per_day = item.get(
            "events_per_day",
            {}
        )

        data_mais_recente_tempo = obter_data_mais_recente(
            tempo_por_dia_horas
        )

        data_mais_recente_eventos = obter_data_mais_recente(
            events_per_day
        )

        tempo_ultimo_dia_horas = None
        if data_mais_recente_tempo:
            tempo_ultimo_dia_horas = normalizar_numero(
                tempo_por_dia_horas.get(data_mais_recente_tempo),
                0
            )

        ativacoes_ultimo_dia = None
        if data_mais_recente_eventos:
            ativacoes_ultimo_dia = int(
                normalizar_numero(
                    events_per_day.get(data_mais_recente_eventos),
                    0
                )
            )

        resumo.append({
            "sensor_original": sensor_original,
            "sensor": nome,
            "tempo_total_min": normalizar_numero(
                item.get("tempo_total_min"),
                0
            ),
            "tempo_total_formatado": formatar_minutos(
                item.get("tempo_total_min", 0)
            ),
            "media_diaria_min": normalizar_numero(
                item.get("media_diaria_min"),
                0
            ),
            "media_diaria_formatada": formatar_minutos(
                item.get("media_diaria_min", 0)
            ),
            "ativacoes_total": int(
                normalizar_numero(
                    item.get("ativacoes_total"),
                    0
                )
            ),
            "ativacoes_hoje": int(
                normalizar_numero(
                    item.get("ativacoes_hoje"),
                    0
                )
            ),
            "data_ultimo_tempo": data_mais_recente_tempo,
            "tempo_ultimo_dia_horas": tempo_ultimo_dia_horas,
            "tempo_ultimo_dia_formatado": (
                formatar_horas(tempo_ultimo_dia_horas)
                if tempo_ultimo_dia_horas is not None
                else "sem dados"
            ),
            "data_ultimas_ativacoes": data_mais_recente_eventos,
            "ativacoes_ultimo_dia": ativacoes_ultimo_dia,
            "hora_pico": item.get("hora_pico"),
            "tempo_medio_ativacao_s": normalizar_numero(
                item.get("tempo_medio_ativacao_s"),
                0
            ),
            "alertas": item.get("alertas", [])
        })

    return resumo


# =========================
# DETETAR TIPO / INTENÇÃO
# =========================

def detectar_tipo(pergunta):
    p = pergunta.lower()

    # 1. Verificar PRIMEIRO se é um pedido geral/global
    if any(x in p for x in [
        "fábrica", "fabrica", "tudo", "geral", 
        "todos os sistemas", "resumo de toda","casa","resumo geral", 
        "resumo de toda a casa","resumo de toda a fábrica", 
        "resumo de toda a fabrica"
        
    ]):
        return "geral"

    # 2. Depois verifica os motores
    if any(x in p for x in [
        "motor", "motores", "rpm", "corrente",
        "potência", "potencia", "tensão", "tensao",
        "energia"
    ]):
        return "motor"

    # 3. Depois as bombas
    if any(x in p for x in [
        "bomba", "bombas", "pressão", "pressao", "bar",
        "água", "agua"
    ]):
        return "bomba"

    # 4. Por fim a iluminação
    if any(x in p for x in [
        "luz", "luzes", "iluminação", "iluminacao",
        "lampada", "lâmpada", "lampadas", "lâmpadas",
        "sala", "cozinha", "quarto", "corredor",
        "hall", "garagem", "wc", "casa de banho",
        "bathroom", "living", "kitchen", "bedroom",
        "ativações", "ativacoes", "ativação", "ativacao",
        "ligada", "ligado", "ativas", "ativo",
        "tempo ligada", "tempo ligado","cozinha?"
    ]):
        return "iluminacao"

    return "geral"


def detectar_intencao(pergunta):
    p = pergunta.lower()

    if any(x in p for x in [
        "mais ativa", "mais ativações", "mais ativacoes",
        "maior número de ativações", "maior numero de ativacoes",
        "maior quantidade de ativações", "qual tem mais ativações"
    ]):
        return "ranking_ativacoes_maior"

    if any(x in p for x in [
        "menos ativa", "menos ativações", "menos ativacoes",
        "menor número de ativações", "menor numero de ativacoes"
    ]):
        return "ranking_ativacoes_menor"

    if any(x in p for x in [
        "ativações", "ativacoes", "ativação", "ativacao",
        "quantas vezes", "número de vezes", "numero de vezes"
    ]):
        return "ativacoes"

    if any(x in p for x in [
        "mais tempo", "maior tempo", "mais ligada",
        "mais ligado", "mais horas", "maior consumo"
    ]):
        return "ranking_tempo_maior"

    if any(x in p for x in [
        "menos tempo", "menor tempo", "menos ligada",
        "menos ligado", "menos horas", "menor consumo"
    ]):
        return "ranking_tempo_menor"

    if any(x in p for x in [
        "tempo", "horas", "minutos", "ligada",
        "ligado", "ativo", "ativa", "ativas"
    ]):
        return "tempo"

    if any(x in p for x in [
        "alerta", "alertas", "problema", "anomalia",
        "erro", "falha", "avaria"
    ]):
        return "alertas"

    if any(x in p for x in [
        "hora pico", "pico", "hora de pico"
    ]):
        return "hora_pico"

    if any(x in p for x in [
        "resumo", "resume", "estado", "situação",
        "situacao", "como estão", "como estao"
    ]):
        return "resumo"

    return "geral"


# =========================
# CONTEXTO
# =========================

def gerar_contexto(pergunta):

    dados = carregar_resultados()

    if not dados:
        return {
            "tipo": "geral",
            "intencao": "erro",
            "dados": [],
            "erro": "Não foi possível carregar resultados."
        }

    tipo = detectar_tipo(pergunta)
    intencao = detectar_intencao(pergunta)
    equipamento = detectar_equipamento(pergunta)

    luzes = obter_lista_iluminacao(dados)
    motores = obter_motores(dados)
    bombas = obter_bombas(dados)

    if tipo == "iluminacao":

        if equipamento:
            luzes = [
                x for x in luzes
                if x.get("sensor") == equipamento
            ]

        return {
            "tipo": "iluminacao",
            "intencao": intencao,
            "equipamento": equipamento,
            "dados": luzes
        }

    if tipo == "motor":
        return {
            "tipo": "motor",
            "intencao": intencao,
            "dados": motores
        }

    if tipo == "bomba":
        return {
            "tipo": "bomba",
            "intencao": intencao,
            "dados": bombas
        }

    return {
        "tipo": "geral",
        "intencao": intencao,
        "dados": {
            "iluminacao": luzes,
            "motores": motores,
            "bombas": bombas
        }
    }




def extrair_data_da_pergunta(pergunta, luzes):
    """
    Tenta descobrir a data pedida pelo utilizador.
    Exemplo:
    - "dia 19"
    - "no dia 19"
    - "2026-05-19"
    """

    import re

    pergunta_lower = pergunta.lower()

    # Recolher todas as datas existentes nos dados
    datas_disponiveis = set()

    for item in luzes:
        dias = item.get(
            "tempo_em_horas_das_luzes_ligadas_por_dia",
            {}
        )

        if isinstance(dias, dict):
            for d in dias.keys():
                datas_disponiveis.add(str(d))

    if not datas_disponiveis:
        return None

    datas_ordenadas = sorted(datas_disponiveis)

    # Caso escrevas a data completa: 2026-05-19
    match_data_completa = re.search(
        r"\d{4}-\d{2}-\d{2}",
        pergunta_lower
    )

    if match_data_completa:
        data = match_data_completa.group(0)

        if data in datas_disponiveis:
            return data

    # Caso escrevas "dia 19"
    match_dia = re.search(
        r"dia\s+(\d{1,2})",
        pergunta_lower
    )

    if match_dia:
        dia_pedido = int(match_dia.group(1))

        # procurar a data disponível cujo dia seja 19
        for data in reversed(datas_ordenadas):
            try:
                dt = datetime.strptime(
                    data,
                    "%Y-%m-%d"
                )

                if dt.day == dia_pedido:
                    return data

            except Exception:
                pass

    # Caso escrevas "ontem"
    if "ontem" in pergunta_lower:
        try:
            ultima_data = datetime.strptime(
                datas_ordenadas[-1],
                "%Y-%m-%d"
            ).date()

            ontem = ultima_data.fromordinal(
                ultima_data.toordinal() - 1
            )

            ontem_str = ontem.strftime("%Y-%m-%d")

            if ontem_str in datas_disponiveis:
                return ontem_str

        except Exception:
            pass

    return None




# =========================
# RESPOSTAS DIRETAS — ILUMINAÇÃO
# =========================

def responder_iluminacao(pergunta, contexto):
    luzes = contexto.get("dados", [])
    intencao = contexto.get("intencao", "geral")

    if not luzes:
        return "Não encontrei dados de iluminação para essa pergunta."

    resumo = preparar_luzes_resumidas(luzes)

    # =========================
    # ATIVAÇÕES
    # =========================

    if intencao == "ativacoes":

        linhas = []

        for item in resumo:
            linhas.append(
                f"{item['sensor']} - {item['ativacoes_total']} ativações no total"
            )

        return "\n\n".join(linhas)

    if intencao == "ranking_ativacoes_maior":

        ordenado = sorted(
            resumo,
            key=lambda x: x["ativacoes_total"],
            reverse=True
        )

        top = ordenado[0]

        return (
            f"A luz com maior número de ativações é "
            f"{top['sensor']}, com {top['ativacoes_total']} ativações."
        )

    if intencao == "ranking_ativacoes_menor":

        ordenado = sorted(
            resumo,
            key=lambda x: x["ativacoes_total"]
        )

        top = ordenado[0]

        return (
            f"A luz com menor número de ativações é "
            f"{top['sensor']}, com {top['ativacoes_total']} ativações."
        )

    # =========================
    # TEMPO
    # =========================

    if intencao == "tempo":

        data_pedida = extrair_data_da_pergunta(
            pergunta,
            luzes
        )

        linhas = []

        for original, item in zip(luzes, resumo):

            tempo_por_dia = original.get(
                "tempo_em_horas_das_luzes_ligadas_por_dia",
                {}
            )

            # Se o utilizador pediu uma data específica
            if data_pedida:

                if data_pedida in tempo_por_dia:

                    horas = normalizar_numero(
                        tempo_por_dia.get(data_pedida),
                        0
                    )

                    linhas.append(
                        f"{item['sensor']} -> {formatar_horas(horas)} no dia {data_pedida}"
                    )

                else:

                    linhas.append(
                        f"{item['sensor']} -> sem dados no dia {data_pedida}"
                    )

            # Se não pediu data específica
            else:

                if item["data_ultimo_tempo"]:
                    linhas.append(
                        f"{item['sensor']} -> {item['tempo_total_formatado']} no total "
                        f"(último dia com dados: {item['data_ultimo_tempo']} = "
                        f"{item['tempo_ultimo_dia_formatado']})"
                    )
                else:
                    linhas.append(
                        f"{item['sensor']} -> {item['tempo_total_formatado']} no total"
                    )

        return "\n\n".join(linhas)

    if intencao == "ranking_tempo_maior":

        ordenado = sorted(
            resumo,
            key=lambda x: x["tempo_total_min"],
            reverse=True
        )

        top = ordenado[0]

        return (
            f"A luz que esteve ligada durante mais tempo foi "
            f"{top['sensor']}, com {top['tempo_total_formatado']} no total."
        )

    if intencao == "ranking_tempo_menor":

        ordenado = sorted(
            resumo,
            key=lambda x: x["tempo_total_min"]
        )

        top = ordenado[0]

        return (
            f"A luz que esteve ligada durante menos tempo foi "
            f"{top['sensor']}, com {top['tempo_total_formatado']} no total."
        )

    # =========================
    # ALERTAS
    # =========================

    if intencao == "alertas":

        linhas = []

        for item in resumo:
            alertas = item.get("alertas", [])

            if alertas:
                linhas.append(
                    f"{item['sensor']} -> {', '.join(alertas)}"
                )

        if not linhas:
            return "Não existem alertas relevantes nas luzes."

        return "\n\n".join(linhas)

    # =========================
    # HORA PICO
    # =========================

    if intencao == "hora_pico":

        linhas = []

        for item in resumo:
            hora = item.get("hora_pico")

            linhas.append(
                f"{item['sensor']} -> {hora if hora is not None else 'sem hora de pico disponível'}"
            )

        return "\n\n".join(linhas)

    # =========================
    # RESUMO GERAL
    # =========================

    linhas = []

    for item in resumo:
        linhas.append(
            f"{item['sensor']} -> tempo total: {item['tempo_total_formatado']}, "
            f"ativações: {item['ativacoes_total']}, "
            f"média diária: {item['media_diaria_formatada']}"
        )

    return "\n\n".join(linhas)



def resumir_motores(motores):
    if not motores:
        return "Não encontrei dados dos motores."

    linhas = []

    for motor in motores:
        nome = motor.get("motor", "Motor")
        status = motor.get("status", "Sem estado")

        linhas.append(f"{nome} -> estado: {status}")

        if "consumo_total_kwh" in motor:
            linhas.append(
                f"Consumo total: {motor.get('consumo_total_kwh')} kWh"
            )

        if "eficiencia_estimada" in motor:
            linhas.append(
                f"Eficiência estimada: {motor.get('eficiencia_estimada')}"
            )

        stats = motor.get("estatisticas", {})

        for campo, valores in stats.items():
            linhas.append(
                f"{campo}: média={valores.get('media')}, "
                f"mín={valores.get('min')}, máx={valores.get('max')}"
            )

    return "\n\n".join(linhas)


# =========================
# RESPOSTAS DIRETAS — BOMBAS
# =========================

def resumir_bombas(bombas):
    if not bombas:
        return "Não encontrei dados das bombas."

    linhas = []

    for bomba in bombas:
        nome = bomba.get("bomba", "Bombas / Sistema de Pressão")

        if nome == "Sistema de Pressão":
            nome = "Bombas / Sistema de Pressão"

        status = bomba.get("status", "Sem estado")

        linhas.append(f"{nome} -> estado: {status}")

        if "estabilidade" in bomba:
            linhas.append(
                f"Estabilidade: {bomba.get('estabilidade')}"
            )

        pressao = bomba.get("estatisticas_pressao", {})

        if pressao:
            linhas.append(
                f"Pressão: média={pressao.get('media')} bar, "
                f"mín={pressao.get('min')} bar, "
                f"máx={pressao.get('max')} bar"
            )

        custo = bomba.get("estatisticas_custo", {})

        if custo:
            linhas.append(
                f"Custo energético: média={custo.get('media')}, "
                f"total={custo.get('consumo_total')}"
            )

    return "\n\n".join(linhas)


# =========================
# LLM FALLBACK
# =========================

def chamar_llm(pergunta, contexto_texto, chat_history):
    historico = "\n".join([
        f"Utilizador: {x['pergunta']}\nAssistente: {x['resposta']}"
        for x in chat_history[-5:]
    ])

    prompt = f"""
És um assistente de análise inteligente.

Responde apenas à pergunta do utilizador.
Não inventes dados.
Usa apenas o contexto fornecido.
Responde em português de Portugal.

====================
HISTÓRICO
====================
{historico if historico else "Sem histórico."}

====================
PERGUNTA
====================
{pergunta}

====================
CONTEXTO
====================
{contexto_texto}

====================
REGRAS
====================
- Responde diretamente.
- Não faças perguntas ao utilizador se houver dados suficientes.
- Se não houver dados suficientes, diz claramente.
- Não mistures motores com luzes.
- Não mistures bombas com luzes.
- Num resumo geral, menciona sempre as luzes, os motores e as bombas.
- Mantém a formatação exata dos números e unidades do contexto (ex: se o contexto diz "4.06 h", escreve "4.06 h" e nunca "4h06").
"""


    #print("\n========== PROMPT ENVIADO AO LLM ==========")
    #print(prompt)
    #print("===========================================\n")

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": { 
                    "temperature": 0.8,
                    "num_predict": 3000,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1,
                    "num_ctx": 8192
                }
            },
            timeout=180
        )

        response.raise_for_status()

        data = response.json()

        return data.get("response", "Sem resposta do modelo.").strip()

    except requests.exceptions.ConnectionError:
        return "Erro: não foi possível ligar ao Ollama."

    except requests.exceptions.Timeout:
        return "Erro: o Ollama demorou demasiado tempo."

    except Exception as e:
        return f"Erro: {e}"





def preparar_contexto_luzes_para_llm(pergunta, contexto):

    luzes = contexto.get("dados", [])
    intencao = contexto.get("intencao", "geral")

    if not luzes:
        return "Não existem dados de iluminação disponíveis."

    resumo = preparar_luzes_resumidas(luzes)

    data_pedida = extrair_data_da_pergunta(
        pergunta,
        luzes
    )

    linhas = []

    for original, item in zip(luzes, resumo):

        linha = [
            f"Sensor: {item['sensor']}",
            f"Sensor técnico: {item['sensor_original']}",
            f"Ativações totais: {item['ativacoes_total']}",
            f"Ativações hoje: {item['ativacoes_hoje']}",
            f"Tempo total: {item['tempo_total_formatado']}",
            f"Média diária: {item['media_diaria_formatada']}",
        ]

        tempo_por_dia = original.get(
            "tempo_em_horas_das_luzes_ligadas_por_dia",
            {}
        )

        events_per_day = original.get(
            "events_per_day",
            {}
        )

        if data_pedida:

            if data_pedida in tempo_por_dia:
                linha.append(
                    f"Tempo no dia {data_pedida}: {tempo_por_dia[data_pedida]} h"
                )
            else:
                linha.append(
                    f"Tempo no dia {data_pedida}: sem dados"
                )

            if data_pedida in events_per_day:
                linha.append(
                    f"Ativações no dia {data_pedida}: {events_per_day[data_pedida]}"
                )
            else:
                linha.append(
                    f"Ativações no dia {data_pedida}: sem dados"
                )

        else:

            if item["data_ultimo_tempo"]:
                linha.append(
                    f"Último dia com dados de tempo: {item['data_ultimo_tempo']}"
                )

                linha.append(
                    f"Tempo nesse último dia: {item['tempo_ultimo_dia_formatado']}"
                )

            if item["data_ultimas_ativacoes"]:
                linha.append(
                    f"Último dia com ativações: {item['data_ultimas_ativacoes']}"
                )

                linha.append(
                    f"Ativações nesse último dia: {item['ativacoes_ultimo_dia']}"
                )

        if item.get("hora_pico") is not None:
            linha.append(
                f"Hora de pico: {item['hora_pico']}"
            )

        if item.get("alertas"):
            linha.append(
                f"Alertas: {', '.join(item['alertas'])}"
            )
        else:
            linha.append(
                "Alertas: sem alertas relevantes"
            )

        linhas.append(
            "\n".join(linha)
        )

    contexto_texto = f"""
DADOS DE ILUMINAÇÃO

Intenção detetada: {intencao}

Data pedida pelo utilizador: {data_pedida if data_pedida else "não especificada"}

{chr(10).join(["---"] + linhas)}
"""

    return contexto_texto




# =========================
# FUNÇÃO PRINCIPAL DO CHAT
# =========================

def perguntar_llm(pergunta, contexto, chat_history):
    tipo = contexto.get("tipo")
    intencao = contexto.get("intencao")

    # =========================
    # ILUMINAÇÃO
    # =========================

    if tipo == "iluminacao":

        contexto_texto = preparar_contexto_luzes_para_llm(
            pergunta,
            contexto
        )

        resposta = chamar_llm(
            pergunta,
            contexto_texto,
            chat_history
        )

        chat_history.append({
            "pergunta": pergunta,
            "resposta": resposta
        })

        if len(chat_history) > 20:
            chat_history.pop(0)

        return resposta

    # =========================
    # MOTORES
    # =========================

    if tipo == "motor":
        contexto_texto = resumir_motores(
            contexto.get("dados", [])
        )

        resposta = chamar_llm(
            pergunta,
            contexto_texto,
            chat_history
        )

        chat_history.append({
            "pergunta": pergunta,
            "resposta": resposta
        })

        if len(chat_history) > 20:
            chat_history.pop(0)

        return resposta

    # =========================
    # BOMBAS
    # =========================

    if tipo == "bomba":

        resposta = resumir_bombas(
            contexto.get("dados", [])
        )

        chat_history.append({
            "pergunta": pergunta,
            "resposta": resposta
        })

        if len(chat_history) > 20:
            chat_history.pop(0)

        return resposta

    # =========================
    # GERAL
    # =========================

    dados = contexto.get("dados", {})

    luzes = preparar_luzes_resumidas(
        dados.get("iluminacao", [])
    )

    texto_luzes = "\n".join([
        f"{x['sensor']} -> tempo: {x['tempo_total_formatado']}, "
        f"ativações: {x['ativacoes_total']}"
        for x in luzes
    ])

    texto_motores = resumir_motores(
        dados.get("motores", [])
    )

    texto_bombas = resumir_bombas(
        dados.get("bombas", [])
    )

    contexto_texto = f"""
LUZES:
{texto_luzes}

MOTORES:
{texto_motores}

BOMBAS:
{texto_bombas}
"""

    resposta = chamar_llm(
        pergunta,
        contexto_texto,
        chat_history
    )

    chat_history.append({
        "pergunta": pergunta,
        "resposta": resposta
    })

    if len(chat_history) > 20:
        chat_history.pop(0)

    return resposta


# =========================
# TESTE POR TERMINAL
# =========================

def iniciar_chat():
    chat_history = []

    print("\nMini Chat Industrial")
    print("Escreve 'sair' para terminar.\n")

    while True:
        pergunta = input("Pergunta > ")

        if pergunta.lower() == "sair":
            break

        contexto = gerar_contexto(pergunta)
        
        
        print("\n========== CONTEXTO ESTRUTURADO ==========")
        import json
        print(json.dumps(contexto, indent=4, ensure_ascii=False))
        print("==========================================\n")

        resposta = perguntar_llm(
            pergunta,
            contexto,
            chat_history
        )

        print("\n========== RESPOSTA ==========")
        print(resposta)
        print("==============================\n")





# ============================================================
# AVALIADOR ROBUSTO DA CONSULTA INTELIGENTE
# ============================================================
#
# Coloque esta secção no fim do seu programa.
# O avaliador:
#   1) verifica tipo, intenção e equipamento;
#   2) verifica o conteúdo da resposta com base nos dados reais;
#   3) permite várias execuções por pergunta para avaliar estabilidade;
#   4) separa erros de encaminhamento dos erros de resposta;
#   5) gera um resumo global e por categoria.
#
# IMPORTANTE:
# - As perguntas de teste devem representar casos diferentes.
# - Não use apenas palavras-chave como critério principal.
# - Os valores esperados são obtidos dos dados carregados quando possível.

import re
from collections import Counter, defaultdict


# ------------------------------------------------------------
# CONFIGURAÇÃO DA AVALIAÇÃO
# ------------------------------------------------------------

NUM_EXECUCOES = 3       # 3 execuções por pergunta
MOSTRAR_RESPOSTAS = True # False para uma saída mais curta


# ------------------------------------------------------------
# UTILITÁRIOS DO AVALIADOR
# ------------------------------------------------------------

import unicodedata

def normalizar_texto(texto):
    """
    Normaliza o texto para facilitar as comparações.

    - Converte o texto para minúsculas;
    - Remove acentos;
    - Garante que o valor recebido é convertido para string.
    """

    if texto is None:
        return ""

    texto = str(texto).lower()

    return ''.join(
        c
        for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

def obter_luz_por_sensor(dados, sensor):
    """Obtém diretamente uma luz pelo identificador técnico."""
    luzes = obter_lista_iluminacao(dados)

    for luz in luzes:
        if luz.get("sensor") == sensor:
            return luz

    return None


def obter_motor_por_nome(dados, nome):
    """Obtém diretamente um motor pelo nome."""
    motores = obter_motores(dados)

    for motor in motores:
        if motor.get("motor") == nome:
            return motor

    return None


def extrair_numeros(texto):
    """
    Extrai números de uma resposta, aceitando:
      39.20
      39,20
      39
      1.880
    """
    texto = str(texto)

    encontrados = re.findall(
        r"(?<![\w])\d+(?:[.,]\d+)?(?![\w])",
        texto
    )

    valores = []

    for item in encontrados:
        try:
            # Para números como 39,20 / 39.20
            valor = float(item.replace(",", "."))
            valores.append(valor)
        except ValueError:
            pass

    return valores


def numero_aparece(texto, esperado, tolerancia=0.01):
    """Verifica se um valor numérico aparece na resposta."""
    valores = extrair_numeros(texto)

    return any(
        abs(valor - float(esperado)) <= tolerancia
        for valor in valores
    )


def inteiro_aparece(texto, esperado):
    """
    Verifica números inteiros, incluindo respostas como:
    1880, 1.880 ou 1,880.
    """
    texto = str(texto)

    esperado = int(esperado)

    # Procura números escritos como inteiros
    candidatos = re.findall(r"(?<!\w)\d[\d.,]*", texto)

    for candidato in candidatos:
        limpo = candidato.replace(".", "").replace(",", "")

        if limpo.isdigit() and int(limpo) == esperado:
            return True

    return False


def duracao_em_minutos(texto):
    """
    Extrai durações presentes numa resposta e converte-as para minutos.

    Exemplos aceites:
        39h 20min
        39 h 20 min
        39 horas 20 minutos
        39 horas e 20 minutos
        4h06
        4 horas e 6 minutos
        3.52 h
        3,52 h
    """

    texto = normalizar_texto(texto)
    resultados = []

    # Padrão para horas e, opcionalmente, minutos
    padrao_hm = re.compile(
        r"(\d+(?:[.,]\d+)?)\s*"
        r"(?:h|hora|horas)"
        r"(?:\s*(?:e\s*)?(\d+(?:[.,]\d+)?)\s*"
        r"(?:m|min|mins|minuto|minutos))?"
    )

    for correspondencia in padrao_hm.finditer(texto):

        horas = float(
            correspondencia.group(1).replace(",", ".")
        )

        minutos = 0.0

        if correspondencia.group(2) is not None:
            minutos = float(
                correspondencia.group(2).replace(",", ".")
            )

        total_minutos = horas * 60 + minutos

        resultados.append(total_minutos)

    return resultados

def duracao_confere(texto, minutos_esperados, tolerancia=0.6):
    """
    Verifica se a duração apresentada na resposta corresponde
    à duração esperada.

    A comparação é feita em minutos, independentemente do formato
    utilizado pelo modelo de linguagem.

    Exemplos equivalentes:
        39h 20min
        39 horas 20 minutos
        39 horas e 20 minutos

    A tolerância predefinida é de 0,6 minutos.
    """

    if minutos_esperados is None:
        return False

    try:
        esperado = float(minutos_esperados)
    except (TypeError, ValueError):
        return False

    duracoes_obtidas = duracao_em_minutos(texto)

    for duracao in duracoes_obtidas:
        if abs(duracao - esperado) <= tolerancia:
            return True

    return False


def contem_algum(texto, alternativas):
    """Verifica se pelo menos uma alternativa aparece."""
    texto_norm = normalizar_texto(texto)

    return any(
        normalizar_texto(alternativa) in texto_norm
        for alternativa in alternativas
    )


# ------------------------------------------------------------
# VALIDAÇÃO DA INTENÇÃO / TIPO / EQUIPAMENTO
# ------------------------------------------------------------

def validar_encaminhamento(pergunta, contexto, teste):
    """
    Avalia apenas a parte realizada pelo programa antes do LLM.
    """
    erros = []

    tipo_esperado = teste.get("tipo_esperado")
    intencao_esperada = teste.get("intencao_esperada")
    equipamento_esperado = teste.get("equipamento_esperado")

    tipo_obtido = contexto.get("tipo")
    intencao_obtida = contexto.get("intencao")
    equipamento_obtido = contexto.get("equipamento")

    if tipo_esperado is not None and tipo_obtido != tipo_esperado:
        erros.append(
            f"Tipo: esperado='{tipo_esperado}', obtido='{tipo_obtido}'"
        )

    if intencao_esperada is not None and intencao_obtida != intencao_esperada:
        erros.append(
            f"Intenção: esperada='{intencao_esperada}', obtida='{intencao_obtida}'"
        )

    if equipamento_obtido != equipamento_esperado:
        erros.append(
            f"Equipamento: esperado='{equipamento_esperado}', "
            f"obtido='{equipamento_obtido}'"
        )

    return len(erros) == 0, erros


# ------------------------------------------------------------
# VALIDAÇÃO DA RESPOSTA DO LLM
# ------------------------------------------------------------

def validar_resposta_teste(resposta, teste, resultados):
    """
    Verifica o conteúdo da resposta com base no tipo de teste.
    Retorna:
      (True/False, [erros])
    """
    resposta_norm = normalizar_texto(resposta)
    erros = []

    regra = teste.get("regra")
    equipamento = teste.get("equipamento_esperado")

    # --------------------------------------------------------
    # TERMOS OBRIGATÓRIOS
    # --------------------------------------------------------
    if regra == "termos":
        for termo in teste.get("termos_obrigatorios", []):
            if normalizar_texto(termo) not in resposta_norm:
                erros.append(f"Termo em falta: '{termo}'")

        return len(erros) == 0, erros

    # --------------------------------------------------------
    # AUSÊNCIA DE DADOS
    # --------------------------------------------------------
    if regra == "sem_dados":
        termos = [
            "sem dados",
            "nao ha dados",
            "não há dados",
            "nao existem dados",
            "não existem dados",
            "dados insuficientes",
            "não foi possível determinar",
            "nao foi possivel determinar"
        ]

        if not contem_algum(resposta, termos):
            erros.append("Não foi indicada claramente a ausência de dados.")

        return len(erros) == 0, erros

    # --------------------------------------------------------
    # TEMPO TOTAL DE UMA LUZ
    # --------------------------------------------------------
    if regra == "tempo_total":

        luz = obter_luz_por_sensor(
            resultados,
            equipamento
        )

        if luz is None:
            return False, [
                f"Não foi encontrada a luz '{equipamento}' nos dados."
            ]

        minutos_esperados = luz.get("tempo_total_min")

        if minutos_esperados is None:
            return False, [
                "Não existe 'tempo_total_min' nos dados."
            ]

        # Verificar apenas se a duração apresentada está correta.
        # Não é obrigatório que o LLM mencione o nome da luz,
        # uma vez que o equipamento já foi identificado na pergunta
        # e validado na fase de encaminhamento.

        if not duracao_confere(
            resposta,
            minutos_esperados
        ):
            erros.append(
                f"Tempo esperado: {formatar_minutos(minutos_esperados)}"
            )

        return len(erros) == 0, erros

    # --------------------------------------------------------
    # ATIVAÇÕES DE UMA LUZ
    # --------------------------------------------------------
    if regra == "ativacoes":
        luz = obter_luz_por_sensor(resultados, equipamento)

        if luz is None:
            return False, [f"Não foi encontrada a luz '{equipamento}' nos dados."]

        esperado = luz.get("ativacoes_total")

        if esperado is None:
            return False, ["Não existe 'ativacoes_total' nos dados."]

        if not inteiro_aparece(resposta, esperado):
            erros.append(
                f"Ativações esperadas: {int(esperado)}"
            )

        return len(erros) == 0, erros

    # --------------------------------------------------------
    # RANKING DE ATIVAÇÕES
    # --------------------------------------------------------
    if regra == "ranking_ativacoes_maior":
        luzes = preparar_luzes_resumidas(
            obter_lista_iluminacao(resultados)
        )

        if not luzes:
            return False, ["Não existem dados de iluminação."]

        top = max(
            luzes,
            key=lambda x: x["ativacoes_total"]
        )

        esperado_sensor = top["sensor_original"]
        esperado_nome = top["sensor"]
        esperado_ativacoes = top["ativacoes_total"]

        if not contem_algum(
            resposta,
            [esperado_sensor, esperado_nome]
        ):
            erros.append(
                f"Equipamento esperado no ranking: {esperado_nome}"
            )

        if not inteiro_aparece(resposta, esperado_ativacoes):
            erros.append(
                f"Ativações esperadas: {esperado_ativacoes}"
            )

        return len(erros) == 0, erros

    # --------------------------------------------------------
    # RANKING DE TEMPO
    # --------------------------------------------------------
    if regra == "ranking_tempo_maior":
        luzes = preparar_luzes_resumidas(
            obter_lista_iluminacao(resultados)
        )

        if not luzes:
            return False, ["Não existem dados de iluminação."]

        top = max(
            luzes,
            key=lambda x: x["tempo_total_min"]
        )

        esperado_nome = top["sensor"]
        esperado_tempo = top["tempo_total_min"]

        if not contem_algum(
            resposta,
            [top["sensor_original"], esperado_nome]
        ):
            erros.append(
                f"Equipamento esperado: {esperado_nome}"
            )

        if not duracao_confere(resposta, esperado_tempo):
            erros.append(
                f"Tempo esperado: {formatar_minutos(esperado_tempo)}"
            )

        return len(erros) == 0, erros

    # --------------------------------------------------------
    # HORA DE PICO
    # --------------------------------------------------------
    if regra == "hora_pico":
        luz = obter_luz_por_sensor(resultados, equipamento)

        if luz is None:
            return False, [f"Luz '{equipamento}' não encontrada."]

        hora_esperada = luz.get("hora_pico")

        # Se não existir valor, a resposta deve reconhecer isso.
        if hora_esperada is None:
            termos = [
                "sem dados",
                "nao ha dados",
                "não há dados",
                "nao foi possivel",
                "não foi possível",
                "indisponivel",
                "indisponível"
            ]

            if not contem_algum(resposta, termos):
                erros.append(
                    "Era esperado indicar que não existem dados de hora de pico."
                )

            return len(erros) == 0, erros

        if str(hora_esperada).lower() not in resposta_norm:
            erros.append(
                f"Hora de pico esperada: {hora_esperada}"
            )

        return len(erros) == 0, erros

    # --------------------------------------------------------
    # TEMPO NUM DIA ESPECÍFICO
    # --------------------------------------------------------
    if regra == "tempo_data":
        luz = obter_luz_por_sensor(resultados, equipamento)

        if luz is None:
            return False, [f"Luz '{equipamento}' não encontrada."]

        data = teste.get("data")
        tempos = luz.get(
            "tempo_em_horas_das_luzes_ligadas_por_dia",
            {}
        )

        if data not in tempos:
            # Se não existir, a resposta deve indicar ausência de dados.
            if not contem_algum(
                resposta,
                ["sem dados", "não há dados", "nao ha dados"]
            ):
                erros.append(
                    f"Não existem dados para a data {data} e isso não foi indicado."
                )

            return len(erros) == 0, erros

        horas_esperadas = float(tempos[data])

        if not duracao_confere(
            resposta,
            horas_esperadas * 60,
            tolerancia=0.6
        ):
            erros.append(
                f"Tempo esperado em {data}: {formatar_horas(horas_esperadas)}"
            )

        # É útil confirmar a data.
        dia_str = str(int(data.split("-")[2]))
        if dia_str not in resposta_norm and data not in resposta_norm:
            erros.append(
                f"Data/dia esperado na resposta: {data}"
            )

        return len(erros) == 0, erros

    # --------------------------------------------------------
    # RESUMO DOS MOTORES
    # --------------------------------------------------------
    if regra == "motores_resumo":
        motores = obter_motores(resultados)

        if not motores:
            return False, ["Não existem dados dos motores."]

        for motor in motores:
            nome = motor.get("motor", "")
            if nome and normalizar_texto(nome) not in resposta_norm:
                erros.append(f"Motor em falta: {nome}")

            if "consumo_total_kwh" in motor:
                valor = motor["consumo_total_kwh"]

                if not numero_aparece(resposta, valor):
                    erros.append(
                        f"{nome}: consumo esperado={valor} kWh"
                    )

        return len(erros) == 0, erros

    # --------------------------------------------------------
    # POTÊNCIA E RPM
    # --------------------------------------------------------
    if regra == "motores_potencia_rpm":
        motores = obter_motores(resultados)

        if not motores:
            return False, ["Não existem dados dos motores."]

        for motor in motores:
            nome = motor.get("motor", "")
            stats = motor.get("estatisticas", {})

            potencia = stats.get("potencia", {})
            rpm = stats.get("velocidade", stats.get("rpm", {}))

            # Tentar algumas designações possíveis do JSON.
            if not potencia:
                potencia = stats.get("potencia_kw", {})

            if not rpm:
                rpm = stats.get("velocidade_rotacao", {})

            if nome and normalizar_texto(nome) not in resposta_norm:
                erros.append(f"Motor em falta: {nome}")

            if isinstance(potencia, dict) and "media" in potencia:
                if not numero_aparece(resposta, potencia["media"]):
                    erros.append(
                        f"{nome}: potência média esperada={potencia['media']}"
                    )

            if isinstance(rpm, dict) and "media" in rpm:
                if not numero_aparece(resposta, rpm["media"]):
                    erros.append(
                        f"{nome}: RPM médio esperado={rpm['media']}"
                    )

        return len(erros) == 0, erros

    # --------------------------------------------------------
    # BOMBAS
    # --------------------------------------------------------
    if regra == "bombas":
        bombas = obter_bombas(resultados)

        if not bombas:
            return False, ["Não existem dados das bombas."]

        for bomba in bombas:
            estado = bomba.get("status")

            if estado is not None and normalizar_texto(str(estado)) not in resposta_norm:
                erros.append(f"Estado esperado: {estado}")

            pressao = bomba.get("estatisticas_pressao", {})

            if isinstance(pressao, dict):
                for chave in ("media", "min", "max"):
                    if chave in pressao:
                        if not numero_aparece(resposta, pressao[chave]):
                            erros.append(
                                f"Pressão {chave} esperada={pressao[chave]} bar"
                            )

        return len(erros) == 0, erros

    # --------------------------------------------------------
    # RESUMO GERAL
    # --------------------------------------------------------
    if regra == "geral":
        categorias = {
            "luzes": ["luz", "luzes", "iluminacao", "iluminação"],
            "motores": ["motor", "motores"],
            "bombas": ["bomba", "bombas", "pressao", "pressão"],
        }

        for categoria, termos in categorias.items():
            if not contem_algum(resposta, termos):
                erros.append(
                    f"Categoria não mencionada: {categoria}"
                )

        return len(erros) == 0, erros

    return False, [f"Regra de teste desconhecida: {regra}"]


# ------------------------------------------------------------
# CASOS DE TESTE
# ------------------------------------------------------------
#
# NOTA:
# "intencao_esperada" é agora avaliada separadamente.
# Os critérios da resposta são baseados nos valores dos dados.
#
# Podes aumentar este conjunto para 20, 30 ou mais perguntas.
# ------------------------------------------------------------

TESTES = [
    {
        "id": 1,
        "categoria": "Iluminação - tempo",
        "pergunta": "Quantas horas esteve ligada a luz da cozinha?",
        "tipo_esperado": "iluminacao",
        "intencao_esperada": "tempo",
        "equipamento_esperado": "Luz3",
        "regra": "tempo_total",
    },
    {
        "id": 2,
        "categoria": "Iluminação - ranking ativações",
        "pergunta": "Qual foi a luz com maior número de ativações?",
        "tipo_esperado": "iluminacao",
        "intencao_esperada": "ranking_ativacoes_maior",
        "equipamento_esperado": None,
        "regra": "ranking_ativacoes_maior",
    },
    {
        "id": 3,
        "categoria": "Bombagem - estado",
        "pergunta": "Como está o estado das bombas?",
        "tipo_esperado": "bomba",
        "intencao_esperada": "resumo",
        "equipamento_esperado": None,
        "regra": "bombas",
    },
    {
        "id": 4,
        "categoria": "Iluminação - tempo",
        "pergunta": "Quanto tempo esteve ligada a luz da cozinha?",
        "tipo_esperado": "iluminacao",
        "intencao_esperada": "tempo",
        "equipamento_esperado": "Luz3",
        "regra": "tempo_total",
    },
    {
        "id": 5,
        "categoria": "Iluminação - ativações",
        "pergunta": "Quantas vezes a luz da sala de máquinas foi ativada?",
        "tipo_esperado": "iluminacao",
        "intencao_esperada": "ativacoes",
        "equipamento_esperado": "Luz5",
        "regra": "ativacoes",
    },
    {
        "id": 6,
        "categoria": "Iluminação - ranking tempo",
        "pergunta": "Qual foi a luz que esteve mais tempo ligada?",
        "tipo_esperado": "iluminacao",
        "intencao_esperada": "ranking_tempo_maior",
        "equipamento_esperado": None,
        "regra": "ranking_tempo_maior",
    },
    {
        "id": 7,
        "categoria": "Iluminação - hora de pico",
        "pergunta": "Diz-me a hora de pico do quarto 1.",
        "tipo_esperado": "iluminacao",
        "intencao_esperada": "hora_pico",
        "equipamento_esperado": "Luz8",
        "regra": "hora_pico",
    },
    {
        "id": 8,
        "categoria": "Iluminação - data específica",
        "pergunta": "Tempo da luz da garagem no dia 19",
        "tipo_esperado": "iluminacao",
        "intencao_esperada": "tempo",
        "equipamento_esperado": "Luz7",
        "regra": "tempo_data",
        # Ajusta o ano/mês se os teus dados mudarem.
        "data": "2026-05-19",
    },
    {
        "id": 9,
        "categoria": "Motores - resumo",
        "pergunta": "Faz um resumo do estado atual dos motores.",
        "tipo_esperado": "motor",
        "intencao_esperada": "resumo",
        "equipamento_esperado": None,
        "regra": "motores_resumo",
    },
    {
        "id": 10,
        "categoria": "Motores - potência e RPM",
        "pergunta": "Qual é a potência e os rpm dos motores?",
        "tipo_esperado": "motor",
        "intencao_esperada": "geral",
        "equipamento_esperado": None,
        "regra": "motores_potencia_rpm",
    },
    {
        "id": 11,
        "categoria": "Bombagem - estado",
        "pergunta": "Como estão as bombas de água?",
        "tipo_esperado": "bomba",
        "intencao_esperada": "resumo",
        "equipamento_esperado": None,
        "regra": "bombas",
    },
    {
        "id": 12,
        "categoria": "Bombagem - falhas",
        "pergunta": "Houve alguma falha de pressão nas bombas?",
        "tipo_esperado": "bomba",
        "intencao_esperada": "alertas",
        "equipamento_esperado": None,
        "regra": "bombas",
    },
    {
        "id": 13,
        "categoria": "Geral",
        "pergunta": "Faz um resumo de toda a casa, como estão as luzes e as máquinas?",
        "tipo_esperado": "geral",
        "intencao_esperada": "resumo",
        "equipamento_esperado": None,
        "regra": "geral",
    },
]


# ------------------------------------------------------------
# EXECUÇÃO DO AVALIADOR
# ------------------------------------------------------------

import time  # Importar o módulo time

def avaliar_acerto_chatbot():
    print("\n" + "=" * 70)
    print("INÍCIO DA AVALIAÇÃO AUTOMÁTICA")
    print("=" * 70)

    resultados = carregar_resultados()

    if not resultados:
        print("ERRO: não foi possível carregar resultados.json.")
        return

    total_testes = len(TESTES) * NUM_EXECUCOES
    total_passou = 0
    
    # Lista para registar os tempos de todas as execuções
    todos_os_tempos = [] 

    resultados_individuais = []
    por_categoria = defaultdict(lambda: {"total": 0, "passou": 0})

    print(
        f"\nPerguntas: {len(TESTES)} | "
        f"Execuções por pergunta: {NUM_EXECUCOES} | "
        f"Total de avaliações: {total_testes}\n"
    )

    for teste in TESTES:

        passes_teste = 0
        erros_teste = []
        tempos_do_teste = [] # Regista tempos apenas deste teste

        for execucao in range(1, NUM_EXECUCOES + 1):

            chat_history = []

            contexto = gerar_contexto(teste["pergunta"])

            encaminhamento_ok, erros_encaminhamento = validar_encaminhamento(
                teste["pergunta"],
                contexto,
                teste
            )

            # ============================================================
            # MEDIÇÃO DO TEMPO DE RESPOSTA
            # ============================================================
            inicio = time.time()

            resposta = perguntar_llm(
                teste["pergunta"],
                contexto,
                chat_history
            )

            tempo_execucao = time.time() - inicio
            tempos_do_teste.append(tempo_execucao)
            todos_os_tempos.append(tempo_execucao)
            # ============================================================

            resposta_ok, erros_resposta = validar_resposta_teste(
                resposta,
                teste,
                resultados
            )

            passou = encaminhamento_ok and resposta_ok

            if passou:
                total_passou += 1
                passes_teste += 1

            por_categoria[teste["categoria"]]["total"] += 1

            if passou:
                por_categoria[teste["categoria"]]["passou"] += 1

            resultados_individuais.append({
                "teste": teste["id"],
                "categoria": teste["categoria"],
                "execucao": execucao,
                "passou": passou,
                "encaminhamento_ok": encaminhamento_ok,
                "resposta_ok": resposta_ok,
                "tempo_s": tempo_execucao
            })

            if not passou:
                erros_teste.append({
                    "execucao": execucao,
                    "encaminhamento": erros_encaminhamento,
                    "resposta": erros_resposta,
                    "resposta_texto": resposta,
                })

            if MOSTRAR_RESPOSTAS:
                print("\n" + "-" * 70)
                print(
                    f"Teste {teste['id']} | "
                    f"Execução {execucao}/{NUM_EXECUCOES}"
                )
                print(f"Categoria: {teste['categoria']}")
                print(f"Pergunta: {teste['pergunta']}")
                print(f"Tipo: {contexto.get('tipo')}")
                print(f"Intenção: {contexto.get('intencao')}")
                print(f"Equipamento: {contexto.get('equipamento')}")
                print(f"Tempo de Resposta: {tempo_execucao:.2f} s")
                print(f"Resultado: {'PASSOU' if passou else 'FALHOU'}")
                print("Resposta:")
                print(resposta)

                if erros_encaminhamento:
                    print("Erros de encaminhamento:")
                    for erro in erros_encaminhamento:
                        print(f"  - {erro}")

                if erros_resposta:
                    print("Erros da resposta:")
                    for erro in erros_resposta:
                        print(f"  - {erro}")

        estabilidade = (
            "ESTÁVEL - passou em todas as execuções"
            if passes_teste == NUM_EXECUCOES
            else
            "INSTÁVEL - passou em algumas execuções"
            if passes_teste > 0
            else
            "FALHOU - não passou em nenhuma execução"
        )

        media_tempo_teste = sum(tempos_do_teste) / len(tempos_do_teste)

        print("\n" + "=" * 70)
        print(
            f"Teste {teste['id']} - "
            f"{passes_teste}/{NUM_EXECUCOES} -> {estabilidade} | "
            f"Tempo médio: {media_tempo_teste:.2f} s"
        )
        print("=" * 70)

    # --------------------------------------------------------
    # RESULTADO GLOBAL COM MÉDIA DE TEMPOS
    # --------------------------------------------------------

    taxa_global = (
        total_passou / total_testes * 100
        if total_testes
        else 0
    )

    media_tempo_global = (
        sum(todos_os_tempos) / len(todos_os_tempos)
        if todos_os_tempos
        else 0
    )

    print("\n\n" + "=" * 70)
    print("RESULTADO GLOBAL")
    print("=" * 70)

    print(
        f"Respostas corretas: {total_passou}/{total_testes}"
    )
    print(
        f"Taxa global de sucesso: {taxa_global:.1f}%"
    )
    print(
        f"Tempo médio de resposta global: {media_tempo_global:.2f} segundos"
    )

    # --------------------------------------------------------
    # RESULTADOS POR CATEGORIA
    # --------------------------------------------------------

    print("\nRESULTADOS POR CATEGORIA")
    print("-" * 70)

    for categoria, valores in sorted(por_categoria.items()):
        taxa = (
            valores["passou"] / valores["total"] * 100
            if valores["total"]
            else 0
        )

        print(
            f"{categoria}: "
            f"{valores['passou']}/{valores['total']} "
            f"({taxa:.1f}%)"
        )

    # --------------------------------------------------------
    # ESTABILIDADE E TEMPOS POR PERGUNTA
    # --------------------------------------------------------

    print("\nESTABILIDADE E TEMPO MÉDIO POR PERGUNTA")
    print("-" * 70)

    for teste in TESTES:
        resultados_teste = [
            x for x in resultados_individuais
            if x["teste"] == teste["id"]
        ]

        passou = sum(
            1 for x in resultados_teste if x["passou"]
        )
        
        media_tempo = sum(
            x["tempo_s"] for x in resultados_teste
        ) / len(resultados_teste)

        print(
            f"Teste {teste['id']:02d}: "
            f"{passou}/{NUM_EXECUCOES} | "
            f"Tempo médio: {media_tempo:.2f} s"
        )

    # --------------------------------------------------------
    # RESUMO PARA A DISSERTAÇÃO
    # --------------------------------------------------------

    perguntas_estaveis = 0
    perguntas_instaveis = 0
    perguntas_falhadas = 0

    for teste in TESTES:
        resultados_teste = [
            x for x in resultados_individuais
            if x["teste"] == teste["id"]
        ]

        passou = sum(
            1 for x in resultados_teste if x["passou"]
        )

        if passou == NUM_EXECUCOES:
            perguntas_estaveis += 1
        elif passou == 0:
            perguntas_falhadas += 1
        else:
            perguntas_instaveis += 1

    print("\nRESUMO")
    print("-" * 70)
    print(
        f"Perguntas estáveis: {perguntas_estaveis}/{len(TESTES)}"
    )
    print(
        f"Perguntas instáveis: {perguntas_instaveis}/{len(TESTES)}"
    )
    print(
        f"Perguntas que falharam em todas as execuções: "
        f"{perguntas_falhadas}/{len(TESTES)}"
    )
    print(
        f"Tempo médio global: {media_tempo_global:.2f} s"
    )

    print("\n" + "=" * 70)
    print("FIM DA AVALIAÇÃO")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    iniciar_chat()
    #avaliar_acerto_chatbot()



