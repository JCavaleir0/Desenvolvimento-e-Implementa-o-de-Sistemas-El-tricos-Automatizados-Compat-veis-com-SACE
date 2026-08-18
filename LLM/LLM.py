import os
import json
import pandas as pd
import requests
from datetime import date, datetime
from influxdb_client import InfluxDBClient
from dotenv import load_dotenv

from industrial_chat import MODEL


load_dotenv()

INFLUX_URL = "https://eu-central-1-1.aws.cloud2.influxdata.com/"
TOKEN = os.getenv("INFLUX_TOKEN")
ORG = "755b787e0d3381b2"
BUCKET = "fuxa-data"

HISTORICO_FILE = "historico.parquet"
MOTOR_HISTORICO_FILE = "motor_historico.parquet"
BOMBAS_HISTORICO_FILE = "bombas_historico.parquet"
RESULTADOS_FILE = "resultados.json"
LAST_RUN_FILE = "last_run.json"
final_time_str = None



def gerar_insight(data, tipo_analise="iluminacao"):
    if tipo_analise == "iluminacao":
        prompt = f"""
    Resumo:
    Analisa estes dados de iluminação de forma simples e prática.
    Os dados que recebes como luz1,luz2,...Escadas, correspondem ao seguintes Nomes/Localizações:
    Qualquer análise ou insight que tenhas a dar, tem de ser baseada nestes nomes e não nos nomes técnicos dos sensores.
            "Escadas": "Stairs",
            "Luz2": "Living room",
            "Luz3": "Kitchen",
            "Luz4": "Living Area",
            "Luz5": "Machinery Room",
            "Luz6": "Bathroom 0",
            "Luz7": "Garage",
            "Luz8": "Bedroom 1",
            "Luz9": "Bedroom 2",
            "Luz10": "Bedroom 3",
            "Luz11": "Bathroom 1",
            "Luz12": "Hallway",

    DADOS:
    {data}
    """
    elif tipo_analise == "motor":
        prompt = f"""
        És um especialista industrial em motores elétricos, manutenção preditiva e eficiência energética.

        Analisa os seguintes dados do motor de forma técnica, objetiva e prática.

        A análise deve focar-se em:
        - Eficiência energética
        - Estabilidade operacional
        - Comportamentos anormais
        - Possíveis problemas de manutenção
        - Anomalias elétricas
        - Anomalias mecânicas
        - Padrões de consumo
        - Degradação de desempenho
        - Riscos operacionais
        - Recomendações de otimização

        DADOS DO MOTOR:
        {data}

    REGRAS IMPORTANTES:
    - Sê técnico mas conciso.
    - Usa linguagem de engenharia industrial.
    - NÃO inventes valores que não estejam nos dados.
    - Deteta possíveis anomalias com base em corrente, tensão, RPM, potência e energia.
    - Compara médias, mínimos e máximos quando relevante.
    - Indica se o motor aparenta estar estável ou instável.
    - Refere possíveis causas para relações anormais entre RPM, corrente e potência.
    - Identifica possíveis condições de sobrecarga.
    - Refere possíveis desperdícios energéticos ou baixa eficiência.
    - Sugere ações de manutenção preventiva quando existirem padrões anormais.
    - Se os valores estiverem normais, indica que o funcionamento aparenta estar saudável.

    FORMATO DA RESPOSTA:

    Status:
    - NORMAL / ALERTA / CRÍTICO

    Análise Técnica:
    - Interpretação técnica detalhada dos dados.

    Eficiência Energética:
    - Avaliação do consumo energético e eficiência.

    Comportamento Operacional:
    - Estabilidade, consistência do RPM, comportamento da carga e anomalias.

    Insights de Manutenção:
    - Possíveis problemas mecânicos/elétricos e ações preventivas.

    Recomendações:
    - Recomendações práticas de engenharia e otimização.
    """
    elif tipo_analise == "bomba":
        prompt = f"""
    Analisa estes dados do sistema de bomba de pressão de forma técnica e objetiva.

    Os dados disponíveis representam:

    Pressão do sistema (bar)
    Custo energético / consumo da bomba NA MOEDA EURO, MUITO IMPORTANTE PARA A ANÁLISE 

    Com base nestes dados, fornece:

    Avaliação da estabilidade da pressão
    Identificação de oscilações ou quedas anormais de pressão
    Relação entre pressão e custo energético
    Possíveis sinais de:
    Sobrecarga
    Fugas no sistema
    Funcionamento irregular
    Perda de eficiência
    Consumo excessivo
    Identificação de padrões de utilização ao longo do dia
    Conclusão técnica sobre o estado geral do sistema

    Regras:

    Usa linguagem técnica mas clara
    Não inventes dados
    Baseia a análise apenas nos dados fornecidos
    Se não houver informação suficiente, diz explicitamente

    DADOS DA BOMBA:
    {data}


    """
    else:
        prompt = f"""
    Analisa estes dados de forma geral:
    {data}
    """

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120000
        )
        return response.json().get("response", "Sem resposta do modelo")
    except Exception as e:
        return f"Erro: {e}"


