from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import psycopg2
from sqlalchemy import create_engine
from scipy.interpolate import CubicSpline
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

app = Flask(__name__)

# Almacenamiento temporal para el histórico
historico_data = pd.DataFrame(columns=["time_index", "temperatura", "humedad"])

# Función para obtener datos reales o simulados
def get_data_from_db(use_all=False, simulate=False):
    try:
        if simulate:
            # Generar datos simulados
            time_stamps = [datetime.now() - timedelta(minutes=5 * i) for i in range(288)]
            time_stamps = sorted(time_stamps)
            temps = np.random.normal(25, 3, len(time_stamps))
            hums = np.random.normal(60, 10, len(time_stamps))

            # Limitar a valores realistas
            temps = np.clip(temps, 15, 35)
            hums = np.clip(hums, 40, 80)
            simulated_data = {
                "time_index": time_stamps,
                "temperatura": temps,
                "humedad": hums,
            }
            return pd.DataFrame(simulated_data)
        else:
            # Conexión a la base de datos real
            engine = create_engine("postgresql+psycopg2://david:12345@localhost:5432/datawarehouse")
            query = """
                SELECT time_index, temp AS temperatura, humedad AS humedad
                FROM sensor_data
                {}
                ORDER BY time_index ASC
            """.format("WHERE time_index >= NOW() - INTERVAL '24 HOURS'" if not use_all else "")
            with engine.connect() as conn:
                return pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"Error al conectar con la base de datos: {e}")
        return pd.DataFrame()

# Función para generar gráficos de predicción interactivos con Plotly
def generate_prediction_plot(df, predictions_temp, predictions_humidity, future_time):
    fig = go.Figure()

    # Datos reales
    fig.add_trace(go.Scatter(
        x=df['time_index'], y=df['temperatura'],
        mode='lines+markers', name='Temperatura Real (°C)',
        line=dict(color='blue')
    ))
    fig.add_trace(go.Scatter(
        x=df['time_index'], y=df['humedad'],
        mode='lines+markers', name='Humedad Real (%)',
        line=dict(color='green')
    ))

    # Predicciones
    fig.add_trace(go.Scatter(
        x=future_time, y=predictions_temp,
        mode='lines+markers', name='Predicción Temperatura (°C)',
        line=dict(color='orange', dash='dash')
    ))
    fig.add_trace(go.Scatter(
        x=future_time, y=predictions_humidity,
        mode='lines+markers', name='Predicción Humedad (%)',
        line=dict(color='red', dash='dash')
    ))

    fig.update_layout(
        title="Predicción para la Planta",
        xaxis_title="Tiempo",
        yaxis_title="Valores",
        template="plotly_white"
    )

    return fig.to_html(full_html=False)

# Función para generar gráficos tipo batería (gauge)
def generate_status_gauges(temp, humidity):
    gauges = []

    # Gráfico de batería para temperatura
    temp_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=temp,
        title={'text': "Temperatura (°C)"},
        gauge={
            'axis': {'range': [0, 50]},
            'steps': [
                {'range': [0, 10], 'color': "lightblue"},
                {'range': [10, 28], 'color': "lightgreen"},
                {'range': [28, 50], 'color': "red"},
            ],
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 28}
        }
    ))
    gauges.append(temp_gauge.to_html(full_html=False))

    # Gráfico de batería para humedad
    humidity_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=humidity,
        title={'text': "Humedad (%)"},
        gauge={
            'axis': {'range': [0, 100]},
            'steps': [
                {'range': [0, 40], 'color': "orange"},
                {'range': [40, 70], 'color': "lightgreen"},
                {'range': [70, 100], 'color': "lightblue"},
            ],
            'threshold': {'line': {'color': "orange", 'width': 4}, 'thickness': 0.75, 'value': 40}
        }
    ))
    gauges.append(humidity_gauge.to_html(full_html=False))

    return gauges

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/predicciones", methods=["GET", "POST"])
def predicciones():
    message = ""
    predictions_temp = []
    predictions_humidity = []
    recommendations = []
    plot_html = None
    interval_start, interval_end = None, None
    decision_text = ""
    gauges_html = []

    df = pd.DataFrame()

    if request.method == "POST":
        use_all = "use_all" in request.form
        simulate = "use_demo" in request.form
        df = get_data_from_db(use_all=use_all, simulate=simulate)

        if df.empty:
            message = "No hay datos disponibles."
        else:
            interval_start = df["time_index"].min()
            interval_end = df["time_index"].max()

            if len(df) < 2:
                message = "No hay suficientes datos para la interpolación."
            else:
                x = np.arange(len(df))
                f_temp = CubicSpline(x, df["temperatura"])
                f_humidity = CubicSpline(x, df["humedad"])

                future_x = np.arange(len(df), len(df) + 10)
                predictions_temp = np.clip(f_temp(future_x), 15, 35).tolist()
                predictions_humidity = np.clip(f_humidity(future_x), 40, 80).tolist()

                future_time = pd.date_range(interval_end, periods=10, freq="H")

                for temp, hum in zip(predictions_temp, predictions_humidity):
                    if temp > 28:
                        if hum < 50:
                            recommendations.append("Riesgo de estrés hídrico. Aumentar riego.")
                        elif hum > 70:
                            recommendations.append("Riesgo de hongos. Reducir riego.")
                        else:
                            recommendations.append("Condición óptima.")
                    elif temp < 10:
                        if hum < 10:
                            recommendations.append("Riesgo de congelación. Incrementar temperatura.")
                        elif hum > 50:
                            recommendations.append("Riesgo de daño por frío. Reducir humedad.")
                        else:
                            recommendations.append("Condición óptima.")
                    else:
                        recommendations.append("Condición óptima.")

                plot_html = generate_prediction_plot(df, predictions_temp, predictions_humidity, future_time)

                # Generar texto de decisión
                if any("estrés hídrico" in rec for rec in recommendations):
                    decision_text = "Recomendación: Aumentar el riego para evitar estrés hídrico."
                elif any("hongos" in rec for rec in recommendations):
                    decision_text = "Recomendación: Reducir el riego para prevenir la aparición de hongos."
                elif any("congelación" in rec for rec in recommendations):
                    decision_text = "Recomendación: Incrementar la temperatura para evitar congelación."
                else:
                    decision_text = "Recomendación: Las condiciones son óptimas. No se requieren ajustes."

                if not df.empty:
                    last_temp = df["temperatura"].iloc[-1]
                    last_humidity = df["humedad"].iloc[-1]
                    gauges_html = generate_status_gauges(last_temp, last_humidity)

    predictions = zip(
        df["time_index"].tail(10) if not df.empty else [],
        predictions_temp,
        predictions_humidity,
        recommendations
    )

    return render_template(
        "predicciones.html",
        message=message,
        interval_start=interval_start,
        interval_end=interval_end,
        predictions=predictions,
        plot_html=plot_html,
        decision_text=decision_text,
        gauges_html=gauges_html
    )

@app.route("/historico", methods=["GET", "POST"])
def historico():
    global historico_data

    if request.method == "POST":
        if "borrar_datos" in request.form:
            historico_data = pd.DataFrame(columns=["time_index", "temperatura", "humedad"])
        else:
            new_data = get_data_from_db()
            if not new_data.empty:
                historico_data = pd.concat([historico_data, new_data]).drop_duplicates().reset_index(drop=True)

    return render_template("historico.html", historico_data=historico_data)

if __name__ == "__main__":
    app.run(port=5002, debug=True)

