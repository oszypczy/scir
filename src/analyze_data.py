"""
Etap 4 - Analiza i wizualizacja danych stacji pogodowej.

Pobiera dane z ThingSpeak, czyści je, oblicza metryki pochodne,
generuje 10 wykresów PNG i raport tekstowy.
"""

import os
import math
import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
from matplotlib.patches import Patch
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Konfiguracja
# ---------------------------------------------------------------------------

load_dotenv()

CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID")
READ_API_KEY = os.getenv("THINGSPEAK_READ_API_KEY")
THINGSPEAK_BASE = "https://api.thingspeak.com"

OUTPUT_DIR = Path(__file__).parent.parent / "output"
CHARTS_DIR = OUTPUT_DIR / "charts"
REPORT_PATH = OUTPUT_DIR / "report.txt"

FIELD_MAP = {
    "field1": "temperature",
    "field2": "humidity",
    "field3": "pressure",
    "field4": "light",
}
UNITS = {
    "temperature": "°C",
    "humidity": "%",
    "pressure": "hPa",
    "light": "lux",
}
# Zakresy fizyczne do walidacji
VALID_RANGES = {
    "temperature": (-30, 50),
    "humidity": (0, 100),
    "pressure": (900, 1100),
    "light": (0, 150000),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Pobieranie danych z ThingSpeak
# ---------------------------------------------------------------------------

def fetch_thingspeak(channel_id: str, api_key: str | None, results: int = 8000) -> pd.DataFrame:
    """Pobiera dane z ThingSpeak z obsługą paginacji po datach."""
    all_feeds: list[dict] = []
    url = f"{THINGSPEAK_BASE}/channels/{channel_id}/feeds.json"
    params: dict = {"results": results}
    if api_key:
        params["api_key"] = api_key

    log.info("Pobieranie danych z ThingSpeak (kanał %s)...", channel_id)
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    feeds = data.get("feeds", [])
    all_feeds.extend(feeds)

    # Jeśli zwrócono max wyników - pobieramy starsze dane stronicując po dacie
    while len(feeds) == results:
        oldest = feeds[0]["created_at"]
        # Cofnij o 1 sekundę, żeby nie duplikować
        end_dt = datetime.fromisoformat(oldest.replace("Z", "+00:00")) - timedelta(seconds=1)
        params["end"] = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        feeds = resp.json().get("feeds", [])
        all_feeds = feeds + all_feeds

    log.info("Pobrano łącznie %d rekordów.", len(all_feeds))

    df = pd.DataFrame(all_feeds)
    if df.empty:
        raise ValueError("Brak danych w kanale ThingSpeak.")

    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df = df.set_index("created_at").sort_index()

    for field, name in FIELD_MAP.items():
        if field in df.columns:
            df[name] = pd.to_numeric(df[field], errors="coerce")

    df = df[list(FIELD_MAP.values())]
    return df


# ---------------------------------------------------------------------------
# 2. Czyszczenie danych
# ---------------------------------------------------------------------------

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Usuwa outliery, waliduje zakresy fizyczne, uzupełnia małe luki."""
    df = df.copy()

    # Walidacja zakresów fizycznych
    for col, (lo, hi) in VALID_RANGES.items():
        if col in df.columns:
            mask = (df[col] < lo) | (df[col] > hi)
            if mask.sum():
                log.warning("Usuwam %d wartości poza zakresem fizycznym w '%s'.", mask.sum(), col)
            df.loc[mask, col] = np.nan

    # Metoda IQR (3*IQR)
    for col in df.columns:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lo = q1 - 3 * iqr
        hi = q3 + 3 * iqr
        mask = (df[col] < lo) | (df[col] > hi)
        if mask.sum():
            log.info("IQR: usuwam %d outlierów w '%s'.", mask.sum(), col)
        df.loc[mask, col] = np.nan

    # Forward-fill małych luk (do 5 minut)
    df = df.resample("1min").mean()
    df = df.ffill(limit=5)

    log.info("Po czyszczeniu: %d rekordów, zakres: %s – %s",
             len(df), df.index.min(), df.index.max())
    return df


# ---------------------------------------------------------------------------
# 3. Metryki pochodne
# ---------------------------------------------------------------------------

def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Punkt rosy (wzór Magnusa)
    T = df["temperature"]
    RH = df["humidity"].clip(1, 100)
    alpha = (17.27 * T) / (237.7 + T) + np.log(RH / 100)
    df["dew_point"] = (237.7 * alpha) / (17.27 - alpha)

    # Klasyfikacja dzień/noc (próg 10 lux)
    df["is_day"] = (df["light"] >= 10).astype(int)

    # Trend ciśnienia: różnica krocząca 3h
    df["pressure_trend"] = df["pressure"].diff(180)  # 180 minut = 3h przy resample 1min

    # Indeks komfortu Thomaa (DI)
    df["comfort_index"] = T - 0.55 * (1 - 0.01 * df["humidity"]) * (T - 14.5)

    return df


# ---------------------------------------------------------------------------
# 4. Analiza statystyczna
# ---------------------------------------------------------------------------

def compute_statistics(df: pd.DataFrame) -> dict:
    sensors = ["temperature", "humidity", "pressure", "light"]
    stats: dict = {}

    # Statystyki opisowe
    desc = df[sensors].describe(percentiles=[0.25, 0.5, 0.75])
    stats["descriptive"] = desc

    # Agregacje dobowe
    daily = df[sensors].resample("1D").agg(["mean", "min", "max"])
    daily.columns = ["_".join(c) for c in daily.columns]
    daily["temperature_amplitude"] = daily["temperature_max"] - daily["temperature_min"]
    stats["daily"] = daily

    # Profile godzinowe (0-23)
    df_hour = df[sensors].copy()
    df_hour.index = df_hour.index.hour
    hourly = df_hour.groupby(df_hour.index).agg(["mean", "std"])
    stats["hourly"] = hourly

    # Macierz korelacji Pearsona
    stats["correlation"] = df[sensors].corr(method="pearson")

    # Porównanie dzień vs noc
    day_df = df[df["is_day"] == 1][sensors]
    night_df = df[df["is_day"] == 0][sensors]
    stats["day"] = day_df.describe()
    stats["night"] = night_df.describe()

    # Detekcja anomalii (z-score > 3)
    anomalies: dict = {}
    for col in sensors:
        s = df[col].dropna()
        z = (s - s.mean()) / s.std()
        anomalies[col] = s[z.abs() > 3]

        # Nagłe skoki (zmiana > 3 odch. std. między próbkami)
        diff = df[col].diff().abs()
        jump_threshold = 3 * diff.std()
        anomalies[f"{col}_jumps"] = df.loc[diff > jump_threshold, col]
    stats["anomalies"] = anomalies

    return stats


# ---------------------------------------------------------------------------
# 5. Wizualizacje
# ---------------------------------------------------------------------------

def _savefig(fig: plt.Figure, name: str) -> None:
    path = CHARTS_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Zapisano wykres: %s", path)


def plot_time_series(df: pd.DataFrame) -> None:
    """Wykres 1: Przebieg czasowy 4 czujników."""
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
    sensors = ["temperature", "humidity", "pressure", "light"]
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12"]
    for ax, col, color in zip(axes, sensors, colors):
        ax.plot(df.index, df[col], color=color, linewidth=0.8, label=col)
        ax.set_ylabel(f"{col}\n[{UNITS[col]}]", fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", fontsize=8)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=30, ha="right")
    fig.suptitle("Przebieg czasowy parametrów stacji pogodowej", fontsize=13)
    fig.tight_layout()
    _savefig(fig, "01_time_series.png")


def plot_hourly_profile(df: pd.DataFrame) -> None:
    """Wykres 2: Profil dobowy ze wstęgą odch. std."""
    sensors = ["temperature", "humidity", "pressure", "light"]
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    for ax, col, color in zip(axes, sensors, colors):
        grp = df[col].groupby(df.index.hour)
        mean = grp.mean()
        std = grp.std()
        hours = mean.index
        ax.plot(hours, mean, color=color, linewidth=2)
        ax.fill_between(hours, mean - std, mean + std, alpha=0.25, color=color)
        ax.set_xlabel("Godzina")
        ax.set_ylabel(f"[{UNITS[col]}]")
        ax.set_title(col)
        ax.set_xticks(range(0, 24, 3))
        ax.grid(True, alpha=0.3)
    fig.suptitle("Profil dobowy parametrów (±1σ)", fontsize=13)
    fig.tight_layout()
    _savefig(fig, "02_hourly_profile.png")


def plot_correlation_matrix(df: pd.DataFrame) -> None:
    """Wykres 3: Heatmapa korelacji Pearsona."""
    sensors = ["temperature", "humidity", "pressure", "light"]
    corr = df[sensors].corr()
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(corr, cmap="RdYlGn", vmin=-1, vmax=1)
    plt.colorbar(im, ax=ax, label="Pearson r")
    ax.set_xticks(range(len(sensors)))
    ax.set_yticks(range(len(sensors)))
    ax.set_xticklabels(sensors, rotation=30, ha="right")
    ax.set_yticklabels(sensors)
    for i in range(len(sensors)):
        for j in range(len(sensors)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=11,
                    color="black" if abs(corr.iloc[i, j]) < 0.7 else "white")
    ax.set_title("Macierz korelacji Pearsona", fontsize=13)
    fig.tight_layout()
    _savefig(fig, "03_correlation_matrix.png")


def plot_scatter_correlations(df: pd.DataFrame) -> None:
    """Wykres 4: Scatter 2x2 z linią regresji i R²."""
    pairs = [
        ("temperature", "humidity"),
        ("temperature", "pressure"),
        ("light", "temperature"),
        ("humidity", "dew_point"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.flatten()
    for ax, (x_col, y_col) in zip(axes, pairs):
        x = df[x_col].dropna()
        y = df[y_col].dropna()
        idx = x.index.intersection(y.index)
        x, y = x[idx], y[idx]
        ax.scatter(x, y, s=3, alpha=0.3, color="#3498db")
        # Regresja liniowa
        if len(x) > 1:
            coeffs = np.polyfit(x, y, 1)
            x_line = np.linspace(x.min(), x.max(), 200)
            ax.plot(x_line, np.polyval(coeffs, x_line), "r-", linewidth=1.5)
            r = np.corrcoef(x, y)[0, 1]
            ax.text(0.05, 0.92, f"R²={r**2:.3f}", transform=ax.transAxes, fontsize=10,
                    color="red", bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7))
        ax.set_xlabel(f"{x_col} [{UNITS.get(x_col, '')}]")
        ax.set_ylabel(f"{y_col} [{UNITS.get(y_col, '°C')}]")
        ax.set_title(f"{x_col} vs {y_col}")
        ax.grid(True, alpha=0.3)
    fig.suptitle("Korelacje między parametrami", fontsize=13)
    fig.tight_layout()
    _savefig(fig, "04_scatter_correlations.png")


def plot_histograms(df: pd.DataFrame) -> None:
    """Wykres 5: Histogramy rozkładów z zaznaczeniem średniej/mediany."""
    sensors = ["temperature", "humidity", "pressure", "light"]
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    for ax, col, color in zip(axes, sensors, colors):
        data = df[col].dropna()
        ax.hist(data, bins=50, color=color, alpha=0.7, edgecolor="white")
        mean_val = data.mean()
        median_val = data.median()
        ax.axvline(mean_val, color="black", linestyle="--", linewidth=1.5, label=f"Średnia: {mean_val:.1f}")
        ax.axvline(median_val, color="gray", linestyle=":", linewidth=1.5, label=f"Mediana: {median_val:.1f}")
        ax.set_xlabel(f"[{UNITS[col]}]")
        ax.set_ylabel("Liczba pomiarów")
        ax.set_title(col)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")
    fig.suptitle("Rozkłady wartości czujników", fontsize=13)
    fig.tight_layout()
    _savefig(fig, "05_histograms.png")


def plot_day_night_boxplot(df: pd.DataFrame) -> None:
    """Wykres 6: Box ploty dzień vs noc dla temp i wilgotności."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 6))
    for ax, col in zip(axes, ["temperature", "humidity"]):
        day_data = df[df["is_day"] == 1][col].dropna()
        night_data = df[df["is_day"] == 0][col].dropna()
        bp = ax.boxplot([day_data, night_data], labels=["Dzień", "Noc"],
                        patch_artist=True, notch=False,
                        medianprops=dict(color="black", linewidth=2))
        bp["boxes"][0].set_facecolor("#f39c12")
        bp["boxes"][1].set_facecolor("#2c3e50")
        ax.set_ylabel(f"{col} [{UNITS[col]}]")
        ax.set_title(col)
        ax.grid(True, alpha=0.3, axis="y")
    fig.suptitle("Porównanie dzień vs noc", fontsize=13)
    fig.tight_layout()
    _savefig(fig, "06_day_night_boxplot.png")


def plot_pressure_trend(df: pd.DataFrame) -> None:
    """Wykres 7: Ciśnienie z kolorowym tłem trendu (fill_between zamiast pętli axvspan)."""
    fig, ax = plt.subplots(figsize=(14, 5))

    trend = df["pressure_trend"].fillna(0)
    p_min = df["pressure"].min() - 1
    p_max = df["pressure"].max() + 1

    # Wypełnienia wektorowe zamiast pętli
    rising = trend >= 0.5
    falling = trend <= -0.5

    ax.fill_between(df.index, p_min, p_max, where=rising, color="#2ecc71", alpha=0.25, label="Rośnie")
    ax.fill_between(df.index, p_min, p_max, where=falling, color="#e74c3c", alpha=0.25, label="Spada")

    ax.plot(df.index, df["pressure"], color="#27ae60", linewidth=1, zorder=3, label="Ciśnienie")
    ax.set_ylim(p_min, p_max)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=30, ha="right")
    ax.set_ylabel(f"Ciśnienie [{UNITS['pressure']}]")
    ax.set_title("Ciśnienie atmosferyczne z trendem 3h", fontsize=13)
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    _savefig(fig, "07_pressure_trend.png")