def get_last_time():
    try:
        with open(LAST_RUN_FILE, encoding="utf-8") as f:
            last_time = json.load(f)["last_time"]
            return last_time.replace("+00:00Z", "Z")
    except Exception:
        return "-30d"


def preparar_df(df):
    if df.empty:
        return df

    df = df.copy()

    df["rawDuration"] = pd.to_numeric(df["rawDuration"], errors="coerce").fillna(0)
    df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0)

    df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
    df = df.dropna(subset=["time"])

    df["time"] = df["time"].dt.tz_convert("UTC").dt.tz_localize(None)

    df["date"] = df["time"].dt.date
    df["hour"] = df["time"].dt.hour
    df["duration_s"] = df["rawDuration"] / 1000

    return df





def run_analysis():

    print("\nNova análise...")

    sensores = [
        "Luz2", "Luz3", "Luz4", "Luz5", "Luz6",
        "Luz7", "Luz8", "Luz9", "Luz10", "Luz11", "Luz12", "Escadas"
    ]

    resultados_json_anteriores = {}

    if os.path.exists(RESULTADOS_FILE):
        try:
            with open(RESULTADOS_FILE, encoding="utf-8") as f:
                resultados_json_anteriores = json.load(f)
        except Exception:
            resultados_json_anteriores = {}

    resultados_anteriores_luzes = {}
    resultados_anteriores_motores = []
    resultados_anteriores_bombas = []

    if isinstance(resultados_json_anteriores, dict):

        for r in resultados_json_anteriores.get("iluminacao", []):

            if isinstance(r, dict) and "sensor" in r:

                resultados_anteriores_luzes[r["sensor"]] = r

        resultados_anteriores_motores = resultados_json_anteriores.get(
            "motores",
            []
        )

        resultados_anteriores_bombas = resultados_json_anteriores.get(
            "bombas",
            []
        )

    # =========================
    # HISTÓRICO LUZES
    # ======================

    if os.path.exists(HISTORICO_FILE) and os.path.getsize(HISTORICO_FILE) > 0:
        try:
            df_old = pd.read_parquet(HISTORICO_FILE)
        except Exception as e:
            print(f"Erro ao ler histórico, a reiniciar: {e}")
            df_old = pd.DataFrame()
    else:
        df_old = pd.DataFrame()
        
