CREATE DATABASE `gliderblog_db` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

-- gliderblog_db.login definition

CREATE TABLE `login` (
  `UserID` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password` varchar(255) NOT NULL,
  `email` varchar(100) NOT NULL,
  `type` tinyint DEFAULT '1',
  `timestamp` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `email_token` varchar(100) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT '0',
  `reset_token` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`UserID`),
  UNIQUE KEY `alias` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO smart_db.login (username,password,email,`type`,`timestamp`,email_token,is_active,reset_token) VALUES
	('admin','$2b$12$OYAwVJOsnK27rP9SD1g78.CEwkyJEajUVSOgI/saVmx6267sCft5a','',0,'2026-02-03 10:08:37',NULL,1,NULL)
