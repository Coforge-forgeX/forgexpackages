"""
Factory class for creating database adapter instances.
Implements the Factory Pattern to instantiate the appropriate adapter
based on configuration or database type.
"""
import os
import logging
from typing import Optional, Dict
from .base import DatabaseAdapter
from .mongodb_adapter import MongoDBAdapter
from .documentdb_adapter import DocumentDBAdapter
from .config import DBSettings

class DatabaseAdapterFactory:
	_adapters: Dict[str, DatabaseAdapter] = {
		'mongodb': MongoDBAdapter(),
		'documentdb': DocumentDBAdapter(),
	}

	@classmethod
	def create_adapter(cls, db_type: Optional[str] = None) -> DatabaseAdapter:
		if db_type is None:
			db_type = os.getenv('DB_TYPE', 'mongodb').lower()
		else:
			db_type = db_type.lower()
		if db_type not in cls._adapters:
			supported_types = ', '.join(cls._adapters.keys())
			raise ValueError(
				f"Unsupported database type: '{db_type}'. "
				f"Supported types are: {supported_types}"
			)
		logging.info(f"Using database adapter: {db_type}")
		return cls._adapters[db_type]

	@classmethod
	def create_client_from_settings(cls, settings: DBSettings, **kwargs):
		"""
		Create a database client using a DBSettings instance.
		"""
		adapter = cls.create_adapter(settings.db_type)
		return adapter.create_client(settings=settings, **kwargs)

	@classmethod
	def register_adapter(cls, db_type: str, adapter: DatabaseAdapter) -> None:
		cls._adapters[db_type.lower()] = adapter
		logging.info(f"Registered custom adapter: {db_type}")
