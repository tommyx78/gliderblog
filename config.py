import configparser

class AppConfig:
    def __init__(self, path="config.ini"):
        cfg = configparser.ConfigParser()
        cfg.read(path)

        # Sezione [server]
        self.server = {
            "host": cfg["server"].get("host", "0.0.0.0"),
            "port": int(cfg["server"].get("port", 7979))
        }
        
        
        self.host = self.server["host"]
        self.port = self.server["port"]


        self.db = {
            "host": cfg["database"]["host"],
            "port": int(cfg["database"]["port"]),
            "user": cfg["database"]["user"],
            "password": cfg["database"]["password"],
            "database": cfg["database"]["name"],
        }


        self.smtp = {
            "server": cfg["smtp"]["server"],
            "port": int(cfg["smtp"]["port"]),
            "user": cfg["smtp"]["user"],
            "password": cfg["smtp"]["password"],
        }

 
        self.email = {
            "hostlink": cfg["email"]["hostlink"],
            "portlink": cfg["email"]["portlink"],
        }