import mysql.connector
import requests
from le_beta_vis.common.RedisBackedConfigurationService import RedisBackedConfigurationService
import os

class EventPersistence():
    """
    Docstring for EventPersistence
    """
    def __init__(self):
        self.config = RedisBackedConfigurationService()
        self.db_host="localhost",
        self.db_user=os.environ.get("DB_USER"),
        self.db_password=os.environ.get("DB_PASS"),
        self.database=os.environ.get("DB_NAME")
        self.port = 8082

    def db_connect(self):
        """
        Opens a connection to the database with the values from the configuration
        """
        try:
            self.conn = mysql.connector.connect(
                    host=self.db_host,
                    user=self.db_user,
                    password=self.db_password,
                    database=self.database
            )
        except mysql.connector.Error as err:
            print(f"Could not connect: {err}")

    def store_fits(self, fits: dict) -> int:
        pass