def plot_dew_point(df: pd.DataFrame) -> None:
    """Wykres 8: Temperatura i punkt rosy z zacienionym obszarem."""
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(df.index, df["temperature"], color="#e74c3c", linewidth=1, label="Temperatura")
    ax.plot(df.index, df["dew_point"], color="#3498db", linewidth=1, label="Punkt rosy")
    ax.fill_between(df.index, df["dew_point"], df["temperature"],
                    alpha=0.15, color="#9b59b6", label="Różnica (ryzyko mgły)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=30, ha="right")
    ax.set_ylabel("Temperatura [°C]")
    ax.set_title("Temperatura vs Punkt rosy", fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    _savefig(fig, "08_dew_point.png")


def plot_heatmap_temp(df: pd.DataFrame) -> None:
    """Wykres 9: Mapa cieplna: godzina (x) vs dzień (y) vs temperatura."""
    df_copy = df[["temperature"]].copy()
    df_copy["hour"] = df_copy.index.hour
    df_copy["date"] = df_copy.index.date
    pivot = df_copy.pivot_table(values="temperature", index="date", columns="hour", aggfunc="mean")

    fig, ax = plt.subplots(figsize=(14, max(4, len(pivot) // 3)))
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlBu_r",
                   extent=[-0.5, 23.5, len(pivot) - 0.5, -0.5])
    plt.colorbar(im, ax=ax, label="Temperatura [°C]")
    ax.set_xlabel("Godzina")
    ax.set_xticks(range(0, 24, 2))
    ax.set_yticks(range(0, len(pivot), max(1, len(pivot) // 10)))
    ax.set_yticklabels([str(pivot.index[i]) for i in range(0, len(pivot), max(1, len(pivot) // 10))],
                       fontsize=8)
    ax.set_title("Mapa cieplna temperatury: godzina × dzień", fontsize=13)
    fig.tight_layout()
    _savefig(fig, "09_heatmap_temperature.png")


def plot_anomalies(df: pd.DataFrame, stats: dict) -> None:
    """Wykres 10: Temperatura z zaznaczonymi anomaliami."""
    anomalies = stats["anomalies"].get("temperature", pd.Series(dtype=float))
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(df.index, df["temperature"], color="#e74c3c", linewidth=0.8, label="Temperatura", zorder=2)
    if not anomalies.empty:
        ax.scatter(anomalies.index, anomalies.values, color="black", s=30, zorder=5,
                   label=f"Anomalie ({len(anomalies)})", marker="x")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=30, ha="right")
    ax.set_ylabel(f"Temperatura [{UNITS['temperature']}]")
    ax.set_title("Detekcja anomalii temperatury (z-score > 3)", fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    _savefig(fig, "10_anomalies.png")


# ---------------------------------------------------------------------------
# 6. Raport tekstowy
# ---------------------------------------------------------------------------

def generate_report(df: pd.DataFrame, stats: dict) -> str:
    sensors = ["temperature", "humidity", "pressure", "light"]
    lines: list[str] = []

    def h(title: str) -> None:
        lines.append("")
        lines.append("=" * 60)
        lines.append(title.upper())
        lines.append("=" * 60)

    h("Stacja pogodowa — Raport analizy danych (Etap 4)")
    lines.append(f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Zakres danych: {df.index.min()} — {df.index.max()}")
    lines.append(f"Liczba pomiarów: {df[sensors[0]].count()} (po czyszczeniu)")
    duration = df.index.max() - df.index.min()
    lines.append(f"Czas obserwacji: {duration.days} dni {duration.seconds//3600} godz.")

    h("Statystyki opisowe")
    desc = stats["descriptive"]
    for col in sensors:
        d = desc[col]
        lines.append(f"\n  {col} [{UNITS[col]}]:")
        lines.append(f"    Średnia:   {d['mean']:8.2f}")
        lines.append(f"    Mediana:   {d['50%']:8.2f}")
        lines.append(f"    Odch.std:  {d['std']:8.2f}")
        lines.append(f"    Min / Max: {d['min']:8.2f} / {d['max']:8.2f}")
        lines.append(f"    Q1  / Q3:  {d['25%']:8.2f} / {d['75%']:8.2f}")

    h("Macierz korelacji Pearsona")
    corr = stats["correlation"]
    header = f"{'':14s}" + "".join(f"{c:14s}" for c in sensors)
    lines.append(header)
    for row in sensors:
        row_str = f"{row:14s}" + "".join(f"{corr.loc[row, c]:14.3f}" for c in sensors)
        lines.append(row_str)

    h("Najsilniejsze korelacje")
    pairs_corr = []
    for i, a in enumerate(sensors):
        for b in sensors[i + 1:]:
            pairs_corr.append((abs(corr.loc[a, b]), a, b, corr.loc[a, b]))
    for _, a, b, r in sorted(pairs_corr, reverse=True):
        direction = "dodatnia" if r > 0 else "ujemna"
        lines.append(f"  {a} ↔ {b}: r = {r:.3f} ({direction})")

    h("Metryki pochodne")
    dp = df["dew_point"].dropna()
    lines.append(f"  Punkt rosy — śr.: {dp.mean():.1f}°C, min: {dp.min():.1f}°C, max: {dp.max():.1f}°C")
    ci = df["comfort_index"].dropna()
    lines.append(f"  Indeks komfortu (DI) — śr.: {ci.mean():.1f}, min: {ci.min():.1f}, max: {ci.max():.1f}")

    h("Trend ciśnienia")
    trend = df["pressure_trend"].dropna()
    n = len(trend)
    rising = (trend > 0.5).sum()
    falling = (trend < -0.5).sum()
    stable = n - rising - falling
    lines.append(f"  Rośnie  (>+0.5 hPa/3h): {rising:5d} pomiarów ({100*rising/n:.1f}%)")
    lines.append(f"  Spada   (<-0.5 hPa/3h): {falling:5d} pomiarów ({100*falling/n:.1f}%)")
    lines.append(f"  Stabilne:               {stable:5d} pomiarów ({100*stable/n:.1f}%)")

    h("Porównanie dzień vs noc")
    for period, key in [("Dzień", "day"), ("Noc", "night")]:
        lines.append(f"\n  {period}:")
        s = stats[key]
        for col in ["temperature", "humidity"]:
            d = s[col]
            lines.append(f"    {col}: śr.={d['mean']:.1f}, std={d['std']:.1f}, "
                         f"min={d['min']:.1f}, max={d['max']:.1f}")

    h("Raport anomalii")
    for col in sensors:
        anom = stats["anomalies"].get(col, pd.Series(dtype=float))
        jumps = stats["anomalies"].get(f"{col}_jumps", pd.Series(dtype=float))
        lines.append(f"  {col}: {len(anom)} anomalii z-score, {len(jumps)} nagłych skoków")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    if not CHANNEL_ID:
        raise ValueError(
            "Brak THINGSPEAK_CHANNEL_ID w pliku .env!\n"
            "Dodaj: THINGSPEAK_CHANNEL_ID=<twój_id_kanału>"
        )

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Pobierz dane
    df_raw = fetch_thingspeak(CHANNEL_ID, READ_API_KEY)

    # 2. Wyczyść
    df = clean_data(df_raw)

    # 3. Metryki pochodne
    df = add_derived_metrics(df)

    # 4. Statystyki
    stats = compute_statistics(df)

    # 5. Wykresy
    log.info("Generowanie wykresów...")
    plot_time_series(df)
    plot_hourly_profile(df)
    plot_correlation_matrix(df)
    plot_scatter_correlations(df)
    plot_histograms(df)
    plot_day_night_boxplot(df)
    plot_pressure_trend(df)
    plot_dew_point(df)
    plot_heatmap_temp(df)
    plot_anomalies(df, stats)
    log.info("Wszystkie 10 wykresów zapisano w %s", CHARTS_DIR)

    # 6. Raport
    report_text = generate_report(df, stats)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    log.info("Raport zapisano: %s", REPORT_PATH)

    print("\n" + report_text)
    print(f"\nWykresy: {CHARTS_DIR}")
    print(f"Raport:  {REPORT_PATH}")


if __name__ == "__main__":
    main()
