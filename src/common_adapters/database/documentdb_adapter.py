"""
Adapter implementation for AWS DocumentDB.
Provides DocumentDB-specific client creation and configuration.
"""
from pymongo import MongoClient
import logging
import os
from urllib.parse import urlparse, parse_qs

from .base import DatabaseAdapter
from .config import DBSettings
import urllib.request

class DocumentDBAdapter(DatabaseAdapter):
	AWS_RDS_CA_CERT_URL = "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem"

	def _download_certificate(self, cert_path: str) -> bool:
		try:
			logging.info(f"Downloading AWS RDS CA certificate from {self.AWS_RDS_CA_CERT_URL}")
			logging.info(f"Saving to: {cert_path}")
			cert_dir = os.path.dirname(cert_path)
			if cert_dir and not os.path.exists(cert_dir):
				os.makedirs(cert_dir, exist_ok=True)
				logging.info(f"Created directory: {cert_dir}")
			urllib.request.urlretrieve(self.AWS_RDS_CA_CERT_URL, cert_path)
			if os.path.isfile(cert_path) and os.path.getsize(cert_path) > 1000:
				logging.info(f"\u2705 Certificate downloaded successfully: {os.path.getsize(cert_path)} bytes")
				return True
			else:
				logging.error("Downloaded file is too small or doesn't exist")
				return False
		except Exception as e:
			logging.error(f"Failed to download certificate: {e}")
			raise Exception(
				f"Failed to download AWS RDS CA certificate.\n"
				f"Error: {e}\n\n"
				f"Please download manually from:\n"
				f"{self.AWS_RDS_CA_CERT_URL}\n\n"
				f"Save to: {cert_path}"
			)

	def _resolve_and_validate_tls_certificate(self, connection_uri: str, kwargs):
		tls_ca_file = None
		if 'tlsCAFile' in kwargs:
			tls_ca_file = kwargs.pop('tlsCAFile')
			logging.info(f"Using tlsCAFile from kwargs: {tls_ca_file}")
		elif os.getenv('DOCUMENTDB_CA_FILE'):
			tls_ca_file = os.getenv('DOCUMENTDB_CA_FILE')
			logging.info(f"Using tlsCAFile from DOCUMENTDB_CA_FILE env: {tls_ca_file}")
		else:
			try:
				parsed = urlparse(connection_uri)
				params = parse_qs(parsed.query)
				if 'tlsCAFile' in params and params['tlsCAFile']:
					tls_ca_file = params['tlsCAFile'][0]
					logging.info(f"Using tlsCAFile from URI: {tls_ca_file}")
			except Exception as e:
				logging.debug(f"Could not parse URI for tlsCAFile: {e}")
		if not tls_ca_file:
			error_msg = (
				"\u274c CRITICAL: DocumentDB requires TLS certificate but none provided.\n"
				"You must set the DOCUMENTDB_CA_FILE environment variable or provide tlsCAFile in your URI or kwargs.\n"
				"Download the AWS RDS CA bundle from:\n"
				f"  {self.AWS_RDS_CA_CERT_URL}\n"
				"and set DOCUMENTDB_CA_FILE to its path."
			)
			logging.error(error_msg)
			raise ValueError(error_msg)
		if not os.path.isabs(tls_ca_file):
			current_file_dir = os.path.dirname(os.path.abspath(__file__))
			project_root = os.path.abspath(os.path.join(current_file_dir, '..'))
			absolute_path = os.path.join(project_root, tls_ca_file)
			logging.info(f"Resolved relative certificate path:\n  Original: {tls_ca_file}\n  Absolute: {absolute_path}")
			tls_ca_file = absolute_path
		tls_ca_file = os.path.normpath(tls_ca_file)
		if not os.path.isfile(tls_ca_file):
			auto_download = os.getenv('AUTO_DOWNLOAD_CERT', 'false').lower() in ('true', '1', 'yes')
			if auto_download:
				logging.warning(f"Certificate file not found: {tls_ca_file}")
				logging.info("AUTO_DOWNLOAD_CERT=true - Attempting automatic download...")
				try:
					self._download_certificate(tls_ca_file)
					logging.info("\u2705 Certificate downloaded and ready to use")
				except Exception as download_error:
					logging.error(f"Auto-download failed: {download_error}")
					raise
			else:
				error_msg = (
					f"\u274c TLS certificate file not found: {tls_ca_file}\n"
					f"You must download the AWS RDS CA bundle and set DOCUMENTDB_CA_FILE to its path."
				)
				logging.error(error_msg)
				raise FileNotFoundError(error_msg)
		if not os.access(tls_ca_file, os.R_OK):
			error_msg = (
				f"\u274c TLS certificate file exists but is not readable: {tls_ca_file}\n"
				f"Check file permissions."
			)
			logging.error(error_msg)
			raise PermissionError(error_msg)
		logging.info(f"\u2705 Using valid TLS certificate: {tls_ca_file}")
		return tls_ca_file

	def create_client(self, connection_uri: str = None, settings: DBSettings = None, **kwargs) -> MongoClient:
		"""
		Create a DocumentDB client using either a provided connection_uri or a DBSettings instance.
		"""
		if settings is not None:
			connection_uri = settings.db_uri
			db_type = settings.db_type
			if settings.tls_ca_file:
				kwargs['tlsCAFile'] = settings.tls_ca_file
			if settings.auto_download_cert:
				os.environ['AUTO_DOWNLOAD_CERT'] = 'true'
		else:
			db_type = kwargs.pop('db_type', 'documentdb')
		if not connection_uri or not connection_uri.startswith('mongodb://'):
			if connection_uri and connection_uri.startswith('mongodb+srv://'):
				raise ValueError(
					"\u274c DocumentDB does not support mongodb+srv:// URIs. "
					"Use mongodb:// format instead. "
					"Example: mongodb://user:pass@cluster.region.docdb.amazonaws.com:27017/?tls=true"
				)
			else:
				raise ValueError(f"Invalid DocumentDB URI format. Must start with mongodb://")
		if '.mongodb.net' in connection_uri:
			logging.error(
				"\u274c Detected MongoDB Atlas endpoint (.mongodb.net) with DocumentDB adapter. "
				"Change DB_TYPE=mongodb to use MongoDB Atlas."
			)
			raise ValueError(
				"URI mismatch: MongoDB Atlas endpoint detected but DB_TYPE=documentdb. "
				"Either change DB_TYPE=mongodb or use a DocumentDB endpoint (*.docdb.amazonaws.com)"
			)
		if 'docdb.amazonaws.com' not in connection_uri:
			logging.warning(
				"\u26a0\ufe0f  URI does not contain 'docdb.amazonaws.com'. "
				"Ensure this is a valid AWS DocumentDB endpoint."
			)
		if 'tls=true' not in connection_uri.lower() and 'ssl=true' not in connection_uri.lower():
			logging.warning("\u26a0\ufe0f  DocumentDB requires TLS. Consider adding '?tls=true' to your URI")
		connection_uri = self.escape_mongodb_uri(connection_uri)
		logging.info(f"Initializing DocumentDB connection (DB_TYPE={db_type})")
		tls_ca_file = self._resolve_and_validate_tls_certificate(connection_uri, kwargs)
		default_config = {
			'tls': True,
			'tlsCAFile': tls_ca_file,
			'retryWrites': False,
			'retryReads': False,
			'maxPoolSize': 50,
			'minPoolSize': 0,
			'maxIdleTimeMS': 45000,
			'serverSelectionTimeoutMS': 5000,
			'connectTimeoutMS': 10000,
			'socketTimeoutMS': 45000,
			'waitQueueTimeoutMS': 10000,
		}
		config = {**default_config, **kwargs}
		logging.info("Creating AWS DocumentDB client connection...")
		try:
			client = MongoClient(connection_uri, **config)
		except Exception as e:
			if 'SSL' in str(e) or 'certificate' in str(e).lower():
				logging.error(f"\u274c SSL/Certificate error: {e}\nCheck your TLS certificate and connection string.")
			raise
		return client

	def get_database(self, client: MongoClient, database_name: str):
		return client[database_name]

	def ping(self, client: MongoClient) -> bool:
		try:
			client.admin.command('ping')
			return True
		except Exception as e:
			logging.error(f"DocumentDB ping failed: {e}")
			return False

	def close(self, client: MongoClient) -> None:
		if client:
			client.close()
			logging.info("DocumentDB connection closed")
