"""
Abstract base class for database adapters.
Defines the interface that all database adapters must implement.
"""
from abc import ABC, abstractmethod
from typing import Any
import logging
from urllib.parse import quote_plus
import re

class DatabaseAdapter(ABC):
	@abstractmethod
	def create_client(self, connection_uri: str, **kwargs) -> Any:
		pass

	@abstractmethod
	def get_database(self, client: Any, database_name: str) -> Any:
		pass

	@abstractmethod
	def ping(self, client: Any) -> bool:
		pass

	@abstractmethod
	def close(self, client: Any) -> None:
		pass

	@staticmethod
	def escape_mongodb_uri(uri: str) -> str:
		if not uri:
			return uri
		protocol_pattern = r'^(mongodb(?:\+srv)?://)'
		protocol_match = re.match(protocol_pattern, uri)
		if not protocol_match:
			return uri
		protocol = protocol_match.group(1)
		remainder = uri[len(protocol):]
		last_at_index = remainder.rfind('@')
		if last_at_index == -1:
			return uri
		credentials = remainder[:last_at_index]
		host_and_rest = remainder[last_at_index + 1:]
		colon_index = credentials.find(':')
		if colon_index == -1:
			return uri
		username = credentials[:colon_index]
		password = credentials[colon_index + 1:]
		if '%' in username or '%' in password:
			logging.debug("URI credentials appear to be already encoded")
			return uri
		escaped_username = quote_plus(username)
		escaped_password = quote_plus(password)
		escaped_uri = f"{protocol}{escaped_username}:{escaped_password}@{host_and_rest}"
		if escaped_username != username or escaped_password != password:
			logging.info("\u2713 Automatically encoded credentials in database URI")
		return escaped_uri
