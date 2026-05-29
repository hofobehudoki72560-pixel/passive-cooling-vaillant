import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, date

from main import fetch_data, simulate_state_machine

# --- Конфігурація сторінки ---
st.set_page_config(
    page_title="Симуляція пасивного охолодження — Vaillant",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Кастомні стилі ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    }
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown label,
    section[data-testid="stSidebar"] .stMarkdown span {
        color: #e0e0e0 !important;
    }

    /* Cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea20, #764ba220);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        backdrop-filter: blur(10px);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.2);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #888;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Heating card */
    .metric-card-heat {
        background: linear-gradient(135deg, #3b82f620, #06b6d420);
        border: 1px solid rgba(59, 130, 246, 0.15);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
    }
    .metric-value-heat {
        font-size: 2rem;
        font-weight: 700;
        color: #60a5fa;
        margin-bottom: 4px;
    }

    /* Cooling card */
    .metric-card-cool {
        background: linear-gradient(135deg, #ef444420, #f9731620);
        border: 1px solid rgba(239, 68, 68, 0.15);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
    }
    .metric-value-cool {
        font-size: 2rem;
        font-weight: 700;
        color: #f87171;
        margin-bottom: 4px;
    }

    /* Standby card */
    .metric-card-standby {
        background: linear-gradient(135deg, #22c55e20, #10b98120);
        border: 1px solid rgba(34, 197, 94, 0.15);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
    }
    .metric-value-standby {
        font-size: 2rem;
        font-weight: 700;
        color: #4ade80;
        margin-bottom: 4px;
    }

    /* Header */
    .main-header {
        text-align: center;
        padding: 1rem 0 0.5rem;
    }
    .main-header h1 {
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.25rem;
    }
    .main-header p {
        color: #888;
        font-size: 0.95rem;
    }

    /* Divider */
    .gradient-divider {
        height: 2px;
        background: linear-gradient(90deg, transparent, #667eea, #764ba2, transparent);
        border: none;
        margin: 1rem 0;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("## 🌡️ Параметри")
    st.markdown("---")

    # --- Період часу ---
    st.markdown("### 📅 Період часу")

    # Пресети
    preset = st.selectbox(
        "Швидкий вибір",
        ["Довільний", "Останній місяць", "Останні 3 місяці",
         "Останні 6 місяців", "Останній рік",
         "Літо 2025", "Літо 2024", "Літо 2023",
         "Літо 2022", "Літо 2021", "Літо 2020"],
        index=4
    )

    today = date.today()
    # Open-Meteo archive API has ~5 day delay, so we use today - 5
    api_end = today - timedelta(days=5)

    preset_map = {
        "Останній місяць": 30,
        "Останні 3 місяці": 90,
        "Останні 6 місяців": 180,
        "Останній рік": 365,
    }

    preset_map_summer = {
        "Літо 2025": (date(2025, 5, 1), date(2025, 10, 1)),
        "Літо 2024": (date(2024, 5, 1), date(2024, 10, 1)),
        "Літо 2023": (date(2023, 5, 1), date(2023, 10, 1)),
        "Літо 2022": (date(2022, 5, 1), date(2022, 10, 1)),
        "Літо 2021": (date(2021, 5, 1), date(2021, 10, 1)),
        "Літо 2020": (date(2020, 5, 1), date(2020, 10, 1)),
    }

    if preset in preset_map:
        days = preset_map[preset]
        default_start = api_end - timedelta(days=days)
        default_end = api_end
    elif preset in preset_map_summer:
        default_start, default_end = preset_map_summer[preset]
    else:
        default_start = api_end - timedelta(days=365)
        default_end = api_end

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date = st.date_input(
            "Від",
            value=default_start,
            min_value=date(2000, 1, 1),
            max_value=api_end
        )
    with col_d2:
        end_date = st.date_input(
            "До",
            value=default_end,
            min_value=date(2000, 1, 1),
            max_value=api_end
        )

    if start_date >= end_date:
        st.error("⚠️ Дата початку має бути раніше за дату кінця!")

    st.markdown("---")

    # --- Параметри моделі ---
    st.markdown("### ⚙️ Параметри моделі")

    t_off_heat = st.slider(
        "Межа вимкнення опалення (°C)",
        min_value=10.0, max_value=25.0,
        value=18.0, step=0.5,
        help="Температура, при якій опалення вимикається"
    )

    t_start_cool = st.slider(
        "Старт охолодження (°C)",
        min_value=18.0, max_value=35.0,
        value=23.0, step=0.5,
        help="Середньодобова температура для початку охолодження"
    )

    hysteresis = st.slider(
        "Гістерезис (К)",
        min_value=0.5, max_value=5.0,
        value=1.0, step=0.5,
        help="Різниця температур для запобігання частим перемиканням"
    )

    delay_hours = st.slider(
        "Затримка перемикання (год)",
        min_value=1, max_value=24,
        value=6, step=1,
        help="Час безперервного виконання умови для переключення режиму"
    )

    st.markdown("---")

    # Показуємо похідні пороги
    st.markdown("### 📊 Похідні пороги")
    t_stop_cool = t_start_cool - hysteresis
    t_start_heat = t_off_heat - hysteresis

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.metric("Зупинка охол.", f"{t_stop_cool:.1f} °C")
    with col_p2:
        st.metric("Старт опал.", f"{t_start_heat:.1f} °C")

    st.markdown("---")
    run_btn = st.button("🚀 Розрахувати", use_container_width=True, type="primary")


# ============================================================
# MAIN AREA
# ============================================================

# Header
st.markdown("""
<div class="main-header">
    <h1>🏠 Симуляція автоматики теплового насоса Vaillant</h1>
    <p>Аналіз режимів опалення та охолодження на основі метеоданих Києва</p>
</div>
<div class="gradient-divider"></div>
""", unsafe_allow_html=True)


# ============================================================
# DATA LOADING & SIMULATION
# ============================================================

@st.cache_data(show_spinner=False, ttl=3600)
def load_and_simulate(s_date, e_date, p_t_off_heat, p_t_start_cool, p_hysteresis, p_delay_hours):
    """Завантажує дані та запускає симуляцію. Кешується для однакових параметрів."""
    df = fetch_data(start_date=s_date, end_date=e_date)
    df = simulate_state_machine(
        df,
        t_off_heat=p_t_off_heat,
        t_start_cool=p_t_start_cool,
        hysteresis=p_hysteresis,
        delay_hours=p_delay_hours
    )
    return df


# Run on button click or on first load
if run_btn or "data_loaded" not in st.session_state:
    if start_date >= end_date:
        st.error("Оберіть коректний період дат.")
        st.stop()

    with st.spinner("⏳ Завантаження метеоданих та розрахунок..."):
        try:
            df = load_and_simulate(
                start_date, end_date,
                t_off_heat, t_start_cool, hysteresis, delay_hours
            )
            st.session_state["df"] = df
            st.session_state["data_loaded"] = True
            st.session_state["params"] = {
                "t_off_heat": t_off_heat,
                "t_start_cool": t_start_cool,
                "hysteresis": hysteresis,
                "delay_hours": delay_hours,
                "start_date": start_date,
                "end_date": end_date,
            }
        except Exception as e:
            st.error(f"❌ Помилка завантаження даних: {e}")
            st.stop()

if "df" not in st.session_state:
    st.info("👈 Оберіть параметри в бічній панелі та натисніть **Розрахувати**.")
    st.stop()

df = st.session_state["df"]
params = st.session_state["params"]


# ============================================================
# STATISTICS
# ============================================================
total_hours = len(df)
heat_hours = int((df["Mode"] == 1).sum())
cool_hours = int((df["Mode"] == 2).sum())
standby_hours = int((df["Mode"] == 0).sum())

heat_pct = heat_hours / total_hours * 100 if total_hours else 0
cool_pct = cool_hours / total_hours * 100 if total_hours else 0
standby_pct = standby_hours / total_hours * 100 if total_hours else 0

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{total_hours:,}</div>
        <div class="metric-label">Загальна кількість годин</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card-heat">
        <div class="metric-value-heat">🔥 {heat_hours:,} год ({heat_pct:.1f}%)</div>
        <div class="metric-label">Режим опалення</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card-cool">
        <div class="metric-value-cool">❄️ {cool_hours:,} год ({cool_pct:.1f}%)</div>
        <div class="metric-label">Режим охолодження</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card-standby">
        <div class="metric-value-standby">⏸️ {standby_hours:,} год ({standby_pct:.1f}%)</div>
        <div class="metric-label">Очікування</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)


# ============================================================
# PLOTLY CHARTS
# ============================================================

fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    row_heights=[0.75, 0.25],
    subplot_titles=("Температури та режими роботи", "Стейт-машина (режим)")
)

# --- Верхній графік: Температури ---
# Кольорова заливка для режимів (heating)
heating_mask = df["Mode"] == 1
cooling_mask = df["Mode"] == 2

# Заливка для опалення
if heating_mask.any():
    heat_groups = (heating_mask != heating_mask.shift()).cumsum()
    for _, group in df[heating_mask].groupby(heat_groups[heating_mask]):
        fig.add_vrect(
            x0=group.index[0], x1=group.index[-1],
            fillcolor="rgba(96, 165, 250, 0.12)",
            line_width=0,
            row=1, col=1
        )

# Заливка для охолодження
if cooling_mask.any():
    cool_groups = (cooling_mask != cooling_mask.shift()).cumsum()
    for _, group in df[cooling_mask].groupby(cool_groups[cooling_mask]):
        fig.add_vrect(
            x0=group.index[0], x1=group.index[-1],
            fillcolor="rgba(248, 113, 113, 0.12)",
            line_width=0,
            row=1, col=1
        )

# Лінія T_out
fig.add_trace(
    go.Scatter(
        x=df.index, y=df["T_out"],
        name="T_out (Поточна)",
        line=dict(color="rgba(156, 163, 175, 0.7)", width=1),
        hovertemplate="<b>Поточна:</b> %{y:.1f} °C<br>%{x}<extra></extra>"
    ),
    row=1, col=1
)

# Лінія T_avg_24
fig.add_trace(
    go.Scatter(
        x=df.index, y=df["T_avg_24"],
        name="T_avg_24 (Середньодобова)",
        line=dict(color="#3b82f6", width=2),
        hovertemplate="<b>Середньодобова:</b> %{y:.1f} °C<br>%{x}<extra></extra>"
    ),
    row=1, col=1
)

# Горизонтальні пороги
thresholds = [
    (params["t_start_cool"], "Старт охолодження", "#ef4444", "dash"),
    (params["t_start_cool"] - params["hysteresis"], "Зупинка охолодження", "#9ca3af", "dashdot"),
    (params["t_off_heat"], "Вимкнення опалення", "#f59e0b", "solid"),
    (params["t_off_heat"] - params["hysteresis"], "Відновлення опалення", "#9ca3af", "dot"),
]

for val, label, color, dash_style in thresholds:
    fig.add_hline(
        y=val, line_dash=dash_style, line_color=color, line_width=1,
        annotation_text=f"{label} ({val:.1f}°C)",
        annotation_position="top right",
        annotation_font_size=10,
        annotation_font_color=color,
        row=1, col=1
    )

# --- Нижній графік: Стейт-машина ---
mode_colors = {0: "#4ade80", 1: "#60a5fa", 2: "#f87171"}
mode_names_map = {0: "Очікування", 1: "Опалення", 2: "Охолодження"}

fig.add_trace(
    go.Scatter(
        x=df.index, y=df["Mode"],
        name="Режим",
        line=dict(color="#475569", width=2, shape="hv"),
        fill="tozeroy",
        fillcolor="rgba(102, 126, 234, 0.1)",
        hovertemplate="<b>Режим:</b> %{text}<br>%{x}<extra></extra>",
        text=[mode_names_map.get(m, "—") for m in df["Mode"]],
        showlegend=False
    ),
    row=2, col=1
)

# Layout
fig.update_layout(
    height=700,
    template="plotly_white",
    paper_bgcolor="#ffffff",
    plot_bgcolor="#ffffff",
    font=dict(family="Inter, sans-serif", color="#1e293b"),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        bgcolor="rgba(255,255,255,0.8)",
        bordercolor="rgba(0,0,0,0.1)",
        borderwidth=1,
        font=dict(size=11, color="#1e293b")
    ),
    margin=dict(l=60, r=30, t=80, b=40),
    hovermode="x unified"
)

# Осі
fig.update_xaxes(
    gridcolor="#e2e8f0",
    showgrid=True,
    row=1, col=1
)
fig.update_xaxes(
    gridcolor="#e2e8f0",
    showgrid=True,
    title_text="Час",
    row=2, col=1
)

fig.update_yaxes(
    title_text="Температура, °C",
    gridcolor="#e2e8f0",
    row=1, col=1
)
fig.update_yaxes(
    title_text="Режим",
    tickvals=[0, 1, 2],
    ticktext=["Очікування", "Опалення", "Охолодження"],
    gridcolor="#e2e8f0",
    range=[-0.3, 2.3],
    row=2, col=1
)

st.plotly_chart(fig, use_container_width=True, config={
    "displayModeBar": True,
    "scrollZoom": True,
    "displaylogo": False,
    "modeBarButtonsToAdd": ["drawrect", "eraseshape"],
    "toImageButtonOptions": {
        "format": "png",
        "filename": "vaillant_simulation",
        "height": 800,
        "width": 1600,
        "scale": 2
    }
})


# ============================================================
# FOOTER INFO
# ============================================================
st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

st.markdown(f"""
<div style="text-align: center; color: #666; font-size: 0.8rem; padding: 0.5rem 0;">
    📍 Київ (50.45°N, 30.52°E) &nbsp;|&nbsp;
    📅 {params['start_date'].strftime('%d.%m.%Y')} — {params['end_date'].strftime('%d.%m.%Y')} &nbsp;|&nbsp;
    🌐 Дані: <a href="https://open-meteo.com/" target="_blank" style="color: #667eea;">Open-Meteo</a>
</div>
""", unsafe_allow_html=True)
