"""
Progress Publisher Registry

Factory methods for creating progress publishers with explicit configuration.
Agent decides what it needs and passes explicit parameters.
"""

from __future__ import annotations

from .ports import CompositeProgressPublisher, NullProgressPublisher, ProgressPublisher
from .transports import (
    AwsEventBridgeProgressPublisher,
    AzureServiceBusProgressPublisher,
    LocalRelayProgressPublisher,
    LogProgressPublisher,
)


def create_null_publisher() -> ProgressPublisher:
    """Create a no-op progress publisher."""
    return NullProgressPublisher()


def create_log_publisher() -> ProgressPublisher:
    """Create a log-only progress publisher."""
    return LogProgressPublisher()


def create_local_relay_publisher(
    publish_url: str = "http://127.0.0.1:8090/publish",
) -> ProgressPublisher:
    """
    Create a local relay progress publisher with logging.
    
    Args:
        publish_url: URL for the local relay endpoint
    """
    return CompositeProgressPublisher([
        LogProgressPublisher(),
        LocalRelayProgressPublisher(publish_url),
    ])


def create_azure_servicebus_publisher(
    connection_string: str,
    entity_name: str,
    entity_type: str = "topic",
) -> ProgressPublisher:
    """
    Create an Azure Service Bus progress publisher with logging.
    
    Args:
        connection_string: Azure Service Bus connection string
        entity_name: Queue or topic name
        entity_type: Either "queue" or "topic"
    """
    return CompositeProgressPublisher([
        LogProgressPublisher(),
        AzureServiceBusProgressPublisher(connection_string, entity_name, entity_type),
    ])


def create_aws_eventbridge_publisher(
    bus_name: str = "default",
) -> ProgressPublisher:
    """
    Create an AWS EventBridge progress publisher with logging.
    
    Args:
        bus_name: EventBridge bus name
    """
    return CompositeProgressPublisher([
        LogProgressPublisher(),
        AwsEventBridgeProgressPublisher(bus_name),
    ])
