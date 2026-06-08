"""Test script: add models to providers and test model switching."""
import os
import sys

os.environ["MONGODB_DATABASE_URI"] = "mongodb+srv://admin:UrplSapIBJizyk3X@cluster0.b6i9x4z.mongodb.net/"

from common_adapters.configurableAI.llm_router_config_store import llm_router_config_store

WORKSPACE_ID = 886

print("=" * 60)
print("STEP 1: Add gpt-5-chat and gemini-2-5-flash to Azure provider")
print("=" * 60)

# Get current azure creds
creds = llm_router_config_store.get_provider_credentials(WORKSPACE_ID, "azure")
if not creds:
    print("ERROR: No azure credentials found for workspace 889")
    sys.exit(1)

print(f"  Current azure model: {creds['model']}")
print(f"  Current available_models: {creds.get('available_models')}")

# Add gpt-5-chat to azure
print("\n  Adding gpt-5-chat to azure...")
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
available_models = creds.get("available_models") or []

# Add models if not already present
for model_entry in [
    {"model_name": "gpt-4.1", "deployment_name": "gpt-4.1"},
    {"model_name": "gpt-5-chat", "deployment_name": "gpt-5-chat"},
    {"model_name": "gemini-2-5-flash", "deployment_name": "gemini-2-5-flash"},
]:
    if not any(m["model_name"] == model_entry["model_name"] for m in available_models):
        available_models.append(model_entry)

# Update in DB directly
from common_adapters.configurableAI.llm_router_config_store import _get_mongo_client, LLM_CONFIG_DB_NAME, LLM_CONFIG_COLLECTION_NAME
client = _get_mongo_client()
col = client[LLM_CONFIG_DB_NAME][LLM_CONFIG_COLLECTION_NAME]
col.update_one(
    {"workspace_id": WORKSPACE_ID},
    {"$set": {
        "provider_credentials.azure.available_models": available_models,
        "provider_credentials.azure.updated_at": now,
    }}
)

# Verify
creds = llm_router_config_store.get_provider_credentials(WORKSPACE_ID, "azure")
print(f"  Updated available_models: {creds.get('available_models')}")
assert len(creds["available_models"]) == 3, f"Expected 3 models, got {len(creds['available_models'])}"
print("  PASS")

print("\n" + "=" * 60)
print("STEP 2: Setup quasar with claude-sonnet-4")
print("=" * 60)
creds_q = llm_router_config_store.get_provider_credentials(WORKSPACE_ID, "quasar")
if not creds_q:
    print("  Quasar not configured, adding it...")
    llm_router_config_store.upsert_provider_credentials(
        workspace_id=WORKSPACE_ID,
        provider_name="quasar",
        api_key="1c2beb07-419b-4a4e-98bf-c87cdd66f35d",
        endpoint="https://quasarmarket.coforge.com/qag/llmrouter-api/v2/chat/completions",
        model="claude-sonnet-4",
        user_id=247,
    )
    creds_q = llm_router_config_store.get_provider_credentials(WORKSPACE_ID, "quasar")
print(f"  Quasar model: {creds_q['model']}")
print(f"  Quasar available_models: {creds_q.get('available_models')}")
print("  PASS")

print("\n" + "=" * 60)
print("STEP 3: Test switch_provider with model param")
print("=" * 60)

# Ensure agent 1 has both providers configured
llm_router_config_store.create_or_update_configuration(
    workspace_id=WORKSPACE_ID,
    agent_id=1,
    configured_providers=["azure", "quasar"],
    current_provider="azure",
    user_id=247,
)

# Switch agent 1 to azure with gpt-5-chat
print("\n  Switching agent 1 to azure + gpt-5-chat...")
result = llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID,
    provider="azure",
    agent_id=1,
    model="gpt-5-chat",
    user_id=247,
)
print(f"  Result current_models: {result.get('current_models')}")
assert result["current_models"]["azure"] == "gpt-5-chat", f"Expected gpt-5-chat, got {result['current_models'].get('azure')}"
assert result["current_provider"] == "azure"
print("  PASS")

