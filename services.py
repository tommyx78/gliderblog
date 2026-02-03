from models import DeviceUpdate

class DeviceService:
    def __init__(self, db, batch):
        self.db = db
        self.batch = batch

    def update_wifi(self, d: DeviceUpdate):
        conn = self.db.conn()
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO devices (device_id, ssid_wifi, password_wifi)
                VALUES (%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    ssid_wifi=VALUES(ssid_wifi),
                    password_wifi=VALUES(password_wifi)
            """, (d.device_id, d.ssid_wifi, d.password_wifi))
        conn.commit()
        conn.close()
