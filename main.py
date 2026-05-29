import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
from datetime import datetime, timedelta

# --- 4. КОНСТАНТИ ТА ПАРАМЕТРИ МОДЕЛІ ---
T_OFF_HEAT = 18.0  # Межа відключення опалення
T_START_COOL = 23.0  # Температура старту охолодження
HYSTERESIS = 1.0  # Гістерезис (1 К)
DELAY_HOURS = 6  # Затримка для перемикання (годин)

# Похідні пороги
T_STOP_COOL = T_START_COOL - HYSTERESIS  # 22.0 °C
T_START_HEAT = T_OFF_HEAT - HYSTERESIS  # 17.0 °C


def fetch_data(start_date=None, end_date=None, days=365):
    """
    Завантажує історичні дані з Open-Meteo за вказаний період.
    Якщо start_date/end_date не вказані — бере останні `days` днів.
    """
    if end_date is None:
        end_date = datetime.now().date()
    if start_date is None:
        start_date = end_date - timedelta(days=days)

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 50.45, "longitude": 30.52,  # Київ
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "hourly": "temperature_2m",
        "timezone": "Europe/Kyiv"
    }

    print("Завантаження даних...")
    response = requests.get(url, params=params).json()

    df = pd.DataFrame({
        "Timestamp": pd.to_datetime(response["hourly"]["time"]),
        "T_out": response["hourly"]["temperature_2m"]
    })

    # Встановлення Timestamp як індексу
    df.set_index("Timestamp", inplace=True)
    return df.dropna()


def simulate_state_machine(df, t_off_heat=T_OFF_HEAT, t_start_cool=T_START_COOL,
                           hysteresis=HYSTERESIS, delay_hours=DELAY_HOURS):
    """
    Імітує роботу автоматики Vaillant згідно з заданою логікою.
    Параметри моделі можна передати явно або використовувати значення за замовчуванням.
    """
    print("Розрахунок умов та моделювання стейт-машини...")

    # Похідні пороги
    t_stop_cool = t_start_cool - hysteresis
    t_start_heat = t_off_heat - hysteresis

    # 5.1 Розрахунок середньодобової температури (ковзне вікно за 24 години)
    df['T_avg_24'] = df['T_out'].rolling(window='24h').mean()

    # 5.2 Ініціалізація таймерів умов
    # Для погодинних даних 6 годин безперервності = 7 точок поспіль (поточна + 6 попередніх)
    delay_points = delay_hours + 1

    # Створення булевих масок для умов із затримкою
    mask_gt_18 = df['T_out'] > t_off_heat
    df['cond_gt_18_delay'] = mask_gt_18.rolling(window=delay_points).sum() == delay_points

    mask_avg_lt_22 = df['T_avg_24'] < t_stop_cool
    df['cond_avg_lt_22_delay'] = mask_avg_lt_22.rolling(window=delay_points).sum() == delay_points

    mask_lt_17 = df['T_out'] < t_start_heat
    df['cond_lt_17_delay'] = mask_lt_17.rolling(window=delay_points).sum() == delay_points

    # 6. Логіка моделювання переходів (Стейт-машина)
    states = np.zeros(len(df), dtype=int)
    current_state = 0  # 0: Очікування, 1: Опалення, 2: Охолодження

    # Визначаємо стартовий стан по першій точці
    if df['T_out'].iloc[0] <= t_start_heat:
        current_state = 1

    # Ітерація для точної симуляції контролера
    for i in range(len(df)):
        if current_state == 1:
            # [Опалення] -> [Очікування]: Негайне вимкнення при T_out > t_off_heat
            if df['T_out'].iloc[i] > t_off_heat:
                current_state = 0

        elif current_state == 0:
            # [Очікування] -> [Охолодження]: T_out > t_off_heat (delay) ТА T_avg_24 > t_start_cool
            if df['cond_gt_18_delay'].iloc[i] and df['T_avg_24'].iloc[i] > t_start_cool:
                current_state = 2
            # [Очікування] -> [Опалення]: T_out < t_start_heat (delay)
            elif df['cond_lt_17_delay'].iloc[i]:
                current_state = 1

        elif current_state == 2:
            # [Охолодження] -> [Очікування]: T_avg_24 < 22 (6 год)
            if df['cond_avg_lt_22_delay'].iloc[i]:
                current_state = 0
            # [Охолодження] -> [Опалення]: Раптове похолодання T_out < 17 (6 год)
            elif df['cond_lt_17_delay'].iloc[i]:
                current_state = 1

        states[i] = current_state

    df['Mode'] = states
    return df


def plot_results(df):
    """
    Будує двопанельний графік згідно з ТЗ.
    """
    print("Формування графіків...")
    # Налаштування subplots: 2 рядки, спільна вісь X, пропорція висот 3:1
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})

    # --- Верхня панель (Температури) ---
    ax1.plot(df.index, df['T_out'], label='T_out (Поточна)', color='gray', alpha=0.7, linewidth=1)
    ax1.plot(df.index, df['T_avg_24'], label='T_avg_24 (Середньодобова)', color='blue', linewidth=1.5)

    # Горизонтальні маркери
    ax1.axhline(T_START_COOL, color='red', linestyle='--', label=f'Старт охолодження ({T_START_COOL} °C)')
    ax1.axhline(T_STOP_COOL, color='gray', linestyle='-.', alpha=0.7, label=f'Зупинка охолодження ({T_STOP_COOL} °C)')
    ax1.axhline(T_OFF_HEAT, color='orange', linestyle='-', label=f'Вимкнення опалення ({T_OFF_HEAT} °C)')
    ax1.axhline(T_START_HEAT, color='gray', linestyle=':', label=f'Відновлення опалення ({T_START_HEAT} °C)')

    # Заливка фону відповідно до режиму
    ax1.fill_between(df.index, ax1.get_ylim()[0], ax1.get_ylim()[1],
                     where=(df['Mode'] == 1), color='skyblue', alpha=0.2, label='Режим: Опалення')
    ax1.fill_between(df.index, ax1.get_ylim()[0], ax1.get_ylim()[1],
                     where=(df['Mode'] == 2), color='salmon', alpha=0.2, label='Режим: Охолодження')

    ax1.set_title('Симуляція автоматики теплового насоса (Vaillant)', fontsize=14)
    ax1.set_ylabel('Температура, °C')
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(loc='upper right', bbox_to_anchor=(1.15, 1.05), fontsize=9)

    # --- Нижня панель (Режими / Стейт-машина) ---
    # Використовуємо where='post' для коректного відображення східчастого переходу
    ax2.step(df.index, df['Mode'], color='black', where='post', linewidth=1.5)

    # Кастомізація осі Y
    ax2.set_yticks([0, 1, 2])
    ax2.set_yticklabels(['Очікування (0)', 'Опалення (1)', 'Охолодження (2)'])
    ax2.set_ylabel('Режим')
    ax2.set_xlabel('Час')
    ax2.grid(True, axis='x', linestyle=':', alpha=0.6)

    # Візуальні межі для нижнього графіка
    ax2.set_ylim(-0.5, 2.5)

    plt.tight_layout()
    plt.savefig('vaillant_simulation.png', dpi=300, bbox_inches='tight')
    plt.show()


# --- ГОЛОВНИЙ БЛОК ВИКОНАННЯ ---
if __name__ == "__main__":
    # 1. Завантаження даних (беремо останні 365 днів для наочності)
    data = fetch_data(days=365)

    # 2. Симуляція
    processed_data = simulate_state_machine(data)

    # 3. Візуалізація
    plot_results(processed_data)