# =========================
# HISTÓRICO MOTOR
# =========================

    if os.path.exists(MOTOR_HISTORICO_FILE) and os.path.getsize(MOTOR_HISTORICO_FILE) > 0:
        try:
            df_motor_old = pd.read_parquet(MOTOR_HISTORICO_FILE)

        except Exception as e:
            print(f"Erro ao ler histórico motor: {e}")
            df_motor_old = pd.DataFrame()

    else:
        df_motor_old = pd.DataFrame()

    if os.path.exists(BOMBAS_HISTORICO_FILE) and os.path.getsize(BOMBAS_HISTORICO_FILE) > 0:
        try:
            df_bombas_old = pd.read_parquet(BOMBAS_HISTORICO_FILE)
        except Exception as e:
            print(f"Erro ao ler histórico bombas: {e}")
            df_bombas_old = pd.DataFrame()
    else:
        df_bombas_old = pd.DataFrame()

    # Inicializar df_bombas_total
    df_bombas_total = df_bombas_old.copy() if not df_bombas_old.empty else pd.DataFrame()

    last_time = get_last_time()

    if last_time == "-30d":
        range_query = '|> range(start: -30d)'
    else:
        range_query = f'|> range(start: date.sub(d: 10s, from: time(v: "{last_time}")))'

    print("Último timestamp:", last_time)

    data = []

    client = None
    query_api = None

    try:
        client = InfluxDBClient(
            url=INFLUX_URL,
            token=TOKEN,
            org=ORG,
            timeout=120000
        )

        query_api = client.query_api()

        for sensor in sensores:
            try:
                print(f"A buscar dados de {sensor}...")

                query = f'''
            import "date"

            from(bucket: "{BUCKET}")
                {range_query}
                |> filter(fn: (r) => r["_measurement"] == "{sensor}")
                |> filter(fn: (r) =>
                    r["_field"] == "rawDuration" or
                    r["_field"] == "value"
                )
                |> aggregateWindow(every: 20s, fn: last, createEmpty: false)
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            '''

                tables = query_api.query(query)

                for table in tables:
                    for record in table.records:
                        data.append({
                            "measurement": record.get_measurement(),
                            "time": record.get_time(),
                            "rawDuration": record.values.get("rawDuration"),
                            "value": record.values.get("value")
                        })

            except Exception as e:
                print(f"Erro ao buscar {sensor}: {e}")
                continue
        
        
        
        # =========================
        # LEITURA DADOS BOMBAS
        # =========================
        bombas_data = []

        try:
            print("A buscar dados de Bombas...")

            query_bombas = f'''
            import "date"
            from(bucket: "{BUCKET}")
                {range_query}
                |> filter(fn: (r) => r["_measurement"] == "Bombas")
                |> filter(fn: (r) =>
                    r["_field"] == "bar" or
                    r["_field"] == "Custo_Energy"
                )
                |> aggregateWindow(every: 20s, fn: last, createEmpty: false)
                |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
            '''

            tables_bombas = query_api.query(query_bombas)

            for table in tables_bombas:
                for record in table.records:
                    bombas_data.append({
                        "time": record.get_time(),
                        "bar": record.values.get("bar"),
                        "Custo_Energy": record.values.get("Custo_Energy"),
                        "custo_energy": record.values.get("custo_energy"),
                        "cost": record.values.get("cost"),
                        "value": record.values.get("value")
                    })

            # DEBUG: ver no terminal
            print(f"Total registos Bombas recebidos: {len(bombas_data)}")
            if bombas_data:
                print("Primeiros 5 registros das Bombas:")
                for i, reg in enumerate(bombas_data[:5]):
                    print(
                        f"{i}: time={reg['time']}, "
                        f"bar={reg['bar']}, "
                        f"cost={reg['Custo_Energy']}"
                    )

        except Exception as e:
            print(f"Erro ao buscar Bombas: {e}")

        # =========================
        # LEITURA MOTOR 1
        # =========================

        motor_data = []

        try:
            print("A buscar dados do Motor1...")

            query_motor = f'''
            import "date"
            from(bucket: "{BUCKET}")
                {range_query}
                |> filter(fn: (r) => r["_measurement"] == "Motor1")
                |> filter(fn: (r) =>
                    r["_field"] == "current1" or
                    r["_field"] == "voltage1" or
                    r["_field"] == "rpm1" or
                    r["_field"] == "energy1" or
                    r["_field"] == "power1"
                )
                |> aggregateWindow(every: 20s, fn: last, createEmpty: false)
                |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
            '''

            tables_motor = query_api.query(query_motor)

            for table in tables_motor:
                for record in table.records:
                    dados_motor = {
                        "time": record.get_time(),
                        "current1": record.values.get("current1"),
                        "voltage1": record.values.get("voltage1"),
                        "rpm1": record.values.get("rpm1"),
                        "energy1": record.values.get("energy1"),
                        "power1": record.values.get("power1")
                    }

                    motor_data.append(dados_motor)
                    
            print(f"Total registos motor: {len(motor_data)}")

        except Exception as e:
            print(f"Erro ao buscar Motor1: {e}")
            
        # =========================
        # LEITURA MOTOR 2
        # =========================
        motor2_data = []

        try:
            print("A buscar dados do Motor2...")

            query_motor2 = f'''
            import "date"

            from(bucket: "{BUCKET}")
                {range_query}
                |> filter(fn: (r) => r["_measurement"] == "Motor2")
                |> filter(fn: (r) =>
                    r["_field"] == "current2" or
                    r["_field"] == "voltage2" or
                    r["_field"] == "rpm2" or
                    r["_field"] == "energy2" or
                    r["_field"] == "power2"
                )
                |> aggregateWindow(every: 20s, fn: last, createEmpty: false)
                |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
            '''

            tables_motor2 = query_api.query(query_motor2)

            for table in tables_motor2:
                for record in table.records:
                    dados_motor2 = {
                        "time": record.get_time(),
                        "current2": record.values.get("current2"),
                        "voltage2": record.values.get("voltage2"),
                        "rpm2": record.values.get("rpm2"),
                        "energy2": record.values.get("energy2"),
                        "power2": record.values.get("power2")
                    }

                    motor2_data.append(dados_motor2)

            print(f"Total registos Motor2: {len(motor2_data)}")

        except Exception as e:
            print(f"Erro ao buscar Motor2: {e}")

    except Exception as e:
        print(f"Erro geral: {e}")
        
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        
                
    df_new = pd.DataFrame(data)
    df_motor = pd.DataFrame(motor_data)
    
    print(f"Novos registos motor: {len(df_motor)}")

    print(df_motor.head())

    print(f"Novos registos encontrados: {len(df_new)}")

    if not df_new.empty:
        df_total = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_total = df_old.copy()
        
        
     # =========================
    # HISTÓRICO TOTAL MOTOR
    # =========================

    df_motor2 = pd.DataFrame(motor2_data)
    
    
        # ======= DEBUG =======
    print(f"--- DEBUG: Novos registros ---")

    # Sensores
    print(f"Novos registros sensores: {len(df_new)}")
    if not df_new.empty:
        print(df_new.head())

    # Motor1
    print(f"Novos registros Motor1: {len(df_motor)}")
    if not df_motor.empty:
        print(df_motor.head())

    # Motor2
    print(f"Novos registros Motor2: {len(df_motor2)}")
    if not df_motor2.empty:
        print(df_motor2.head())

    print(f"--- Fim do debug ---\n")

    if not df_motor.empty:
        df_motor_total = pd.concat([df_motor_old, df_motor], ignore_index=True)
    else:
        df_motor_total = df_motor_old.copy()

    if not df_motor2.empty:
        df_motor_total = pd.concat([df_motor_total, df_motor2], ignore_index=True)
        
        
        

    df_total = preparar_df(df_total)

    # =========================
    # PREPARAR MOTOR
    # =========================

    if not df_motor_total.empty:

        df_motor_total["time"] = pd.to_datetime(
            df_motor_total["time"],
            utc=True,
            errors="coerce"
        )

        df_motor_total = df_motor_total.dropna(subset=["time"])

        df_motor_total = df_motor_total.drop_duplicates(
            subset=["time"],
            keep="last"
        )

        df_motor_total = df_motor_total.sort_values("time")

    if not df_total.empty:
        df_total = df_total.drop_duplicates(
            subset=["measurement", "time"],
            keep="last"
        )
        df_total = df_total.sort_values("time")

    resultados = []
    today_date = date.today()

    for sensor in sensores:

        df_sensor = (
            df_total[df_total["measurement"] == sensor]
            if not df_total.empty
            else pd.DataFrame()
        )

        if df_sensor.empty:
            print(f"Sem dados para {sensor}")

            resultados.append(resultados_anteriores_luzes.get(sensor, {
                "sensor": sensor,
                "tempo_total_min": 0,
                "media_diaria_min": 0,
                "ativacoes_total": 0,
                "ativacoes_hoje": 0,
                "hora_pico": None,
                "tempo_medio_ativacao_s": 0,
                "alertas": [],
                "tempo_em_horas_das_luzes_ligadas_por_dia": {},
                "events_per_day": {},
                "hourly_usage": {},
                "insight": "Sem dados ainda"
            }))

            continue

        # =========================
        # TEMPO LIGADO
        # =========================

        tempo_em_horas_das_luzes_ligadas_por_dia = df_sensor.groupby("date")["duration_s"].sum()

        hourly_usage = df_sensor.groupby(["date", "hour"])["duration_s"].sum()

        total_time = df_sensor["duration_s"].sum()


        # =========================
        # ATIVAÇÕES CORRETAS
        # =========================
        # O campo "value" é um contador acumulado.
        # Por isso NÃO se soma diretamente o value.
        # Calcula-se a diferença entre leituras consecutivas.

        df_sensor = df_sensor.sort_values("time").copy()

        df_sensor["value_anterior"] = df_sensor["value"].shift(1)

        df_sensor["ativacoes_delta"] = (
            df_sensor["value"] - df_sensor["value_anterior"]
        )

        # Na primeira linha não sabemos o valor anterior, por isso fica 0
        df_sensor["ativacoes_delta"] = df_sensor["ativacoes_delta"].fillna(0)

        # Se houver reset do contador, a diferença pode ficar negativa.
        # Nesse caso não contamos como ativação.
        df_sensor.loc[
            df_sensor["ativacoes_delta"] < 0,
            "ativacoes_delta"
        ] = 0

        # Garantir que não há valores estranhos
        df_sensor["ativacoes_delta"] = pd.to_numeric(
            df_sensor["ativacoes_delta"],
            errors="coerce"
        ).fillna(0)


        # Ativações por dia agora usam o DELTA, não o value bruto
        events_per_day = df_sensor.groupby("date")["ativacoes_delta"].sum()

        # Total de ativações correto
        total_events = df_sensor["ativacoes_delta"].sum()

        avg_daily = (
            tempo_em_horas_das_luzes_ligadas_por_dia.mean()
            if not tempo_em_horas_das_luzes_ligadas_por_dia.empty
            else 0
        )

        today = tempo_em_horas_das_luzes_ligadas_por_dia.get(today_date, 0)

        ativacoes_hoje = int(
            events_per_day.get(today_date, 0)
        )

        avg_time_event = (
            total_time / total_events
            if total_events > 0
            else 0
        )

        alerts = []

        if avg_daily > 0 and today > avg_daily * 1.3:
            alerts.append("Consumo acima do normal")

            hora_pico = None

            if not hourly_usage.empty:

                _, hora_pico = hourly_usage.idxmax()

                madrugada_usage = df_sensor[
                    df_sensor["hour"] < 6
                ]["duration_s"].sum()

                total_usage = df_sensor[
                    "duration_s"
                ].sum()

                if (
                    total_usage > 0 and
                    (madrugada_usage / total_usage) > 0.2
                ):

                    alerts.append(
                        "Uso significativo durante madrugada"
                    )

        if total_events > 0 and avg_time_event < 5:
            alerts.append("Ativações muito curtas")

        hourly_dict = {}

        for (date_key, hour), value in hourly_usage.items():
            date_str = str(date_key)

            if date_str not in hourly_dict:
                hourly_dict[date_str] = {}

            hourly_dict[date_str][str(hour)] = round(value, 2)

        hoje = datetime.now().strftime("%Y-%m-%d")

        resultado = {
            "data_hoje": hoje,
            "sensor": sensor,
            "tempo_total_min": round(total_time / 60, 2),
            "media_diaria_min": round(avg_daily / 60, 2),
            "ativacoes_total": int(total_events),
            "ativacoes_hoje": ativacoes_hoje,
            "hora_pico": None,
            "tempo_medio_ativacao_s": round(avg_time_event, 2),
            "alertas": alerts,
            "tempo_em_horas_das_luzes_ligadas_por_dia": {str(k): round(v / 3600, 2)for k, v in tempo_em_horas_das_luzes_ligadas_por_dia.to_dict().items()},
            "events_per_day": {str(k): int(v) for k, v in events_per_day.to_dict().items()},
            "hourly_usage": hourly_dict,
            "insight": "Sem alterações relevantes"
        }

        
  

        dados_llm = {
            "sensor": sensor,
            "tempo_total_min": resultado["tempo_total_min"],
            "media_diaria_min": resultado["media_diaria_min"],
            "ativacoes_total": resultado["ativacoes_total"],
            "ativacoes_hoje": resultado["ativacoes_hoje"],
            "hora_pico": resultado["hora_pico"],
            "tempo_medio_ativacao_s": resultado["tempo_medio_ativacao_s"],
            "alertas": resultado["alertas"]
        }

        df_sensor_novo = (
            df_new[df_new["measurement"] == sensor]
            if not df_new.empty and "measurement" in df_new.columns
            else pd.DataFrame()
        )

        insight_antigo = resultados_anteriores_luzes.get(
            sensor,
            {}
        ).get(
            "insight",
            "Sem novos dados"
        )

        if not df_sensor_novo.empty:

            resultado["insight"] = gerar_insight(
                dados_llm
            )

        else:

            resultado["insight"] = insight_antigo
        resultados.append(resultado)

    # =========================
    # ANÁLISE DE MOTORES
    # =========================
    motores_resultados = []

    for motor_id in ["Motor1", "Motor2"]:
        df_motor_analise = df_motor_total[df_motor_total["time"].notna()].copy() if not df_motor_total.empty else pd.DataFrame()

        if motor_id == "Motor1":
            campos_motor = ["current1", "voltage1", "rpm1", "energy1", "power1"]
            df_motor_analise = df_motor_analise[df_motor_analise["current1"].notna() | df_motor_analise["voltage1"].notna() |
                                              df_motor_analise["rpm1"].notna() | df_motor_analise["energy1"].notna() |
                                              df_motor_analise["power1"].notna()]
        else:  # Motor2
            campos_motor = ["current2", "voltage2", "rpm2", "energy2", "power2"]
            df_motor_analise = df_motor_analise[df_motor_analise["current2"].notna() | df_motor_analise["voltage2"].notna() |
                                              df_motor_analise["rpm2"].notna() | df_motor_analise["energy2"].notna() |
                                              df_motor_analise["power2"].notna()]

        if df_motor_analise.empty:
            motores_resultados.append({
                "motor": motor_id,
                "status": "Sem dados",
                "insights": "Sem dados disponíveis para análise"
            })
            continue

        # Cálculos básicos
        stats_motor = {}
        for campo in campos_motor:
            if campo in df_motor_analise.columns:
                valores = pd.to_numeric(df_motor_analise[campo], errors='coerce').dropna()
                if not valores.empty:
                    stats_motor[campo] = {
                        "media": round(valores.mean(), 2),
                        "min": round(valores.min(), 2),
                        "max": round(valores.max(), 2),
                        "std": round(valores.std(), 2) if len(valores) > 1 else 0
                    }

        # Consumo energético
        consumo_total = 0
        if f"energy{motor_id[-1]}" in df_motor_analise.columns:
            energia_vals = pd.to_numeric(df_motor_analise[f"energy{motor_id[-1]}"], errors='coerce').dropna()
            if not energia_vals.empty:
                consumo_total = round(energia_vals.max() - energia_vals.min(), 2)


        dados_motor_llm = {
            "motor": motor_id,
            "estatisticas": stats_motor,
            "consumo_total_kwh": consumo_total,
            "registros_analisados": len(df_motor_analise),
            "periodo": {
                "inicio": df_motor_analise["time"].min().strftime("%Y-%m-%d %H:%M") if not df_motor_analise.empty else "N/A",
                "fim": df_motor_analise["time"].max().strftime("%Y-%m-%d %H:%M") if not df_motor_analise.empty else "N/A"
            }
        }

        insight_antigo_motor = None

        for antigo in resultados_anteriores_motores:

            if antigo.get("motor") == motor_id:

                insight_antigo_motor = antigo.get("insights")

                break

        if motor_id == "Motor1":

            tem_dados_novos_motor = not df_motor.empty

        else:

            tem_dados_novos_motor = not df_motor2.empty

        if tem_dados_novos_motor:

            insight_motor = gerar_insight(
                dados_motor_llm,
                "motor"
            )

        else:

            insight_motor = insight_antigo_motor or "Sem novos dados"

        motores_resultados.append({
            "motor": motor_id,
            "status": "Analisado",
            "estatisticas": stats_motor,
            "consumo_total_kwh": consumo_total,
            "insights": insight_motor
        })

    # =========================
    # ANÁLISE DE BOMBAS
    # =========================
    bombas_resultados = []

    pump_field = None
    for f in ["bar", "value"]:
        if f in df_bombas_total.columns:
            pump_field = f
            break

    cost_field = None
    for f in ["Custo_Energy", "custo_energy", "cost", "money", "price"]:
        if f in df_bombas_total.columns:
            cost_field = f
            break

    if not df_bombas_total.empty and pump_field is not None and not df_bombas_total[pump_field].isna().all():
        df_bombas_analise = df_bombas_total.dropna(subset=[pump_field]).copy()

        df_bombas_analise[pump_field] = pd.to_numeric(df_bombas_analise[pump_field], errors="coerce")

        pressao_stats = {
            "media": round(df_bombas_analise[pump_field].mean(), 2),
            "min": round(df_bombas_analise[pump_field].min(), 2),
            "max": round(df_bombas_analise[pump_field].max(), 2),
            "std": round(df_bombas_analise[pump_field].std(), 2) if len(df_bombas_analise) > 1 else 0,
            "field": pump_field
        }

        custos_stats = None
        if cost_field and cost_field in df_bombas_analise.columns:
            df_bombas_analise[cost_field] = pd.to_numeric(df_bombas_analise[cost_field], errors="coerce")
            custo_valores = df_bombas_analise[cost_field].dropna()
            if not custo_valores.empty:
                custos_stats = {
           
                    "media": round(custo_valores.mean(), 2),
                    "min": round(custo_valores.min(), 2),
                    "max": round(custo_valores.max(), 2),
                    "std": round(custo_valores.std(), 2) if len(custo_valores) > 1 else 0,
                    "consumo_total": round(custo_valores.sum(), 2),
                    "field": cost_field
                }

        # Estabilidade da pressão
        variacao_pressao = pressao_stats["max"] - pressao_stats["min"]
        estabilidade = "Estável" if variacao_pressao < 0.5 else "Variável" if variacao_pressao < 2 else "Muito variável"

        # Pressão por hora do dia
        df_bombas_analise["hour"] = df_bombas_analise["time"].dt.hour
        pressao_horaria = df_bombas_analise.groupby("hour")[pump_field].mean()

        dados_bombas_llm = {
           "bomba": "Bombas / Sistema de Pressão",
            "campo_pressao": pump_field,
            "estatisticas_pressao": pressao_stats,
            "estatisticas_custo": custos_stats,
            "estabilidade": estabilidade,
            "variacao_total": round(variacao_pressao, 2),
            "pressao_por_hora": {f"{hora}h": round(val, 2) for hora, val in pressao_horaria.items()},
            "registros_analisados": len(df_bombas_analise),
            "periodo": {
                "inicio": df_bombas_analise["time"].min().strftime("%Y-%m-%d %H:%M") if not df_bombas_analise.empty else "N/A",
                "fim": df_bombas_analise["time"].max().strftime("%Y-%m-%d %H:%M") if not df_bombas_analise.empty else "N/A"
            }
        }

        insight_bombas = gerar_insight(dados_bombas_llm, "bomba") if not df_bombas_analise.empty else "Sem dados suficientes"

        bomba_output = {
            "bomba": "Sistema de Pressão",
            "status": "Analisado",
            "estatisticas_pressao": pressao_stats,
            "estabilidade": estabilidade,
            "insights": insight_bombas
        }
        if custos_stats is not None:
            bomba_output["estatisticas_custo"] = custos_stats
            bomba_output["custo_field"] = cost_field

        bombas_resultados.append(bomba_output)
    else:
        bombas_resultados.append({
            "bomba": "Sistema de Pressão",
            "status": "Sem dados",
            "insights": "Sem dados disponíveis para análise"
        })

    # =========================
    # GUARDAR RESULTADOS EXPANDIDOS
    # =========================
    resultados_expandidos = {
        "iluminacao": resultados,
        "motores": motores_resultados,
        "bombas": bombas_resultados,
        "timestamp_analise": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # =========================
    # GUARDAR RESULTADOS
    # =========================
    with open(RESULTADOS_FILE, "w", encoding="utf-8") as f:
        json.dump(resultados_expandidos, f, indent=2, ensure_ascii=False)

    # =========================
    # ATUALIZAR TIMESTAMP (CORRETO)
    # =========================
    previous_last_time = get_last_time()

    if previous_last_time != "-30d":
        prev_time = pd.to_datetime(previous_last_time, utc=True)
    else:
        prev_time = None

    times = []

    if not df_new.empty:
        times.append(pd.to_datetime(df_new["time"], utc=True).max())

    if not df_motor.empty:
        times.append(pd.to_datetime(df_motor["time"], utc=True).max())
        
    if not df_motor2.empty:
        times.append(pd.to_datetime(df_motor2["time"], utc=True).max())

    if bombas_data:
        times.append(pd.to_datetime([r["time"] for r in bombas_data], utc=True).max())

    if times:
        new_time = max(times)
    else:
        new_time = prev_time

    if prev_time is None:
        final_time = new_time
    else:
        final_time = max(prev_time, new_time)

    if final_time is not None:
        final_time = pd.to_datetime(final_time, utc=True)
        final_time_str = final_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_time": final_time_str}, f)

        print("Novo timestamp guardado:", final_time_str)

    # =========================
    # GUARDAR HISTÓRICO
    # =========================
    if not df_total.empty:
        temp_file = HISTORICO_FILE + ".tmp"
        df_total.to_parquet(temp_file, index=False)
        os.replace(temp_file, HISTORICO_FILE)
        
        
        # =========================
        # GUARDAR HISTÓRICO MOTOR
        # =========================

    if not df_motor_total.empty:

        temp_motor_file = MOTOR_HISTORICO_FILE + ".tmp"

        df_motor_total.to_parquet(
            temp_motor_file,
            index=False
        )

        os.replace(
            temp_motor_file,
            MOTOR_HISTORICO_FILE
        )

        print("Histórico motor atualizado!")

    df_bombas = pd.DataFrame(bombas_data)
    if not df_bombas.empty:
        df_bombas["time"] = pd.to_datetime(df_bombas["time"], utc=True, errors="coerce")
        df_bombas = df_bombas.dropna(subset=["time"])
        df_bombas = df_bombas.drop_duplicates(subset=["time"], keep="last")
        df_bombas = df_bombas.sort_values("time")

        # Concatenar com histórico anterior
        if not df_bombas_old.empty:
            df_bombas_total = pd.concat([df_bombas_old, df_bombas], ignore_index=True)
        else:
            df_bombas_total = df_bombas.copy()

        # Remove duplicatas e salva
        if not df_bombas_total.empty:
            df_bombas_total = df_bombas_total.drop_duplicates(subset=["time"], keep="last")
            temp_bombas_file = BOMBAS_HISTORICO_FILE + ".tmp"
            df_bombas_total.to_parquet(temp_bombas_file, index=False)
            os.replace(temp_bombas_file, BOMBAS_HISTORICO_FILE)
            print("Histórico bombas atualizado!")
            
    print("Atualizado!")

    return not df_new.empty
