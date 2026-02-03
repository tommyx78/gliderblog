import bcrypt
import hashlib
from fastapi import HTTPException
from database import Database

class DeviceSecurity:
    def __init__(self, db: Database):
        self.db = db

    def verify_device(self, device_id: str, token: str):
        conn = self.db.conn()
        with conn.cursor() as c:
            c.execute(
                "SELECT 1 FROM devices WHERE device_id=%s AND device_token=%s",
                (device_id, token)
            )
            ok = c.fetchone()
        conn.close()
        if not ok:
            raise HTTPException(401, "Token non valido")

    @staticmethod
    def prepare_password(password: str) -> bytes:
        """
        Pre-hash SHA-256 per aggirare limite 72 byte
        Ritorna bytes pronti per bcrypt
        """
        digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return digest.encode("utf-8")

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Genera hash bcrypt da salvare nel DB
        """
        prepared = DeviceSecurity.prepare_password(password)
        hashed = bcrypt.hashpw(prepared, bcrypt.gensalt())
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verifica password contro hash salvato
        """
        prepared = DeviceSecurity.prepare_password(password)
        return bcrypt.checkpw(prepared, password_hash.encode("utf-8"))
