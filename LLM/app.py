import streamlit as st
import json
import pandas as pd
import os
import subprocess
import datetime
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Image
import tempfile
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from industrial_chat import (perguntar_llm, gerar_contexto
)
   
pdf_bytes = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
    
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title=" SCADA Inteligente",
    layout="wide"
)



#Botao para resetar o tempo total 
if "reset_tempo" not in st.session_state or not isinstance(st.session_state.reset_tempo, dict):
    st.session_state.reset_tempo = {"date": None, "value": 0}
    
if "reset_ativacoes" not in st.session_state or not isinstance(st.session_state.reset_ativacoes, dict):
    st.session_state.reset_ativacoes = {"date": None, "value": 0}





# =========================
# CSS GLOBAL
# =========================
st.markdown("""
<style>
    .stApp {
        background-color: #F7F9FB;
    }

    .main-title {
        font-size: 36px;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0;
    }

    .subtitle {
        font-size: 18px;
        color: #6B7280;
        margin-top: 0;
        margin-bottom: 25px;
    }

    .card {
        background-color: white;
        padding: 22px;
        border-radius: 16px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.06);
        border: 1px solid #E5E7EB;
    }

    .kpi-title {
        font-size: 14px;
        color: #6B7280;
        margin-bottom: 8px;
    }

    .kpi-value {
        font-size: 30px;
        font-weight: 700;
        color: #111827;
    }

    .alert-warning {
        background-color: #FEF3C7;
        border-left: 6px solid #F59E0B;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        color: #92400E;
        font-weight: 500;
    }

    .alert-error {
        background-color: #FEE2E2;
        border-left: 6px solid #DC2626;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        color: #991B1B;
        font-weight: 500;
    }

    .alert-success {
        background-color: #DCFCE7;
        border-left: 6px solid #16A34A;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        color: #166534;
        font-weight: 500;
    }

    .insight-box {
        background-color: white;
        padding: 22px;
        border-radius: 16px;
        border: 1px solid #E5E7EB;
        box-shadow: 0 4px 14px rgba(0,0,0,0.06);
        font-size: 16px;
        line-height: 1.6;
        color: #374151;
    }

    .section-title {
        font-size: 22px;
        font-weight: 700;
        color: #111827;
        margin-top: 20px;
        margin-bottom: 15px;
    }

    div[data-testid="stMetric"] {
        background-color: white;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.06);
        border: 1px solid #E5E7EB;
    }
</style>
""", unsafe_allow_html=True)

