from flask import Flask, request, jsonify
from sqlalchemy import create_engine
import pandas as pd

app = Flask(__name__)

# Configuración del Data Warehouse (PostgreSQL)
DATABASE_TYPE = 'postgresql'
DBAPI = 'psycopg2'
ENDPOINT = 'localhost'
USER = 'david'
PASSWORD = '12345'
PORT = 5432
DATABASE = 'datawarehouse'

# Crear conexión con SQLAlchemy
engine = create_engine(f"{DATABASE_TYPE}+{DBAPI}://{USER}:{PASSWORD}@{ENDPOINT}:{PORT}/{DATABASE}")

# Ruta de bienvenida
@app.route("/", methods=["GET"])
def home():
    return """
    <h1>Bienvenido a la API del Data Warehouse</h1>
    <p>Usa los siguientes endpoints:</p>
    <ul>
        <li><b>/api/data</b>: Obtener todos los datos con paginación.</li>
        <li><b>/api/data/&lt;sensor&gt;</b>: Filtrar datos por tipo de sensor (e.g., temp, humedad).</li>
        <li><b>/api/data/range</b>: Filtrar datos por rango de fechas.</li>
    </ul>
    """

# Endpoint para obtener todos los datos con paginación
@app.route("/api/data", methods=["GET"])
def get_data():
    try:
        # Paginación
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 100))
        offset = (page - 1) * limit

        # Consultar datos con paginación
        query = f"""
            SELECT * FROM sensor_data
            ORDER BY time_index DESC
            LIMIT {limit} OFFSET {offset}
        """
        with engine.connect() as conn:
            data = pd.read_sql_query(query, conn)

        # Retornar datos en formato JSON
        return jsonify(data.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint para filtrar datos por tipo de sensor
@app.route("/api/data/<sensor>", methods=["GET"])
def get_sensor_data(sensor):
    try:
        valid_sensors = ["temp", "humedad"]
        if sensor not in valid_sensors:
            return jsonify({"error": f"Sensor inválido. Usa uno de los siguientes: {valid_sensors}"}), 400

        # Consultar datos filtrados por tipo de sensor
        query = f"""
            SELECT time_index, {sensor}
            FROM sensor_data
            ORDER BY time_index DESC
            LIMIT 100
        """
        with engine.connect() as conn:
            data = pd.read_sql_query(query, conn)

        return jsonify(data.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint para filtrar datos por rango de fechas
@app.route("/api/data/range", methods=["GET"])
def get_data_by_range():
    try:
        # Obtener parámetros de fechas
        start_date = request.args.get("start_date")  # Formato: YYYY-MM-DD
        end_date = request.args.get("end_date")  # Formato: YYYY-MM-DD

        if not start_date or not end_date:
            return jsonify({"error": "Se requieren start_date y end_date"}), 400

        # Consultar datos en el rango de fechas
        query = f"""
            SELECT * FROM sensor_data
            WHERE time_index BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY time_index ASC
        """
        with engine.connect() as conn:
            data = pd.read_sql_query(query, conn)

        return jsonify(data.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Para agregar datos manualmente
@app.route("/api/data", methods=["POST"])
def add_data():
    try:
        # Parsear datos enviados en formato JSON
        data = request.get_json()
        with engine.connect() as conn:
            for row in data:
                conn.execute(
                    f"""
                    INSERT INTO sensor_data (entity_id, entity_type, time_index, temp, humedad, lat, lon)
                    VALUES ('{row['entity_id']}', '{row['entity_type']}', '{row['time_index']}', {row['temp']}, {row['humedad']}, {row['lat']}, {row['lon']})
                    """
                )
        return jsonify({"message": "Datos agregados correctamente"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5006, debug=True)

