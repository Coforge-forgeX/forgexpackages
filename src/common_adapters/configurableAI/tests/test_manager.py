"""
Tests for ConfigurableAI Manager.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from ..manager import ConfigurableAIManager, get_ai_manager
from ..config import AIProviderConfig, OpenAIConfig
from ..providers import ProviderRegistry, BaseAIProvider


class MockProvider(BaseAIProvider):
    """Mock provider for testing."""
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        return f"Mock response for: {prompt}"
    
    async def generate_embeddings(self, texts, **kwargs):
        return [[0.1, 0.2, 0.3] for _ in texts]
    
    def validate_config(self) -> bool:
        return True


@pytest.fixture
def manager():
    """Create a fresh manager for each test."""
    return ConfigurableAIManager()


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    return AIProviderConfig(
        provider_name="mock",
        api_key="test-key",
        model="test-model"
    )


class TestConfigurableAIManager:
    
    def test_initialization(self):
        """Test manager initialization."""
        manager = ConfigurableAIManager()
        assert manager.get_current_provider() is None
        assert manager.list_configured_providers() == []
    
    def test_initialization_with_default(self):
        """Test manager initialization with default provider."""
        manager = ConfigurableAIManager(default_provider="test")
        assert manager._default_provider == "test"
    
    def test_configure_provider(self, manager, mock_config):
        """Test provider configuration."""
        # Register mock provider
        ProviderRegistry.register_provider("mock", MockProvider)
        
        manager.configure_provider("mock", mock_config)
        
        assert "mock" in manager.list_configured_providers()
        assert manager.get_current_provider() == "mock"
    
    def test_configure_provider_with_dict(self, manager):
        """Test provider configuration with dictionary."""
        ProviderRegistry.register_provider("mock", MockProvider)
        
        config_dict = {
            "api_key": "test-key",
            "model": "test-model"
        }
        
        manager.configure_provider("mock", config_dict)
        
        assert "mock" in manager.list_configured_providers()
    
    def test_configure_invalid_provider(self, manager, mock_config):
        """Test configuration with invalid provider."""
        with pytest.raises(ValueError, match="Provider 'invalid' not found"):
            manager.configure_provider("invalid", mock_config)
    
    def test_set_current_provider(self, manager, mock_config):
        """Test setting current provider."""
        ProviderRegistry.register_provider("mock", MockProvider)
        manager.configure_provider("mock", mock_config)
        
        manager.set_current_provider("mock")
        assert manager.get_current_provider() == "mock"
    
    def test_set_invalid_current_provider(self, manager):
        """Test setting invalid current provider."""
        with pytest.raises(ValueError, match="Provider 'invalid' is not configured"):
            manager.set_current_provider("invalid")
    
    @pytest.mark.asyncio
    async def test_generate_text(self, manager, mock_config):
        """Test text generation."""
        ProviderRegistry.register_provider("mock", MockProvider)
        manager.configure_provider("mock", mock_config)
        
        response = await manager.generate_text("Hello")
        assert response == "Mock response for: Hello"
    
    @pytest.mark.asyncio
    async def test_generate_text_with_specific_provider(self, manager, mock_config):
        """Test text generation with specific provider."""
        ProviderRegistry.register_provider("mock", MockProvider)
        manager.configure_provider("mock", mock_config)
        
        response = await manager.generate_text("Hello", provider="mock")
        assert response == "Mock response for: Hello"
    
    @pytest.mark.asyncio
    async def test_generate_text_no_provider(self, manager):
        """Test text generation without configured provider."""
        with pytest.raises(ValueError, match="No provider specified"):
            await manager.generate_text("Hello")
    
    @pytest.mark.asyncio
    async def test_generate_embeddings(self, manager, mock_config):
        """Test embedding generation."""
        ProviderRegistry.register_provider("mock", MockProvider)
        manager.configure_provider("mock", mock_config)
        
        embeddings = await manager.generate_embeddings(["Hello", "World"])
        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
    
    @patch.dict('os.environ', {
        'OPENAI_API_KEY': 'test-key',
        'OPENAI_MODEL': 'gpt-3.5-turbo'
    })
    def test_configure_from_env(self, manager):
        """Test configuration from environment variables."""
        ProviderRegistry.register_provider("openai", MockProvider)
        
        manager.configure_from_env("openai")
        
        assert "openai" in manager.list_configured_providers()
    
    def test_configure_from_file(self, manager, tmp_path):
        """Test configuration from file."""
        ProviderRegistry.register_provider("mock", MockProvider)
        
        config_data = {
            "default_provider": "mock",
            "providers": {
                "mock": {
                    "api_key": "test-key",
                    "model": "test-model"
                }
            }
        }
        
        config_file = tmp_path / "config.json"
        import json
        config_file.write_text(json.dumps(config_data))
        
        manager.configure_from_file(str(config_file))
        
        assert "mock" in manager.list_configured_providers()
        assert manager.get_current_provider() == "mock"


class TestConvenienceFunction:
    
    @patch.dict('os.environ', {
        'OPENAI_API_KEY': 'test-key',
        'OPENAI_MODEL': 'gpt-3.5-turbo'
    })
    def test_get_ai_manager(self):
        """Test convenience function."""
        ProviderRegistry.register_provider("openai", MockProvider)
        
        manager = get_ai_manager("openai", auto_configure=True)
        
        assert isinstance(manager, ConfigurableAIManager)
        assert "openai" in manager.list_configured_providers()
    
    def test_get_ai_manager_no_auto_configure(self):
        """Test convenience function without auto-configure."""
        manager = get_ai_manager("test", auto_configure=False)
        
        assert isinstance(manager, ConfigurableAIManager)
        assert manager.list_configured_providers() == []


if __name__ == "__main__":
    pytest.main([__file__])