# Switch agent 1 to azure with gemini-2-5-flash
print("\n  Switching agent 1 to azure + gemini-2-5-flash...")
result = llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID,
    provider="azure",
    agent_id=1,
    model="gemini-2-5-flash",
    user_id=247,
)
print(f"  Result current_models: {result.get('current_models')}")
assert result["current_models"]["azure"] == "gemini-2-5-flash"
print("  PASS")

# Switch model only (same provider)
print("\n  Switching agent 1 to azure + gpt-4.1 (back to default)...")
result = llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID,
    provider="azure",
    agent_id=1,
    model="gpt-4.1",
    user_id=247,
)
print(f"  Result current_models: {result.get('current_models')}")
assert result["current_models"]["azure"] == "gpt-4.1"
print("  PASS")

print("\n" + "=" * 60)
print("STEP 4: Test switch_provider WITHOUT model (should keep existing)")
print("=" * 60)

# First set a model
llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID, provider="azure", agent_id=1,
    model="gpt-5-chat", user_id=247,
)

# Now switch to quasar without model
result = llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID,
    provider="quasar",
    agent_id=1,
    user_id=247,
)
print(f"  After switching to quasar (no model): current_models={result.get('current_models')}")
# The azure model should still be preserved
assert result["current_models"].get("azure") == "gpt-5-chat", "azure model should be preserved"
assert result["current_provider"] == "quasar"
print("  PASS")

# Switch back to azure without model - should still have gpt-5-chat
result = llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID,
    provider="azure",
    agent_id=1,
    user_id=247,
)
print(f"  After switching back to azure (no model): current_models={result.get('current_models')}")
assert result["current_models"].get("azure") == "gpt-5-chat", "azure model should persist"
print("  PASS")

print("\n" + "=" * 60)
print("STEP 5: Test build_config_dict uses model override")
print("=" * 60)

# Agent 1 has current_models.azure = gpt-5-chat
config = llm_router_config_store.build_config_dict(WORKSPACE_ID, "azure", model_override="gpt-5-chat")
print(f"  With override 'gpt-5-chat': model={config['model']}, deployment={config.get('deployment_name')}")
assert config["model"] == "gpt-5-chat"
assert config["deployment_name"] == "gpt-5-chat"

config = llm_router_config_store.build_config_dict(WORKSPACE_ID, "azure")
print(f"  Without override: model={config['model']} (provider default)")
assert config["model"] == "gpt-4.1"
print("  PASS")

print("\n" + "=" * 60)
print("STEP 6: Test invalid model switch fails")
print("=" * 60)
try:
    llm_router_config_store.switch_provider(
        workspace_id=WORKSPACE_ID, provider="azure", agent_id=1,
        model="nonexistent-model", user_id=247,
    )
    print("  FAIL: should have raised ValueError")
    sys.exit(1)
except ValueError as e:
    print(f"  Correctly rejected: {e}")
    print("  PASS")

print("\n" + "=" * 60)
print("STEP 7: Verify DB document has current_models saved")
print("=" * 60)
doc = col.find_one({"workspace_id": WORKSPACE_ID})
agent1_config = doc["agent_configs"]["1"]
print(f"  Agent 1 current_models in DB: {agent1_config.get('current_models')}")
assert agent1_config.get("current_models", {}).get("azure") == "gpt-5-chat"
print("  PASS")

print("\n" + "=" * 60)
print("STEP 8: Test list response (simulating list_available_llm_providers)")
print("=" * 60)
config = llm_router_config_store.get_effective_configuration(WORKSPACE_ID, 1)
print(f"  effective config current_models: {config.get('current_models')}")
print(f"  current_provider: {config.get('current_provider')}")

creds = llm_router_config_store.get_provider_credentials(WORKSPACE_ID, "azure")
current_model = (config.get("current_models") or {}).get("azure") or creds["model"]
print(f"  Resolved current model for azure: {current_model}")
assert current_model == "gpt-5-chat"
print("  PASS")

# Cleanup: reset agent 1 back to gpt-4.1
llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID, provider="azure", agent_id=1,
    model="gpt-4.1", user_id=247,
)

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)
print(f"\nWorkspace {WORKSPACE_ID} now has:")
print("  Azure: gpt-4.1, gpt-5-chat, gemini-2-5-flash")
print("  Quasar: claude-sonnet-4")
