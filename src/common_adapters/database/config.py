from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal
import os


_DB_SETTINGS: Optional[DBSettings] = None

def initialize_db_settings() -> DBSettings:
	"""
	Initialize and cache DBSettings from environment variables.
	Returns the singleton DBSettings instance.
	"""
	global _DB_SETTINGS
	if _DB_SETTINGS is None:
		_DB_SETTINGS = DBSettings.from_env()
	return _DB_SETTINGS
"""
DBSettings: Centralized configuration for database adapters.
Loads and validates all required environment variables for DB connection.
"""

DBType = Literal["mongodb", "documentdb"]

@dataclass
class DBSettings:
	"""
	Settings for selecting and configuring the database adapter/provider.
	Loads from environment variables using from_env().
	"""
	db_type: DBType
	db_uri: str
	tls_ca_file: Optional[str] = None
	auto_download_cert: bool = False
	# Add more DB config fields as needed

	@staticmethod
	def from_env() -> DBSettings:
		"""
		Create DBSettings from environment variables.
		Environment Variables:
			DB_TYPE: 'mongodb' or 'documentdb' (default: mongodb)
			DB_URI: MongoDB/DocumentDB URI (required)
			DOCUMENTDB_CA_FILE: Path to CA file (optional, for DocumentDB)
			AUTO_DOWNLOAD_CERT: true/false (optional, for DocumentDB)
		"""
		db_type = os.getenv("DB_TYPE", "mongodb").strip().lower()
		if db_type not in {"mongodb", "documentdb"}:
			raise ValueError("DB_TYPE must be 'mongodb' or 'documentdb'")
		db_uri = os.getenv("MONGODB_DATABASE_URI")
		if not db_uri:
			raise ValueError("DB_URI environment variable is required.")
		tls_ca_file = os.getenv("DOCUMENTDB_CA_FILE")
		auto_download_cert = os.getenv("AUTO_DOWNLOAD_CERT", "false").lower() in ("true", "1", "yes")
		return DBSettings(
			db_type=db_type,
			db_uri=db_uri,
			tls_ca_file=tls_ca_file,
			auto_download_cert=auto_download_cert,
		)
