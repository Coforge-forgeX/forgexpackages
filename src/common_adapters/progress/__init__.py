"""Progress reporting abstraction (ports + adapters).

This package keeps long-running API progress transport-agnostic so the same
business flow can publish progress to WebSockets, event buses, or no-op sinks.

Agents create publishers with explicit configuration via registry factory functions.
"""

from .factory import create_progress_reporter
from .models import ProgressEvent
from .ports import ProgressPublisher, NullProgressPublisher, CompositeProgressPublisher
from .reporter import ProgressReporter
from .registry import (
    create_null_publisher,
    create_log_publisher,
    create_local_relay_publisher,
    create_azure_servicebus_publisher,
    create_aws_eventbridge_publisher,
)
from .transports import (
    LogProgressPublisher,
    AzureServiceBusProgressPublisher,
    AwsEventBridgeProgressPublisher,
    LocalRelayProgressPublisher,
    InMemoryWebSocketProgressPublisher,
)

__all__ = [
    # Core
    "ProgressEvent",
    "ProgressReporter",
    "create_progress_reporter",
    # Ports
    "ProgressPublisher",
    "NullProgressPublisher",
    "CompositeProgressPublisher",
    # Registry Factory Functions
    "create_null_publisher",
    "create_log_publisher",
    "create_local_relay_publisher",
    "create_azure_servicebus_publisher",
    "create_aws_eventbridge_publisher",
    # Transports
    "LogProgressPublisher",
    "AzureServiceBusProgressPublisher",
    "AwsEventBridgeProgressPublisher",
    "LocalRelayProgressPublisher",
    "InMemoryWebSocketProgressPublisher",
]
