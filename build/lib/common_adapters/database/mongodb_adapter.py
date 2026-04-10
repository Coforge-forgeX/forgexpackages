"""
Adapter implementation for MongoDB.
Provides MongoDB-specific client creation and configuration.
"""
from pymongo import MongoClient
import certifi
import logging

from .base import DatabaseAdapter
from .config import DBSettings

class MongoDBAdapter(DatabaseAdapter):
	def create_client(self, connection_uri: str = None, settings: DBSettings = None, **kwargs) -> MongoClient:
		"""
		Create a MongoDB client using either a provided connection_uri or a DBSettings instance.
		"""
		if settings is not None:
			connection_uri = settings.db_uri
			db_type = settings.db_type
		else:
			db_type = kwargs.pop('db_type', 'mongodb')
            
		if not connection_uri or not connection_uri.startswith(('mongodb://', 'mongodb+srv://')):
			raise ValueError(f"Invalid MongoDB URI format. Must start with mongodb:// or mongodb+srv://")
		if 'docdb.amazonaws.com' in connection_uri:
			logging.warning("\u26a0\ufe0f  Detected DocumentDB endpoint with MongoDB adapter. Consider using DB_TYPE=documentdb")
        
		connection_uri = self.escape_mongodb_uri(connection_uri)
		logging.info(f"Initializing MongoDB connection (DB_TYPE={db_type})")
		default_config = {
			'tlsCAFile': certifi.where(),
			'maxPoolSize': 50,
			'minPoolSize': 0,
			'maxIdleTimeMS': 45000,
			'serverSelectionTimeoutMS': 5000,
			'retryWrites': True,
			'retryReads': True,
			'connectTimeoutMS': 10000,
			'socketTimeoutMS': 45000,
			'waitQueueTimeoutMS': 10000,
		}
		config = {**default_config, **kwargs}
		logging.info("Creating MongoDB client connection...")
		client = MongoClient(connection_uri, **config)
		return client

	def get_database(self, client: MongoClient, database_name: str):
		return client[database_name]

	def ping(self, client: MongoClient) -> bool:
		try:
			client.admin.command('ping')
			return True
		except Exception as e:
			logging.error(f"MongoDB ping failed: {e}")
			return False

	def close(self, client: MongoClient) -> None:
		if client:
			client.close()
