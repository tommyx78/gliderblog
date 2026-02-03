import bcrypt
import hashlib
from fastapi import HTTPException
from database import Database

class DeviceSecurity:
    def __init__(self, db: Database):
        self.db = db

    def verify_device(self, device_id: str, token: str):
        """
        Validates the device identity against the database.
        Raises 401 Unauthorized if the token is invalid.
        """
        conn = self.db.conn()
        with conn.cursor() as c:
            c.execute(
                "SELECT 1 FROM devices WHERE device_id=%s AND device_token=%s",
                (device_id, token)
            )
            ok = c.fetchone()
        conn.close()
        if not ok:
            raise HTTPException(401, "Invalid Token")

    @staticmethod
    def prepare_password(password: str) -> bytes:
        """
        Pre-hashes the password using SHA-256 to bypass the 72-character limit of bcrypt.
        Returns bytes ready for bcrypt processing.
        """
        # SHA-256 hashing ensures that even very long passwords result in a fixed-length string
        digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return digest.encode("utf-8")

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Generates a secure bcrypt hash to be stored in the database.
        """
        prepared = DeviceSecurity.prepare_password(password)
        # Generate salt and hash the prepared password
        hashed = bcrypt.hashpw(prepared, bcrypt.gensalt())
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verifies the provided password against the stored bcrypt hash.
        """
        prepared = DeviceSecurity.prepare_password(password)
        # Verify the password using bcrypt's secure comparison
        return bcrypt.checkpw(prepared, password_hash.encode("utf-8"))