# =========================
# FUNÇÕES AUXILIARES
# =========================
def kpi_card(title, value):
    st.markdown(f"""
    <div class="card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)


def alert_card(message, level="warning"):
    css_class = "alert-warning"

    if level == "error":
        css_class = "alert-error"
    elif level == "success":
        css_class = "alert-success"

    # Remova a linha abaixo que insere o ícone
    st.markdown(f"""
    <div class="{css_class}">
        {message}  <!-- Apenas exibe a mensagem -->
    </div>
    """, unsafe_allow_html=True)

def preparar_daily_usage(data):

    df = pd.DataFrame(
        list(
            data.get(
                "tempo_em_horas_das_luzes_ligadas_por_dia",
                {}
            ).items()
        ),
        columns=["Data", "Tempo (h)"]
    )

    if df.empty:
        return df

    df["Data"] = pd.to_datetime(
        df["Data"],
        errors="coerce"
    )

    df = df.sort_values("Data")

    df["Tempo formatado"] = df["Tempo (h)"].apply(
        lambda h: f"{round(h, 2)} h"
    )

    return df


def preparar_events_per_day(data):
    df = pd.DataFrame(
        list(data.get("events_per_day", {}).items()),
        columns=["Data", "Ativações"]
    )

    if df.empty:
        return df

    df["Data"] = pd.to_datetime(df["Data"])
    df = df.sort_values("Data")

    return df


def preparar_hourly_usage(data, selected_date):
    hourly = data.get("hourly_usage", {})

    date_str = str(selected_date)

    if date_str not in hourly:
        return pd.DataFrame()

    df = pd.DataFrame(
        list(hourly[date_str].items()),
        columns=["Hora", "Tempo (s)"]
    )

    df["Hora"] = pd.to_numeric(df["Hora"])
    df = df.sort_values("Hora")
    df["Tempo (min)"] = df["Tempo (s)"] / 60

    return df


# =========================
# HEADER
# =========================
st.markdown('<h1 class="main-title">💡 Analysis</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Smart monitoring of lighting, consumption and usage patterns.</p>',
    unsafe_allow_html=True
)

# =========================
# CONTROLOS
# =========================
# =========================
# MINI CHAT INDUSTRIAL
# =========================

st.markdown("---")

st.markdown("## 🤖 Smart Industrial Assistant")

if "chat_resposta" not in st.session_state:
    st.session_state.chat_resposta = ""

with st.form("chat_form", clear_on_submit=False):

    pergunta = st.text_input(
        "Faz uma pergunta sobre o sistema"
    )

    submitted = st.form_submit_button("Perguntar")

    if submitted:

        # Desliga auto-refresh enquanto o mini chat responde
        st.session_state.auto_refresh = False

        contexto = gerar_contexto(
            pergunta
        )

        with st.spinner("A analisar dados..."):

            st.session_state.chat_resposta = perguntar_llm(
                pergunta,
                contexto,
                st.session_state.chat_history
            )

if st.session_state.chat_resposta:

    st.markdown("### Resposta")

    st.write(st.session_state.chat_resposta)


control_col1, control_col2, control_col2 = st.columns([1,1,1])

with control_col1:
    auto_refresh = st.toggle(
        "Auto-refresh",
        key="auto_refresh"
    )
    
with control_col2:
    gerar_pdf = st.button("📄 Generate PDF")
    pdf_placeholder = control_col2.empty()

# =========================
# Botao de download do PDF (placeholder, será atualizado após gerar o relatório)
# =========================

   

if auto_refresh:
    st_autorefresh(interval=180000, key="datarefresh")

# =========================
# CARREGAR DADOS
# =========================
if not os.path.exists("resultados.json"):
    st.warning("Waiting for data in `resultados.json`...")
    st.stop()

with open("resultados.json", encoding="utf-8") as f:
    dados_json = json.load(f)
    
    # Se for um dicionário, extrair a lista de iluminação
    if isinstance(dados_json, dict):
        dados = dados_json.get("iluminacao", [])
    else:
        # Se for uma lista, usar diretamente
        dados = dados_json

    nomes_alterados = {
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
    }

if not isinstance(dados, list) or len(dados) == 0:
    st.error("The `resultados.json` file does not contain a valid list of sensors.")
    st.stop()


# =========================
# ÚLTIMA ATUALIZAÇÃO
# =========================

mod_time = os.path.getmtime("resultados.json")
last_update = datetime.datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M:%S")
st.caption(f"Last update: {last_update}")

# =========================
# SELEÇÃO DE SENSOR
# =========================


def gerar_relatorio(
    data,
    df_daily,
    df_events,
    df_hour,
    start_date,
    end_date,
    selected_date
):
    styles = getSampleStyleSheet()
    
    # Ajustes finos nos estilos de texto
    styles["Title"].fontSize = 18
    styles["Title"].spaceAfter = 12
    styles["Heading2"].fontSize = 14
    styles["Heading2"].spaceAfter = 10
    styles["Heading3"].fontSize = 12
    styles["Heading3"].spaceAfter = 8
    styles["BodyText"].fontSize = 10

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        doc = SimpleDocTemplate(
            tmp_pdf.name,
            pagesize=A4,
            leftMargin=50,
            rightMargin=50,
            topMargin=50,
            bottomMargin=50
        )

        elements = []

        # =========================
        # HEADER
        # =========================

        sensor_name = nomes_alterados.get(data.get('sensor', 'N/A'), data.get('sensor', 'N/A'))
        elements.append(Paragraph("<b>SCADA Smart Consumption Report</b>", styles["Title"]))
        elements.append(Paragraph(f"<b>Sensor:</b> {sensor_name}", styles["BodyText"]))
        elements.append(Paragraph(f"<b>Generated on:</b> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["BodyText"]))
        
        
        elements.append(
    Paragraph(
        f"<b>Analyzed period:</b> {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}",
        styles["BodyText"]
    )
)

        elements.append(
            Paragraph(
                f"<b>Hourly analysis day:</b> {selected_date.strftime('%d/%m/%Y')}",
                styles["BodyText"]
            )
        )
        
        
        
        
        
        
        elements.append(Spacer(1, 20))

        # =========================
        # KPIs (TABELA COMPACTA)
        # =========================
        elements.append(Paragraph("<b>Main indicators</b>", styles["Heading3"]))
        
        # Definimos larguras fixas em pontos para evitar que a tabela estique (ex: 150 e 80)
        kpi_data = [
            ["Metric", "Value"],
            ["Total time", f"{data.get('tempo_total_min', 0)} min"],
            ["Daily average", f"{data.get('media_diaria_min', 0)} min"],
            ["Activations today", f"{data.get('ativacoes_hoje', 0)} uni."],
            ["Peak hour", f"{data.get('hora_pico', '-')}h"],
        ]

        table_kpi = Table(kpi_data, colWidths=[150, 80], hAlign='LEFT')
        table_kpi.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")), # Cabeçalho cinza claro
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),    # Espaço interno reduzido
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4), # Espaço interno reduzido
        ]))
        elements.append(table_kpi)
        elements.append(Spacer(1, 15))

        # =========================
        # INSIGHT E ALERTAS
        # =========================
        # elements.append(Paragraph("<b>Análise e Alertas</b>", styles["Heading3"]))
        # insight_text = data.get("insight", "Sem análise disponível.")
        # elements.append(Paragraph(f"<i>Insight:</i> {insight_text}", styles["BodyText"]))
        
        # if data.get("alertas"):
        #     for alerta in data["alertas"]:
        #         elements.append(Paragraph(f"• {alerta}", styles["BodyText"]))
        # else:
        #     elements.append(Paragraph("• Sem alertas relevantes.", styles["BodyText"]))
        
        # elements.append(Spacer(1, 15))

        # =========================
        # TABELAS DE USO (LARGURA CONTROLADA)
        # =========================
        
        # Função interna para criar tabelas de dados com estilo padronizado
        def criar_tabela_dados(lista_dados, col_widths):
            t = Table(lista_dados, colWidths=col_widths, hAlign='LEFT')
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ALIGN", (1, 0), (1, -1), "CENTER"), # Centraliza valores numéricos
            ]))
            return t

        # Uso Diário
        elements.append(Paragraph("<b>Daily Usage History</b>", styles["Heading3"]))
        dados_daily = [["Date", "Time (h)"]] + [
            [str(row["Data"].date()), round(row["Tempo (h)"], 2)]
            for _, row in df_daily.iterrows()
        ]
        elements.append(criar_tabela_dados(dados_daily, [100, 100]))
        elements.append(Spacer(1, 12))

        # Ativações
        elements.append(Paragraph("<b>Activations per Day</b>", styles["Heading3"]))
        dados_events = [["Date", "Activations"]] + [
            [str(row["Data"].date()), int(row["Ativações"])]
            for _, row in df_events.iterrows()
        ]
        elements.append(criar_tabela_dados(dados_events, [100, 100]))
        elements.append(Spacer(1, 12))

        # Distribuição Horária
        elements.append(Paragraph("<b>Hourly Distribution</b>", styles["Heading3"]))
        dados_hour = [["Hour", "Time (min)"]] + [
            [f"{int(row['Hora']):02d}:00", round(row["Tempo (min)"], 2)]
            for _, row in df_hour.iterrows()
        ]
        elements.append(criar_tabela_dados(dados_hour, [80, 120]))

        # =========================
        # CONSTRUÇÃO FINAL
        # =========================
        doc.build(elements)

        with open(tmp_pdf.name, "rb") as f:
            return f.read()




st.markdown('<div class="section-title">Select sensor</div>', unsafe_allow_html=True)

sensores_raw = [d["sensor"] for d in dados]

# Converter para nomes amigáveis
sensores_ui = [nomes_alterados.get(s, s) for s in sensores_raw]

# Mostrar na UI
sensor_ui = st.selectbox("Sensor", sensores_ui)

# Converter de volta para o nome original
sensor = sensores_raw[sensores_ui.index(sensor_ui)]

# Buscar dados
data = next(d for d in dados if d["sensor"] == sensor)

df_daily = preparar_daily_usage(data)
df_events = preparar_events_per_day(data)




# =========================
# CONTEXTO TEMPORAL
# =========================
datas = sorted(data.get("tempo_em_horas_das_luzes_ligadas_por_dia",{}).keys())


if datas:
    st.info(f"Data available between **{datas[0]}** and **{datas[-1]}**")


st.markdown('<div class="section-title">Select analysis day</div>', unsafe_allow_html=True)

selected_date = st.date_input(
    "Day",
    value=pd.to_datetime(datas[-1]).date() if datas else datetime.date.today()
)

# =========================
# KPIS
# =========================
st.markdown('<div class="section-title">Main Indicators</div>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)

with k1:
    df_daily["Data"] = pd.to_datetime(
    df_daily["Data"],
    errors="coerce"
)

    df_filtrado = df_daily[
        df_daily["Data"].dt.date == selected_date

    ]["Tempo (h)"]

    tempo_real = (df_filtrado.values[0]if not df_filtrado.empty else 0)

    # reset por dia
    if st.session_state.reset_tempo["date"] != selected_date:
        reset_val = 0
    else:
        reset_val = st.session_state.reset_tempo["value"]

    tempo_visivel = tempo_real - reset_val

    total_minutos = int(round(tempo_visivel * 60))
    horas = total_minutos // 60
    minutos = total_minutos % 60

    texto = f"{horas}h {minutos}min"

    col_kpi, col_btn = st.columns([4,1])

    with col_kpi:
        kpi_card("Total time on", texto)

    with col_btn:
        if st.button("↺", key="reset_tempo_btn"):
            st.session_state.reset_tempo = {
                "date": selected_date,
                "value": tempo_real
            }
with k2:
    media_horas = data.get("media_diaria_min", 0) / 60

    total_minutos_media = int(round(media_horas * 60))
    horas_media = total_minutos_media // 60
    minutos_media = total_minutos_media % 60

    texto_media = f"{horas_media}h {minutos_media}min/dia"

    kpi_card("Daily average", texto_media)

with k3:
    # obter ativações do dia selecionado
    ativacoes_dia = df_events[
        df_events["Data"].dt.date == selected_date
    ]["Ativações"]

    ativacoes_real = int(ativacoes_dia.values[0]) if not ativacoes_dia.empty else 0

    # garantir estrutura no session_state
    if "reset_ativacoes" not in st.session_state:
        st.session_state.reset_ativacoes = {"date": None, "value": 0}

    # se mudou o dia → reset automático
    if st.session_state.reset_ativacoes["date"] != selected_date:
        reset_val = 0
    else:
        reset_val = st.session_state.reset_ativacoes["value"]

    ativacoes_visivel = ativacoes_real - reset_val

    # UI
    col_kpi, col_btn = st.columns([3,1])

    with col_kpi:
        kpi_card("Activations today", ativacoes_visivel)

    with col_btn:
        if st.button("↺", key="reset_ativacoes_btn"):
            st.session_state.reset_ativacoes = {
                "date": selected_date,
                "value": ativacoes_real
            }

with k4:
    # calcular hora de pico com base no dia selecionado
  
    df_hour_kpi = preparar_hourly_usage(data, selected_date)

    if not df_hour_kpi.empty:
        hora_pico_dia = int(df_hour_kpi.loc[df_hour_kpi["Tempo (min)"].idxmax()]["Hora"])
    else:
        hora_pico_dia = None

    with k4:
        kpi_card(
            "Peak hour",
            f"{hora_pico_dia}h" if hora_pico_dia is not None else "-"
        )

# =========================
# ALERTAS + INSIGHT
# =========================
st.markdown('<div class="section-title">Status and smart analysis</div>', unsafe_allow_html=True)

alert_col, insight_col = st.columns([1, 2])

with alert_col:
    st.markdown("Alerts")

    alertas = data.get("alertas", [])

    if alertas:
        for alerta in alertas:
            texto = alerta.lower()

            if "alto" in texto or "acima" in texto or "madrugada" in texto:
                alert_card(alerta, "error")
            else:
                alert_card(alerta, "warning")
    else:
        alert_card("No relevant alerts for this sensor.", "success")


st.markdown("#### Smart insight")

insight = data.get("insight", "No insight available.")

st.markdown(f"""
<div class="insight-box">
    {insight}
</div>
""", unsafe_allow_html=True)

# =========================
# PREPARAR DATAFRAMES
# =========================







# =========================
# GRÁFICO 1 — USO DIÁRIO
# =========================

st.markdown('<div class="section-title">Range for trend analysis</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input("Start date", df_daily["Data"].min().date())

with col2:
    end_date = st.date_input("End date", df_daily["Data"].max().date())

df_daily_filtered = df_daily[
    (df_daily["Data"].dt.date >= start_date) &
    (df_daily["Data"].dt.date <= end_date)
]
st.markdown('<div class="section-title">Daily usage</div>', unsafe_allow_html=True)

df_events_filtered = df_events[
    (df_events["Data"].dt.date >= start_date) &
    (df_events["Data"].dt.date <= end_date)
]



if df_daily.empty:
    st.warning("No historical data for this sensor.")
    st.stop()

df_hour_pdf = preparar_hourly_usage(
    data,
    selected_date
)


if gerar_pdf:

    pdf_bytes = gerar_relatorio(
        data,
        df_daily_filtered,
        df_events_filtered,
        df_hour_pdf,
        start_date,
        end_date,
        selected_date
    )

    pdf_placeholder.download_button(
        label="📄 Download PDF",
        data=pdf_bytes,
        file_name="relatorio_scada.pdf",
        mime="application/pdf"
    )

fig_daily = px.line(
    df_daily_filtered,
    x="Data",
    y="Tempo (h)",
    markers=True,
    title="Evolution of time on per day",
    hover_data={
        "Tempo formatado": True,
        "Tempo (h)": False
    }
)

fig_daily.update_layout(
    template="simple_white",
    height=430,
    margin=dict(l=30, r=30, t=60, b=30),
    xaxis_title="Day",
    yaxis_title="Time on (h)"
)

fig_daily.update_traces(line_width=3)

st.plotly_chart(fig_daily, use_container_width=True)

# =========================
# GRÁFICOS 2 E 3
# =========================
graph_col1, graph_col2 = st.columns(2)

with graph_col1:
    st.markdown('<div class="section-title">Activations per day</div>', unsafe_allow_html=True)

    if not df_events_filtered.empty:
        df_events["Data_label"] = df_events["Data"].dt.strftime("%d/%m")

        fig_events = px.bar(
            df_events,
            x="Data_label",
            y="Ativações",
            title="Number of activations per day"
        )

        fig_events.update_layout(
            template="simple_white",
            height=390,
            margin=dict(l=30, r=30, t=60, b=60),
            xaxis_title="Day",
            yaxis_title="Activations",
            xaxis=dict(
                type="category",
                tickangle=0
            )
        )

        fig_events.update_traces(width=0.45)

        st.plotly_chart(fig_events, use_container_width=True)

    else:
        st.info("No data on activations per day.")

with graph_col2:
    st.markdown('<div class="section-title">Usage per hour of the day</div>', unsafe_allow_html=True)

    df_hour = preparar_hourly_usage(data, selected_date)

   
  

    if not df_hour.empty:
        fig_hour = px.bar(
            df_hour,
            x="Hora",
            y="Tempo (min)",
            title=f"Usage on day {selected_date}"
        )

        fig_hour.update_layout(
            template="simple_white",
            height=390,
            margin=dict(l=30, r=30, t=60, b=30),
            xaxis_title="Hour of the day",
            yaxis_title="Time on (min)",
            xaxis=dict(dtick=1)
        )

        st.plotly_chart(fig_hour, use_container_width=True)

    else:
        st.info("No hourly data for this day.")



# =========================
# MÉTRICAS DETALHADAS
# =========================
st.markdown('<div class="section-title">Detailed metrics</div>', unsafe_allow_html=True)

detail_col1, detail_col2, detail_col3 = st.columns(3)

with detail_col1:
    total_ativacoes = int(df_events_filtered["Ativações"].sum())

    kpi_card(
        "Total activations",
        total_ativacoes
    )
    
with detail_col2:
    kpi_card(
        "Average time per activation",
        f"{data.get('tempo_medio_ativacao_s', 0)} s"
    )

with detail_col3:
    if not df_daily.empty:
        max_day = df_daily.loc[df_daily["Tempo (h)"].idxmax()]
        
    kpi_card(
            "Day with highest usage",
            f"{max_day['Data'].strftime('%Y-%m-%d')}"
        )
        
# =========================
# DEBUG
# =========================
with st.expander("View complete data"):
    st.json(data)