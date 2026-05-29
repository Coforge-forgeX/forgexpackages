"""
Examples demonstrating how to use ConfigurableAI.
"""

import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from configurableAI.manager import ConfigurableAIManager, get_ai_manager


async def basic_example():
    """Basic usage example."""
    print("=== Basic Example ===")
    
    # Create manager
    manager = ConfigurableAIManager()
    
    # Configure OpenAI provider from environment
    try:
        manager.configure_from_env("openai")
        
        # Generate text
        response = await manager.generate_text("What is the capital of France?")
        print(f"Response: {response}")
        
        # Generate embeddings
        embeddings = await manager.generate_embeddings(["Hello", "World"])
        print(f"Embeddings shape: {len(embeddings)} x {len(embeddings[0])}")
        
    except Exception as e:
        print(f"Error: {e}")


async def multi_provider_example():
    """Example using multiple providers."""
    print("\n=== Multi-Provider Example ===")
    
    manager = ConfigurableAIManager()
    
    # Configure multiple providers
    providers_to_try = ["openai", "azure", "gcp"]
    
    for provider in providers_to_try:
        try:
            manager.configure_from_env(provider)
            print(f"[OK] Configured {provider}")
        except Exception as e:
            print(f"[ERROR] Failed to configure {provider}: {e}")
    
    # List configured providers
    configured = manager.list_configured_providers()
    print(f"Configured providers: {configured}")
    
    # Try generating text with different providers
    prompt = "Explain machine learning in one sentence."
    
    for provider in configured:
        try:
            response = await manager.generate_text(prompt, provider=provider)
            print(f"{provider.upper()}: {response}")
        except Exception as e:
            print(f"[ERROR] Error with {provider}: {e}")


async def config_dict_example():
    """Example using dictionary configuration."""
    print("\n=== Dictionary Configuration Example ===")
    
    manager = ConfigurableAIManager()
    
    # Configure with dictionary (using dummy values for demo)
    openai_config = {
        "api_key": os.getenv("OPENAI_API_KEY", "dummy-key"),
        "model": "gpt-3.5-turbo",
        "organization": os.getenv("OPENAI_ORGANIZATION")
    }
    
    try:
        manager.configure_provider("openai", openai_config)
        print("[OK] Configured OpenAI with dictionary")
        
        # Set as current provider
        manager.set_current_provider("openai")
        print(f"Current provider: {manager.get_current_provider()}")
        
    except Exception as e:
        print(f"[ERROR] Configuration error: {e}")


async def file_config_example():
    """Example using file configuration."""
    print("\n=== File Configuration Example ===")
    
    # Create a sample config file
    config_content = {
        "default_provider": "openai",
        "providers": {
            "openai": {
                "api_key": os.getenv("OPENAI_API_KEY", "dummy-key"),
                "model": "gpt-3.5-turbo",
                "organization": os.getenv("OPENAI_ORGANIZATION")
            },
            "azure": {
                "api_key": os.getenv("AZURE_API_KEY", "dummy-key"),
                "endpoint": os.getenv("AZURE_ENDPOINT", "https://dummy.openai.azure.com/"),
                "deployment_name": "gpt-4",
                "api_version": "2023-12-01-preview"
            }
        }
    }
    
    import json
    config_file = "temp_ai_config.json"
    
    try:
        # Write config file
        with open(config_file, 'w') as f:
            json.dump(config_content, f, indent=2)
        
        # Configure from file
        manager = ConfigurableAIManager()
        manager.configure_from_file(config_file)
        
        print(f"[OK] Configured from file: {config_file}")
        print(f"Current provider: {manager.get_current_provider()}")
        print(f"Configured providers: {manager.list_configured_providers()}")
        
    except Exception as e:
        print(f"[ERROR] File configuration error: {e}")
    finally:
        # Clean up
        if os.path.exists(config_file):
            os.remove(config_file)


async def convenience_function_example():
    """Example using convenience function."""
    print("\n=== Convenience Function Example ===")
    
    try:
        # Quick setup
        manager = get_ai_manager("openai", auto_configure=True)
        
        print(f"[OK] Quick setup complete")
        print(f"Current provider: {manager.get_current_provider()}")
        
        # Generate text
        response = await manager.generate_text("Hello, AI!")
        print(f"Response: {response}")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")


async def error_handling_example():
    """Example demonstrating error handling."""
    print("\n=== Error Handling Example ===")
    
    manager = ConfigurableAIManager()
    
    # Try to use unconfigured provider
    try:
        await manager.generate_text("Hello")
    except ValueError as e:
        print(f"[OK] Caught expected error: {e}")
    
    # Try to configure invalid provider
    try:
        manager.configure_from_env("invalid_provider")
    except ValueError as e:
        print(f"[OK] Caught expected error: {e}")
    
    # Try to set invalid current provider
    try:
        manager.set_current_provider("nonexistent")
    except ValueError as e:
        print(f"[OK] Caught expected error: {e}")


async def main():
    """Run all examples."""
    print("ConfigurableAI Examples")
    print("=" * 50)
    
    await basic_example()
    await multi_provider_example()
    await config_dict_example()
    await file_config_example()
    await convenience_function_example()
    await error_handling_example()
    
    print("\n" + "=" * 50)
    print("Examples completed!")


if __name__ == "__main__":
    asyncio.run(main())