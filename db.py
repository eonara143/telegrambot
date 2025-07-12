import os
from dotenv import load_dotenv
import mysql.connector.pooling

load_dotenv()

dbconfig = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="scbphil_pool",
    pool_size=10,
    **dbconfig
)

def get_db():
    return pool.get_connection()
