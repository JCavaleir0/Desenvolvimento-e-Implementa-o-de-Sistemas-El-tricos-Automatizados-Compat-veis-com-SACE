import os
import pandas as pd
import numpy as np
import datetime
import plotly.express as px
import plotly.graph_objects as go
from reportlab.lib import styles
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import json
import re
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import tempfile
from industrial_chat import perguntar_llm, gerar_contexto

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(page_title="SCADA Motores", layout="wide")


if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "chat_resposta" not in st.session_state:
    st.session_state.chat_resposta = ""

if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False

# =========================
# CSS
# =========================
st.markdown("""
<style>
.stApp { background-color: #F7F9FB; }
.card { background-color: white; padding: 20px; border-radius: 16px; box-shadow: 0 4px 14px rgba(0,0,0,0.06); border: 1px solid #E5E7EB; }
.kpi-title { font-size: 14px; color: #6B7280; margin-bottom: 8px; }
.kpi-value { font-size: 28px; font-weight: 700; color: #111827; }
.alert-warning { background-color: #FEF3C7; border-left: 6px solid #F59E0B; padding: 15px; border-radius: 10px; margin-bottom: 10px; color: #92400E; font-weight: 500; }
.alert-error { background-color: #FEE2E2; border-left: 6px solid #DC2626; padding: 15px; border-radius: 10px; margin-bottom: 10px; color: #991B1B; font-weight: 500; }
.section-title { font-size: 22px; font-weight: 700; color: #111827; margin-top: 20px; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

# =========================
# FUNÇÕES AUXILIARES
# =========================
def kpi_card(title, value):
    st.markdown(f"<div class='card'><div class='kpi-title'>{title}</div><div class='kpi-value'>{value}</div></div>", unsafe_allow_html=True)

def alert_card(message, level="warning"):
    css_class = "alert-warning" if level=="warning" else "alert-error"
    st.markdown(f'<div class="{css_class}">{message}</div>', unsafe_allow_html=True)

# =========================
# FUNÇÕES DE DADOS
# =========================
def carregar_dados_historicos(file_path="motor_historico.parquet"):
    """Carrega histórico real do motor"""
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        df = pd.read_parquet(file_path)
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        return df
    return pd.DataFrame()

def safe_val(df, col):
    """Extrai valor do último registro ou retorna 0"""
    if col in df.columns and not df[col].empty:
        val = df[col].iloc[-1]
        return float(val) if pd.notnull(val) else 0
    return 0


def safe_val_any(df, cols):
    for col in cols:
        if col in df.columns and not df[col].empty:
            val = df[col].iloc[-1]
            return float(val) if pd.notnull(val) else 0
    return 0


def first_existing_column(df, cols):
    for col in cols:
        if col in df.columns:
            return col
    return None


def clean_insight_text(text):
    if not isinstance(text, str):
        return ""
    text = text.replace("***", "")
    text = re.sub(r"\*\*|\*|`|#|\|", "", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()


def format_insight_paragraph(text):
    cleaned = clean_insight_text(text)
    cleaned = cleaned.replace("\n\n", "<br/><br/>")
    cleaned = cleaned.replace("\n", "<br/>")
    return cleaned


def calcular_kpis(df_motor, motor_suffix="1"):
    if df_motor.empty:
        return {}
    kpis = {
        "Current": safe_val(df_motor, f"current{motor_suffix}"),
        "Voltage": safe_val(df_motor, f"voltage{motor_suffix}"),
        "RPM": safe_val(df_motor, f"rpm{motor_suffix}"),
        "Power": safe_val(df_motor, f"power{motor_suffix}")
    }
    kpis["PF"] = kpis["Power"] / (kpis["Voltage"] * kpis["Current"]) if kpis["Voltage"]*kpis["Current"] != 0 else 0
    kpis["Efficiency"] = kpis["RPM"] / kpis["Power"] if kpis["Power"] != 0 else 0
    return kpis

def plot_trend(df_motor, motor_suffix="1", motor_id="Motor 1", selected_date=None):
    if df_motor.empty:
        st.info("No data for trend chart.")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_motor["time"], y=df_motor[f"power{motor_suffix}"], name=f"{motor_id} Power (kW)", line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=df_motor["time"], y=df_motor[f"rpm{motor_suffix}"], name=f"{motor_id} RPM", line=dict(color='red'), yaxis="y2"))
    date_label = f" - {selected_date}" if selected_date is not None else ""
    fig.update_layout(title=f"Trend Power x RPM - {motor_id}{date_label}", xaxis_title="Hora",
                      xaxis=dict(type='date', tickformat='%H:%M'),
                      yaxis=dict(title="Power (kW)", color='blue'),
                      yaxis2=dict(title="RPM", overlaying='y', side='right', color='red'),
                      template="simple_white", height=400)
    st.plotly_chart(fig, width='stretch')

def plot_scatter(df_motor, motor_suffix="1", motor_id="Motor 1"):
    if df_motor.empty:
        st.info("No data for scatter plot.")
        return
    fig = px.scatter(df_motor, x=f"voltage{motor_suffix}", y=f"current{motor_suffix}", color=f"rpm{motor_suffix}",
                     title=f"Voltage vs Current - {motor_id}",
                     labels={f"voltage{motor_suffix}":"Voltage (V)", f"current{motor_suffix}":"Current (A)", f"rpm{motor_suffix}":"RPM"})
    st.plotly_chart(fig, width='stretch')

def plot_energy(df_motor, motor_suffix="1", motor_id="Motor 1", selected_date=None):
    if df_motor.empty:
        st.info("No data for energy chart.")
        return
    
    if selected_date:
        # Para um dia específico, mostrar por hora
        df_motor['hour'] = df_motor['time'].dt.hour
        df_hourly = df_motor.groupby('hour')[f"energy{motor_suffix}"].sum().reset_index()
        df_hourly['hour'] = df_hourly['hour'].astype(str)
        
        fig = px.bar(df_hourly, x='hour', y=f"energy{motor_suffix}",
                     title=f"Accumulated Energy per Hour - {motor_id} ({selected_date})",
                     labels={'hour':'Hour', f"energy{motor_suffix}":"Energy (kWh)"})
        fig.update_layout(xaxis_title='Hour', xaxis=dict(type='category'))
    else:
        # Extrair só a data
        df_motor['date'] = df_motor['time'].dt.date
        df_daily = df_motor.groupby('date')[f"energy{motor_suffix}"].sum().reset_index()
        
        # Converter para string (YYYY-MM-DD)
        df_daily['date'] = df_daily['date'].astype(str)
        
        # Criar gráfico
        fig = px.bar(df_daily, x='date', y=f"energy{motor_suffix}",
                     title=f"Accumulated Energy per Day - {motor_id}",
                     labels={'date':'Date', f"energy{motor_suffix}":"Energy (kWh)"})
        
        # Ajustar layout para não mostrar hora
        fig.update_layout(
            xaxis_title='Date',
            xaxis=dict(type='category')
        )
    
    # Mostrar gráfico
    st.plotly_chart(fig, width='stretch')

def checar_alertas(df_motor, motor_suffix="1"):
    if df_motor.empty:
        st.info("No alerts available.")
        return
    latest = df_motor.iloc[-1]
    current = latest.get(f"current{motor_suffix}", 0)
    rpm = latest.get(f"rpm{motor_suffix}", 0)
    power = latest.get(f"power{motor_suffix}", 0)
    if current > 50:
        alert_card("Current above 50A!", level="error")
    if rpm < 500 and power > 5:
        alert_card("Low RPM with high Power - possible blockage!", level="error")


def gerar_relatorio_motor_bomba(
    motor_sel,
    df_motor_full,
    df_motor,
    motor_suffix,
    kpis,
    df_bombas_full,
    dados_motores,
    dados_bombas,
    selected_date=None
):
    styles = getSampleStyleSheet()
    styles["Title"].fontSize = 18
    styles["Title"].spaceAfter = 12
    styles["Heading2"].fontSize = 14
    styles["Heading2"].spaceAfter = 10
    styles["Heading3"].fontSize = 12
    styles["Heading3"].spaceAfter = 8
    styles["BodyText"].fontSize = 10

    def criar_tabela(lista, col_widths):
        tabela = Table(lista, colWidths=col_widths, hAlign="LEFT")
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return tabela

    motors_info = [m for m in dados_motores if m.get("motor") in {"Motor1", "Motor 1", "Motor2", "Motor 2"}]
    motors_info.sort(key=lambda m: m.get("motor", ""))
    bomba_info = dados_bombas[0] if isinstance(dados_bombas, list) and len(dados_bombas) > 0 else None

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
        elements.append(Paragraph("Comparative Report of Motors and Pump", styles["Title"]))
        elements.append(Paragraph(f"Mode: {motor_sel}", styles["BodyText"]))
        elements.append(Paragraph(f"Generated on: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["BodyText"]))
        elements.append(Spacer(1, 12))

        if motors_info:
            elements.append(Paragraph("<b>Motor Comparison</b>", styles["Heading2"]))
            header = [["Motor", "Consumption (kWh)", "Status"]]
            rows = header + [
                [
                    m.get("motor", "N/A"),
                    f"{m.get('consumo_total_kwh', 0):.2f}",
                    m.get('status', "N/A")
                ]
                for m in motors_info
            ]
            elements.append(criar_tabela(rows, [90, 120, 100]))
            elements.append(Spacer(1, 12))


        

# =========================
# RESUMO ESTATÍSTICO MOTORES
# =========================

            elements.append(
                Paragraph("<b>Statistical Summary of Motors</b>", styles["Heading2"])
            )

            def min_sem_zero(series):
                series = series.replace(0, np.nan).dropna()
                return series.min() if not series.empty else 0

            # ----- MOTOR 1 -----
            corrente_media_1 = df_motor_full["current1"].mean()
            corrente_min_1 = min_sem_zero(df_motor_full["current1"])
            corrente_max_1 = df_motor_full["current1"].max()

            voltage_media_1 = df_motor_full["voltage1"].mean()
            voltage_min_1 = min_sem_zero(df_motor_full["voltage1"])
            voltage_max_1 = df_motor_full["voltage1"].max()

            rpm_medio_1 = df_motor_full["rpm1"].mean()
            rpm_min_1 = min_sem_zero(df_motor_full["rpm1"])
            rpm_max_1 = df_motor_full["rpm1"].max()

            potencia_media_1 = df_motor_full["power1"].mean()
            potencia_min_1 = min_sem_zero(df_motor_full["power1"])
            potencia_max_1 = df_motor_full["power1"].max()

            # ----- MOTOR 2 -----
            corrente_media_2 = df_motor_full["current2"].mean()
            corrente_min_2 = min_sem_zero(df_motor_full["current2"])
            corrente_max_2 = df_motor_full["current2"].max()

            voltage_media_2 = df_motor_full["voltage2"].mean()
            voltage_min_2 = min_sem_zero(df_motor_full["voltage2"])
            voltage_max_2 = df_motor_full["voltage2"].max()

            rpm_medio_2 = df_motor_full["rpm2"].mean()
            rpm_min_2 = min_sem_zero(df_motor_full["rpm2"])
            rpm_max_2 = df_motor_full["rpm2"].max()

            potencia_media_2 = df_motor_full["power2"].mean()
            potencia_min_2 = min_sem_zero(df_motor_full["power2"])
            potencia_max_2 = df_motor_full["power2"].max()

            # ----- TABELA -----
            rows = [
                ["Metric", "Motor 1", "Motor 2"],

                ["Average Current (A)", f"{corrente_media_1:.2f}", f"{corrente_media_2:.2f}"],
                ["Min Current (A)", f"{corrente_min_1:.2f}", f"{corrente_min_2:.2f}"],
                ["Max Current (A)", f"{corrente_max_1:.2f}", f"{corrente_max_2:.2f}"],

                ["Average Voltage (V)", f"{voltage_media_1:.2f}", f"{voltage_media_2:.2f}"],
                ["Min Voltage (V)", f"{voltage_min_1:.2f}", f"{voltage_min_2:.2f}"],
                ["Max Voltage (V)", f"{voltage_max_1:.2f}", f"{voltage_max_2:.2f}"],

                ["Average RPM", f"{rpm_medio_1:.2f}", f"{rpm_medio_2:.2f}"],
                ["Min RPM", f"{rpm_min_1:.2f}", f"{rpm_min_2:.2f}"],
                ["Max RPM", f"{rpm_max_1:.2f}", f"{rpm_max_2:.2f}"],

                ["Average Power (kW)", f"{potencia_media_1:.2f}", f"{potencia_media_2:.2f}"],
                ["Min Power (kW)", f"{potencia_min_1:.2f}", f"{potencia_min_2:.2f}"],
                ["Max Power (kW)", f"{potencia_max_1:.2f}", f"{potencia_max_2:.2f}"],
            ]

            elements.append(
                criar_tabela(
                    rows,
                    [220, 120, 120]
                )
            )

            elements.append(Spacer(1, 12))

        pump_col = first_existing_column(df_bombas_full, ["bar", "value"])
        cost_col = first_existing_column(df_bombas_full, ["Custo_Energy", "custo_energy", "cost", "money", "price"])

        if not df_bombas_full.empty and pump_col is not None:
                    pressao = pd.to_numeric(df_bombas_full[pump_col], errors="coerce").dropna()
                    if not pressao.empty:
                        elements.append(Paragraph("<b>Pump Summary</b>", styles["Heading2"]))
                        pressao_rows = [["Metric", "Value"]]
                        pressao_rows.append([f"Average ({pump_col})", f"{pressao.mean():.2f}"])
                        pressao_rows.append([f"Minimum ({pump_col})", f"{pressao.min():.2f}"])
                        pressao_rows.append([f"Maximum ({pump_col})", f"{pressao.max():.2f}"])
                        pressao_rows.append(["Standard Deviation", f"{pressao.std():.2f}"])
                        if cost_col and cost_col in df_bombas_full.columns:
                            custo = pd.to_numeric(df_bombas_full[cost_col], errors="coerce").dropna()
                            if not custo.empty:
                                pressao_rows.append([f"Average {cost_col}", f"{custo.mean():.2f}"])
                                pressao_rows.append([f"Minimum {cost_col}", f"{custo.min():.2f}"])
                                pressao_rows.append([f"Maximum {cost_col}", f"{custo.max():.2f}"])
                                pressao_rows.append([f"Std {cost_col}", f"{custo.std():.2f}"])
                        elements.append(criar_tabela(pressao_rows, [170, 150]))
                        elements.append(Spacer(1, 12))

        if motors_info:
                    for m in motors_info:
                        insight_text = clean_insight_text(m.get("insights", "No insights available."))
                        if insight_text:
                            elements.append(Paragraph(f"<b>Insight {m.get('motor', '')}</b>", styles["Heading2"]))
                            elements.append(Paragraph(format_insight_paragraph(insight_text), styles["BodyText"]))
                            elements.append(Spacer(1, 12))
        if bomba_info:
                    insight_text = clean_insight_text(bomba_info.get("insights", "No insights available."))
                    elements.append(Paragraph("<b>Pump Insight</b>",styles["Heading2"]))
                    elements.append(Paragraph(format_insight_paragraph(insight_text), styles["BodyText"]))
                    elements.append(Spacer(1, 12))

        if selected_date is not None:
                    elements.append(Paragraph("<b>Selected date for analysis</b>", styles["Heading2"]))
                    elements.append(Paragraph(selected_date.strftime('%d/%m/%Y'), styles["BodyText"]))
                    elements.append(Spacer(1, 12))

        doc.build(elements)

        tmp_pdf.seek(0)
        return tmp_pdf.read()

# =========================
# AUTO-REFRESH
# =========================
if st.session_state.auto_refresh:st_autorefresh(interval=180000,key="datarefresh")

################
##header
#############
st.markdown('<h1 class="main-title">Hydropressor analysis</h1>', unsafe_allow_html=True)

button_placeholder = st.empty()
            
# =========================
# MINI CHAT INDUSTRIAL
# =========================

st.markdown("---")

st.markdown("## 🤖 Smart Industrial Assistant")

with st.form("chat_form_motores", clear_on_submit=False):

    pergunta = st.text_input(
        "Faz uma pergunta sobre o sistema"
    )

    submitted = st.form_submit_button("Perguntar")

    if submitted:

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

    st.markdown(
        st.session_state.chat_resposta.replace("\n", "  \n")
    )

auto_refresh = st.toggle(
    "Auto-refresh",
    key="auto_refresh"
)            
            
# =========================
# SELEÇÃO DE MOTOR
# =========================
st.markdown('<div class="section-title">Motor Selection</div>', unsafe_allow_html=True)
motor_sel = st.selectbox("Motor", ["Motor 1", "Motor 2", "Comparativo"])



# =========================
# CARREGAR DADOS HISTÓRICOS
# =========================
df_motor_full = carregar_dados_historicos()
df_bombas_full = carregar_dados_historicos("bombas_historico.parquet")
if not df_bombas_full.empty:

    if "bar" in df_bombas_full.columns:
        df_bombas_full["bar"] = pd.to_numeric(
            df_bombas_full["bar"],
            errors="coerce"
        )

    if "Custo_Energy" in df_bombas_full.columns:
        df_bombas_full["Custo_Energy"] = pd.to_numeric(
            df_bombas_full["Custo_Energy"],
            errors="coerce"
        )

pump_field = first_existing_column(df_bombas_full, ["bar", "value"])
cost_field = first_existing_column(df_bombas_full, ["Custo_Energy", "custo_energy", "cost", "money", "price"])



# =========================
# LER INSIGHTS LLM
# =========================

dados_motores = []
dados_bombas = []

if os.path.exists("resultados.json"):
    try:
        with open("resultados.json", encoding="utf-8") as f:
            resultados_json = json.load(f)
        
        # Se o JSON vier em lista
        if isinstance(resultados_json, list):
            dados_motores = []
            dados_bombas = []
        # Se vier em dicionário
        else:
            dados_motores = resultados_json.get("motores", [])
            dados_bombas = resultados_json.get("bombas", [])
    except Exception as e:
        st.warning(f"Error reading resultados.json: {e}")
else:
    st.warning("File resultados.json not found. Run LLM.py first.")
    

# =========================
# Filtrar motor selecionado
# =========================
if motor_sel == "Motor 1":
    motor_suffix = "1"
    df_motor = df_motor_full.copy()
elif motor_sel == "Motor 2":
    motor_suffix = "2"
    # Verifica se todas as colunas do Motor2 existem
    motor2_cols = ["time", "current2", "voltage2", "rpm2", "power2", "energy2"]
    if all(col in df_motor_full.columns for col in motor2_cols):
        # Seleciona apenas colunas do Motor2 e renomeia para a estrutura do Motor1
        df_motor = df_motor_full[motor2_cols].copy()
        df_motor.rename(columns={
            "current2":"current1",
            "voltage2":"voltage1",
            "rpm2":"rpm1",
            "power2":"power1",
            "energy2":"energy1"
        }, inplace=True)
    else:
        df_motor = pd.DataFrame()
else:  # Comparativo
    motor_suffix = None
    df_motor = df_motor_full.copy()

# =========================
# Verificar se há dados
# =========================
if df_motor.empty:
    st.warning(f"No data for {motor_sel} in this period.")
    st.stop()

selected_date = None
kpis = {}
if motor_suffix:
    kpis = calcular_kpis(df_motor, motor_suffix)

if st.button("📄 Generate PDF report"):

    pdf_bytes = gerar_relatorio_motor_bomba(
        motor_sel=motor_sel,
        df_motor_full=df_motor_full,
        df_motor=df_motor,
        motor_suffix=motor_suffix,
        kpis=kpis,
        df_bombas_full=df_bombas_full,
        dados_motores=dados_motores,
        dados_bombas=dados_bombas,
        selected_date=None
    )

    st.download_button(
        label="⬇️ Download report",
        data=pdf_bytes,
        file_name=f"relatorio_{motor_sel.replace(' ', '_')}.pdf",
        mime="application/pdf"
    )

# =========================
# KPIs
# =========================
st.markdown('<div class="section-title">Real-time Indicator </div>', unsafe_allow_html=True)

if motor_suffix:
    pump_field = first_existing_column(df_bombas_full, ["bar", "value"])
    cost_field = first_existing_column(df_bombas_full, ["Custo_Energy", "custo_energy", "cost", "money", "price"])
    bombas_value = safe_val_any(df_bombas_full, ["bar", "value"])
    bombas_cost = safe_val_any(df_bombas_full, ["Custo_Energy", "custo_energy", "cost", "money", "price"])
    cols = st.columns(6 if cost_field else 5)
    cols[0].markdown(f"<div class='card'><div class='kpi-title'>Current (A)</div><div class='kpi-value'>{kpis['Current']:.2f}</div></div>", unsafe_allow_html=True)
    cols[1].markdown(f"<div class='card'><div class='kpi-title'>Voltage (V)</div><div class='kpi-value'>{kpis['Voltage']:.2f}</div></div>", unsafe_allow_html=True)
    cols[2].markdown(f"<div class='card'><div class='kpi-title'>RPM</div><div class='kpi-value'>{kpis['RPM']:.2f}</div></div>", unsafe_allow_html=True)
    cols[3].markdown(f"<div class='card'><div class='kpi-title'>Power (kW)</div><div class='kpi-value'>{kpis['Power']:.2f}</div></div>", unsafe_allow_html=True)
    cols[4].markdown(f"<div class='card'><div class='kpi-title'>Pressure/Pumps(Bar)</div><div class='kpi-value'>{bombas_value:.2f}</div></div>", unsafe_allow_html=True)
    if cost_field:
        cols[5].markdown(f"<div class='card'><div class='kpi-title'>Pump cost</div><div class='kpi-value'>{bombas_cost:.2f}</div></div>", unsafe_allow_html=True)
    checar_alertas(df_motor, motor_suffix)

# =========================
# Gráficos
# =========================
if motor_suffix:
    st.markdown('<div class="section-title">    Motors Data</div>', unsafe_allow_html=True)

if motor_suffix and not df_motor.empty:
    # Seleção de métricas
    metricas_disponiveis = ["Power", "RPM", "Current", "Voltage"]
    metricas_selecionadas = st.multiselect(
        "Select metrics to display", 
        metricas_disponiveis, 
        default=["Power", "RPM"]
    )

    df_motor = df_motor.copy()
    df_motor['date_only'] = df_motor['time'].dt.date
    dia_inicial = df_motor['date_only'].max()
    dia_selecionado = st.date_input("Choose day to display", value=dia_inicial, min_value=df_motor['date_only'].min(), max_value=dia_inicial)
    df_motor_dia = df_motor[df_motor['date_only'] == dia_selecionado].copy()

    if df_motor_dia.empty:
        st.warning(f"No data for the selected day: {dia_selecionado}")
    elif metricas_selecionadas:
        fig = go.Figure()
        cores = {"Power":"blue", "RPM":"red", "Current":"green", "Voltage":"orange"}

        for met in metricas_selecionadas:
            col_name = f"{met.lower()}{motor_suffix}"
            if col_name not in df_motor_dia.columns:
                continue

            if met == "RPM":  # eixo Y secundário
                fig.add_trace(go.Scatter(
                    x=df_motor_dia["time"],
                    y=df_motor_dia[col_name],
                    name=met,
                    line=dict(color=cores[met]),
                    yaxis="y2"
                ))
            else:  # eixo principal
                fig.add_trace(go.Scatter(
                    x=df_motor_dia["time"],
                    y=df_motor_dia[col_name],
                    name=met,
                    line=dict(color=cores[met])
                ))

        fig.update_layout(
            title=f"Motor {motor_sel} Trend - {dia_selecionado}",
            xaxis_title="Hour",
            xaxis=dict(
                type='date',
                tickformat='%H:%M'
            ),
            yaxis=dict(title="Power / Current / Voltage"),
            yaxis2=dict(title="RPM", overlaying='y', side='right'),
            template="simple_white",
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, width='stretch')


# =========================
# AI MOTOR ANALYSIS
# =========================

st.markdown(
    '<div class="section-title">AI Motor Analysis</div>',
    unsafe_allow_html=True
)

if dados_motores:

    for motor in dados_motores:

        st.subheader(motor['motor'])

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Status",
                motor['status']
            )


        with col2:
            st.metric(
                "Total Consumption",
                f"{motor.get('consumo_total_kwh', 0)} kWh"
            )

        st.markdown("### AI Insight")

        st.markdown(format_insight_paragraph(motor['insights']), unsafe_allow_html=True)

        st.divider()


# =========================
# AI PRESSURE SYSTEM ANALYSIS
# =========================

st.markdown(
    '<div class="section-title">AI Pressure System Analysis</div>',
    unsafe_allow_html=True
)

if dados_bombas:

    for bomba in dados_bombas:

        st.subheader(bomba['bomba'])

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Status",
                bomba['status']
            )

        with col2:
            st.metric(
                "Pressure Stability",
                bomba.get('estabilidade', 'N/A')
            )

        st.markdown("### AI Insight")

        st.markdown(format_insight_paragraph(bomba['insights']), unsafe_allow_html=True)

        st.divider()



# =========================
# TRENDS DE PRESSÃO
# =========================
st.markdown('<div class="section-title">Pressure Trend Analysis</div>', unsafe_allow_html=True)

if df_bombas_full.empty:
    st.info("No pressure data available.")
else:
    trend_type = st.selectbox(
        "Type of Trend",
        ["Continuous Line (Time Series)", "Daily Average (Bar Chart)", "Hourly Average (Line Chart)", "Boxplot per Day", "Scatter / Correlation"]
    )

    if trend_type == "Continuous Line (Time Series)":
        if pump_field is None:
            st.info("No pump field available for pressure chart.")
        else:
            fig = px.line(df_bombas_full, x="time", y=pump_field, title="Pressure over time")
            fig.update_layout(xaxis_title="Time", yaxis_title=f"Pressure ({pump_field})")
            st.plotly_chart(fig, width='stretch')

    elif trend_type == "Daily Average (Bar Chart)":
        if pump_field is None:
            st.info("No pump field available for daily average chart.")
        else:
            df_bombas_full['date'] = pd.to_datetime(df_bombas_full['time']).dt.strftime('%Y-%m-%d')
            df_daily_press = (df_bombas_full.groupby('date')[pump_field].mean().reset_index())
            fig = px.bar(df_daily_press,x="date",y=pump_field,title="Average pressure per day")
            fig.update_layout(xaxis_title="Day",yaxis_title=f"Average {pump_field} per day",xaxis=dict(type='category'))
            st.plotly_chart(fig, width='stretch')

    elif trend_type == "Hourly Average (Line Chart)":
        if pump_field is None:
            st.info("No pump field available for hourly average chart.")
        else:
            df_bombas_full['hour'] = pd.to_datetime(df_bombas_full['time']).dt.hour
            df_hourly_press = df_bombas_full.groupby('hour')[pump_field].mean().reset_index()
            fig = px.line(df_hourly_press, x="hour", y=pump_field, title="Hourly pressure pattern")
            fig.update_layout(xaxis_title="Hour", yaxis_title=f"Average {pump_field} (Bar)")
            st.plotly_chart(fig, width='stretch')

    elif trend_type == "Boxplot per Day":
        if pump_field is None:
            st.info("No pump field available for boxplot chart.")
        else:
            df_bombas_full['date'] = pd.to_datetime(df_bombas_full['time']).dt.date
            fig = px.box(df_bombas_full, x="date", y=pump_field, title="Pressure dispersion per day")
            fig.update_layout(xaxis_title="Day", yaxis_title=f"{pump_field} (Bar)")
            st.plotly_chart(fig, width='stretch')

    elif trend_type == "Scatter / Correlation":
        # Para scatter, combinar com dados de motor
        try:
            df_motor_sorted = df_motor_full.dropna(subset=['time']).sort_values('time')
            df_bombas_sorted = df_bombas_full.dropna(subset=['time']).sort_values('time')
            
            if not df_motor_sorted.empty and not df_bombas_sorted.empty:
                df_combined = pd.merge_asof(
                    df_motor_sorted,
                    df_bombas_sorted,
                    on='time',
                    direction='nearest'
                )
                if not df_combined.empty:
                    corr_var = st.selectbox("Motor variable for correlation", ["power1", "rpm1", "current1", "voltage1"])
                    if pump_field is None:
                        st.info("No pump field available for correlation.")
                    else:
                        fig = px.scatter(df_combined, x=pump_field, y=corr_var, title=f"Pressure vs {corr_var}")
                        fig.update_layout(xaxis_title=f"{pump_field} (Bar)", yaxis_title=corr_var)
                        st.plotly_chart(fig, width='stretch')
                else:
                    st.info("No combined data available for correlation.")
            else:
                st.info("No motor or pump data available.")
        except Exception as e:
            st.error(f"Error processing correlation: {e}")




st.markdown('<div class="section-title">Voltage vs Current</div>', unsafe_allow_html=True)
if motor_suffix:
    plot_scatter(df_motor, motor_suffix, motor_sel)

st.markdown('<div class="section-title">Accumulated Energy</div>', unsafe_allow_html=True)
if motor_suffix:
    df_motor['time'] = pd.to_datetime(df_motor['time'])
    df_motor['date'] = df_motor['time'].dt.date
    unique_dates = sorted(df_motor['date'].unique())
    selected_date = st.date_input(
        "Choose the day",
        value=unique_dates[-1],
        min_value=unique_dates[0],
        max_value=unique_dates[-1]
    )
    df_motor_day = df_motor[df_motor['date'] == selected_date]
    if df_motor_day.empty:
        st.warning(f"No data for the selected day: {selected_date}")
    else:
        plot_energy(df_motor_day, motor_suffix, motor_sel, selected_date)

