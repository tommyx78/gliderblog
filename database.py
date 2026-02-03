from mysql.connector import pooling, Error
from fastapi import HTTPException

class Database:
    def __init__(self, cfg):
        self.pool = pooling.MySQLConnectionPool(
            pool_name="forno_pool",
            pool_size=10,
            **cfg
        )

    def conn(self):
        try:
            return self.pool.get_connection()
        except Error as e:
            raise HTTPException(500, f"Errore DB: {e}")
