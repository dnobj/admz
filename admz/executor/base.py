"""
Abstract base for operation executors.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from admz.executor.models import StepResult


class BaseExecutor(ABC):
    """
    Abstract executor interface.

    Each API family has its own executor that knows how to build
    HTTP requests and handle auth for that family's protocol.
    """

    @property
    @abstractmethod
    def family(self) -> str:
        """API family this executor handles (e.g., 'vapix', 'acs')."""

    @abstractmethod
    async def execute(
        self,
        operation: Dict[str, Any],
        device: Dict[str, Any],
        credentials: Dict[str, Any],
        params: Dict[str, str],
    ) -> StepResult:
        """
        Execute an operation against a device.

        Args:
            operation: Operation spec from the catalog (parsed YAML).
            device: Device info from the registry.
            credentials: Auth credentials from the registry.
            params: User-provided parameters for this operation.

        Returns:
            StepResult with success/failure and response data.
        """
