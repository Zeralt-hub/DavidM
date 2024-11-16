from crate import client
from sqlalchemy import create_engine, text
import pandas as pd
from flask import Flask, render_template_string, request
import threading
import schedule
import time
import logging

app = Flask(__name__)
estado = {
    'ultimo_proceso': 'No se ha ejecutado el proceso aún.',
    'estado': 'Inactivo'
}

# Configuración básica de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("data_warehouse.log"),
        logging.StreamHandler()
    ]
)

def actualizar_data_warehouse():
    global estado
    try:
        estado['estado'] = 'En ejecución'
        estado['ultimo_proceso'] = f"Iniciado a las {pd.Timestamp.now()}"
        logging.info("Conectando a CrateDB...")
        # Configuración de CrateDB
        CRATE_HOST = 'http://10.38.32.137:8083/'
        connection = client.connect(CRATE_HOST)
        cursor = connection.cursor()

        # Consulta para extraer datos
        QUERY = """
        SELECT entity_id, entity_type, time_index, temp AS temp, humedad AS humedad, lat AS lat, lon AS lon
        FROM doc.etvariables
        WHERE entity_id = 'DavidM001'
        ORDER BY time_index DESC
        LIMIT 1000;
        """

        cursor.execute(QUERY)
        rows = cursor.fetchall()

        # Verificar si se obtuvieron datos
        if not rows:
            logging.info("No se encontraron datos en CrateDB.")
            estado['estado'] = 'Completado (sin datos)'
            return

        # Crear DataFrame
        columns = ['entity_id', 'entity_type', 'time_index', 'temp', 'humedad', 'lat', 'lon']
        df = pd.DataFrame(rows, columns=columns)

        # Procesamiento de datos
        df['time_index'] = pd.to_datetime(df['time_index'])
        df.sort_values('time_index', inplace=True)
        df.drop_duplicates(subset=['time_index'], keep='last', inplace=True)
        df.dropna(inplace=True)

        # Configuración del Data Warehouse (PostgreSQL)
        DATABASE_TYPE = 'postgresql'
        DBAPI = 'psycopg2'
        ENDPOINT = 'localhost'
        USER = 'david'
        PASSWORD = '12345'
        PORT = 5432
        DATABASE = 'datawarehouse'

        engine = create_engine(f"{DATABASE_TYPE}+{DBAPI}://{USER}:{PASSWORD}@{ENDPOINT}:{PORT}/{DATABASE}")

        # Creación de Tabla
        table_name = 'sensor_data'

        with engine.connect() as conn:
            conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                entity_id VARCHAR(255),
                entity_type VARCHAR(255),
                time_index TIMESTAMP,
                temp FLOAT,
                humedad FLOAT,
                lat FLOAT,
                lon FLOAT,
                PRIMARY KEY (entity_id, time_index)
            );
            """))

        # Insertar datos
        df.to_sql(table_name, engine, if_exists='append', index=False)
        logging.info(f"Datos actualizados correctamente a las {pd.Timestamp.now()}.")
        estado['estado'] = 'Completado'
        estado['ultimo_proceso'] = f"Completado a las {pd.Timestamp.now()}"

    except Exception as e:
        estado['estado'] = f'Error: {e}'
        logging.error(f"Ocurrió un error durante la actualización: {e}")

def job():
    logging.info("Ejecutando tarea programada de actualización...")
    actualizar_data_warehouse()

@app.route('/')
def index():
    return render_template_string('''
    <h1>Estado del Data Warehouse</h1>
    <p>Estado actual: {{ estado['estado'] }}</p>
    <p>Último proceso: {{ estado['ultimo_proceso'] }}</p>
    <form action="/actualizar" method="post">
        <button type="submit">Actualizar Ahora</button>
    </form>
    ''', estado=estado)

@app.route('/actualizar', methods=['POST'])
def actualizar():
    threading.Thread(target=actualizar_data_warehouse).start()
    return "Proceso de actualización iniciado. <a href='/'>Volver</a>", 202

if __name__ == '__main__':
    # Iniciar la actualización al arrancar
    actualizar_data_warehouse()

    # Programar la tarea para que se ejecute cada 5 minutos
    schedule.every(5).minutes.do(job)

    # Ejecutar el servidor Flask y el scheduler en threads separados
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(1)

    threading.Thread(target=run_scheduler).start()
    app.run(host='172.22.187.202', port=5000)

