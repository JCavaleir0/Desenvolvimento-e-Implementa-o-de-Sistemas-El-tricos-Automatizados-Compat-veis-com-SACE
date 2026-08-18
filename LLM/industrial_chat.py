import json
import requests
from datetime import datetime, date


# =========================
# CONFIG
# =========================

OLLAMA_URL = "http://localhost:11434/api/generate"

# Usa este se já instalaste:
#MODEL = "qwen2.5:14b"

# Se ainda não instalaste o qwen, usa temporariamente:
MODEL = "llama3.1:8b"

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
    pergunta = pergunta.lower()

    for equipamento, info in NOMES_EQUIPAMENTOS.items():

        if equipamento.lower() in pergunta:
            return equipamento

        if info["nome"].lower() in pergunta:
            return equipamento

        for alias in info["aliases"]:
            if alias.lower() in pergunta:
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

    if any(x in p for x in [
        "motor", "motores", "rpm", "corrente",
        "potência", "potencia", "tensão", "tensao",
        "energia"
    ]):
        return "motor"

    if any(x in p for x in [
        "bomba", "bombas", "pressão", "pressao", "bar",
        "água", "agua"
    ]):
        return "bomba"

    if any(x in p for x in [
        "luz", "luzes", "iluminação", "iluminacao",
        "lampada", "lâmpada", "lampadas", "lâmpadas",
        "sala", "cozinha", "quarto", "corredor",
        "hall", "garagem", "wc", "casa de banho",
        "bathroom", "living", "kitchen", "bedroom",
        "ativações", "ativacoes", "ativação", "ativacao",
        "ligada", "ligado", "ativas", "ativo",
        "tempo ligada", "tempo ligado"
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

# =========================
# RESPOSTAS DIRETAS — MOTORES
# =========================

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
És um assistente industrial SCADA.

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
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
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

        resposta = perguntar_llm(
            pergunta,
            contexto,
            chat_history
        )

        print("\n========== RESPOSTA ==========")
        print(resposta)
        print("==============================\n")


if __name__ == "__main__":
    iniciar_chat()