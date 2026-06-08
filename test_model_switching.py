"""Test script for model switching functionality."""
import os
import sys

# Ensure MONGODB_DATABASE_URI is set
if not os.getenv("MONGODB_DATABASE_URI"):
    print("ERROR: MONGODB_DATABASE_URI env var must be set")
    sys.exit(1)

from common_adapters.configurableAI.llm_router_config_store import llm_router_config_store

TEST_WS = 9999
passed = 0
failed = 0


def test(name, fn):
    global passed, failed
    print(f"\n=== {name} ===")
    try:
        fn()
        print("  PASS")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1
    except Exception as e:
        print(f"  ERROR: {e}")
        failed += 1


def test_upsert_creates_available_models():
    result = llm_router_config_store.upsert_provider_credentials(
        workspace_id=TEST_WS,
        provider_name="azure",
        api_key="test-key-123",
        endpoint="https://test.openai.azure.com/",
        model="gpt-4.1",
        api_version="2024-12-01-preview",
        deployment_name="gpt-4.1",
        user_id=1,
    )
    models = result.get("available_models") or []
    print(f"  available_models: {models}")
    assert len(models) >= 1, f"Expected >=1 models, got {len(models)}"
    assert models[0]["model_name"] == "gpt-4.1"


def test_upsert_second_model_adds_to_list():
    result = llm_router_config_store.upsert_provider_credentials(
        workspace_id=TEST_WS,
        provider_name="azure",
        api_key="test-key-123",
        endpoint="https://test.openai.azure.com/",
        model="gpt-5.2",
        api_version="2024-12-01-preview",
        deployment_name="gpt-5.2",
        user_id=1,
    )
    models = result.get("available_models") or []
    print(f"  available_models: {models}")
    model_names = [m["model_name"] for m in models]
    assert "gpt-4.1" in model_names, "gpt-4.1 missing"
    assert "gpt-5.2" in model_names, "gpt-5.2 missing"


def test_get_credentials_returns_available_models():
    creds = llm_router_config_store.get_provider_credentials(TEST_WS, "azure")
    models = creds.get("available_models") or []
    print(f"  available_models: {models}")
    assert len(models) == 2, f"Expected 2, got {len(models)}"


def test_config_with_current_models():
    result = llm_router_config_store.create_or_update_configuration(
        workspace_id=TEST_WS,
        agent_id=5,
        configured_providers=["azure"],
        current_provider="azure",
        current_models={"azure": "gpt-4.1"},
        user_id=1,
    )
    print(f"  current_models: {result.get('current_models')}")
    assert result["current_models"] == {"azure": "gpt-4.1"}


def test_switch_provider_with_model():
    result = llm_router_config_store.switch_provider(
        workspace_id=TEST_WS,
        provider="azure",
        agent_id=5,
        model="gpt-5.2",
        user_id=1,
    )
    print(f"  current_models: {result.get('current_models')}")
    assert result["current_models"]["azure"] == "gpt-5.2"


def test_switch_provider_invalid_model_fails():
    try:
        llm_router_config_store.switch_provider(
            workspace_id=TEST_WS,
            provider="azure",
            agent_id=5,
            model="nonexistent-model",
            user_id=1,
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"  Correctly raised: {e}")


def test_build_config_with_override():
    config = llm_router_config_store.build_config_dict(TEST_WS, "azure", model_override="gpt-4.1")
    print(f"  model={config['model']}, deployment_name={config.get('deployment_name')}")
    assert config["model"] == "gpt-4.1"
    assert config["deployment_name"] == "gpt-4.1"


def test_build_config_without_override():
    config = llm_router_config_store.build_config_dict(TEST_WS, "azure")
    print(f"  model={config['model']} (should be provider default: gpt-5.2)")
    assert config["model"] == "gpt-5.2"


def test_switch_provider_without_model_keeps_existing():
    # Switch without model param should not reset current_models
    result = llm_router_config_store.switch_provider(
        workspace_id=TEST_WS,
        provider="azure",
        agent_id=5,
        user_id=1,
    )
    print(f"  current_models: {result.get('current_models')}")
    # Should still have gpt-5.2 from the earlier switch
    assert result["current_models"].get("azure") == "gpt-5.2"


if __name__ == "__main__":
    # Cleanup before tests
    llm_router_config_store.delete_workspace_configurations(TEST_WS)

    test("upsert creates available_models", test_upsert_creates_available_models)
    test("upsert second model adds to list", test_upsert_second_model_adds_to_list)
    test("get_credentials returns available_models", test_get_credentials_returns_available_models)
    test("config with current_models", test_config_with_current_models)
    test("switch_provider with model", test_switch_provider_with_model)
    test("switch_provider invalid model fails", test_switch_provider_invalid_model_fails)
    test("build_config_dict with override", test_build_config_with_override)
    test("build_config_dict without override", test_build_config_without_override)
    test("switch_provider without model keeps existing", test_switch_provider_without_model_keeps_existing)

    # Cleanup
    llm_router_config_store.delete_workspace_configurations(TEST_WS)
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
