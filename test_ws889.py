"""Test: workspace 889 on stage cluster - add models to quasar and test switching."""
import os
import sys

os.environ["MONGODB_DATABASE_URI"] = "mongodb+srv://forgex:lhUFgK2apWjFdh7C@forgexcluster1.8i29hdx.mongodb.net/?retryWrites=true&w=majority&appName=forgeXCluster1"

from common_adapters.configurableAI.llm_router_config_store import llm_router_config_store, _get_mongo_client, LLM_CONFIG_DB_NAME, LLM_CONFIG_COLLECTION_NAME
from datetime import datetime, timezone

WORKSPACE_ID = 889

print("=" * 60)
print("STEP 1: Verify workspace 889 exists and check current state")
print("=" * 60)

creds_azure = llm_router_config_store.get_provider_credentials(WORKSPACE_ID, "azure")
creds_quasar = llm_router_config_store.get_provider_credentials(WORKSPACE_ID, "quasar")

if not creds_azure:
    print("ERROR: No azure credentials for workspace 889")
    sys.exit(1)
if not creds_quasar:
    print("ERROR: No quasar credentials for workspace 889")
    sys.exit(1)

print(f"  Azure model: {creds_azure['model']}, available: {creds_azure.get('available_models')}")
print(f"  Quasar model: {creds_quasar['model']}, available: {creds_quasar.get('available_models')}")

print("\n" + "=" * 60)
print("STEP 2: Add gpt-5-chat and gemini-2-5-flash to Quasar provider")
print("=" * 60)

client = _get_mongo_client()
col = client[LLM_CONFIG_DB_NAME][LLM_CONFIG_COLLECTION_NAME]
now = datetime.now(timezone.utc)

# Build quasar available_models list
quasar_models = creds_quasar.get("available_models") or []
for entry in [
    {"model_name": "claude-sonnet-4", "deployment_name": "claude-sonnet-4"},
    {"model_name": "gpt-5-chat", "deployment_name": "gpt-5-chat"},
    {"model_name": "gemini-2-5-flash", "deployment_name": "gemini-2-5-flash"},
]:
    if not any(m["model_name"] == entry["model_name"] for m in quasar_models):
        quasar_models.append(entry)

# Also ensure azure has gpt-4.1 in available_models
azure_models = creds_azure.get("available_models") or []
if not any(m["model_name"] == "gpt-4.1" for m in azure_models):
    azure_models.append({"model_name": "gpt-4.1", "deployment_name": "gpt-4.1"})

col.update_one(
    {"workspace_id": WORKSPACE_ID},
    {"$set": {
        "provider_credentials.quasar.available_models": quasar_models,
        "provider_credentials.quasar.updated_at": now,
        "provider_credentials.azure.available_models": azure_models,
        "provider_credentials.azure.updated_at": now,
    }}
)

creds_quasar = llm_router_config_store.get_provider_credentials(WORKSPACE_ID, "quasar")
creds_azure = llm_router_config_store.get_provider_credentials(WORKSPACE_ID, "azure")
print(f"  Quasar available_models: {creds_quasar['available_models']}")
print(f"  Azure available_models: {creds_azure['available_models']}")
assert len(creds_quasar["available_models"]) == 3
print("  PASS")

print("\n" + "=" * 60)
print("STEP 3: Switch agent 1 to quasar + gpt-5-chat")
print("=" * 60)

result = llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID,
    provider="quasar",
    agent_id=1,
    model="gpt-5-chat",
    user_id=247,
)
print(f"  current_provider: {result['current_provider']}")
print(f"  current_models: {result['current_models']}")
assert result["current_provider"] == "quasar"
assert result["current_models"]["quasar"] == "gpt-5-chat"
print("  PASS")

print("\n" + "=" * 60)
print("STEP 4: Switch agent 1 to quasar + gemini-2-5-flash")
print("=" * 60)

result = llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID,
    provider="quasar",
    agent_id=1,
    model="gemini-2-5-flash",
    user_id=247,
)
print(f"  current_models: {result['current_models']}")
assert result["current_models"]["quasar"] == "gemini-2-5-flash"
print("  PASS")

print("\n" + "=" * 60)
print("STEP 5: Switch agent 1 to quasar + claude-sonnet-4 (back to default)")
print("=" * 60)

result = llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID,
    provider="quasar",
    agent_id=1,
    model="claude-sonnet-4",
    user_id=247,
)
print(f"  current_models: {result['current_models']}")
assert result["current_models"]["quasar"] == "claude-sonnet-4"
print("  PASS")

print("\n" + "=" * 60)
print("STEP 6: Switch to azure without model (quasar model should persist)")
print("=" * 60)

result = llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID,
    provider="azure",
    agent_id=1,
    user_id=247,
)
print(f"  current_provider: {result['current_provider']}")
print(f"  current_models: {result['current_models']}")
assert result["current_provider"] == "azure"
assert result["current_models"].get("quasar") == "claude-sonnet-4", "quasar model should persist"
print("  PASS")

print("\n" + "=" * 60)
print("STEP 7: Switch back to quasar without model (should use last: claude-sonnet-4)")
print("=" * 60)

result = llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID,
    provider="quasar",
    agent_id=1,
    user_id=247,
)
print(f"  current_provider: {result['current_provider']}")
print(f"  current_models: {result['current_models']}")
assert result["current_provider"] == "quasar"
assert result["current_models"].get("quasar") == "claude-sonnet-4"
print("  PASS")

print("\n" + "=" * 60)
print("STEP 8: Invalid model should fail")
print("=" * 60)

try:
    llm_router_config_store.switch_provider(
        workspace_id=WORKSPACE_ID, provider="quasar", agent_id=1,
        model="totally-fake-model", user_id=247,
    )
    print("  FAIL: Should have raised ValueError")
    sys.exit(1)
except ValueError as e:
    print(f"  Correctly rejected: {e}")
    print("  PASS")

print("\n" + "=" * 60)
print("STEP 9: build_config_dict uses model override for quasar")
print("=" * 60)

config = llm_router_config_store.build_config_dict(WORKSPACE_ID, "quasar", model_override="gpt-5-chat")
print(f"  With override: model={config['model']}")
assert config["model"] == "gpt-5-chat"

config = llm_router_config_store.build_config_dict(WORKSPACE_ID, "quasar")
print(f"  Without override: model={config['model']} (provider default)")
assert config["model"] == "claude-sonnet-4"
print("  PASS")

print("\n" + "=" * 60)
print("STEP 10: Verify DB document shows current_models")
print("=" * 60)

doc = col.find_one({"workspace_id": WORKSPACE_ID})
agent1 = doc["agent_configs"]["1"]
print(f"  DB agent_configs.1.current_models: {agent1.get('current_models')}")
assert agent1.get("current_models", {}).get("quasar") == "claude-sonnet-4"
print("  PASS")

print("\n" + "=" * 60)
print("STEP 11: Test get_effective_configuration returns current_models")
print("=" * 60)

config = llm_router_config_store.get_effective_configuration(WORKSPACE_ID, 1)
print(f"  effective config: provider={config['current_provider']}, models={config['current_models']}")
assert config["current_models"].get("quasar") == "claude-sonnet-4"
print("  PASS")

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)
print(f"\nWorkspace {WORKSPACE_ID} final state:")
print("  Azure: gpt-4.1")
print("  Quasar: claude-sonnet-4, gpt-5-chat, gemini-2-5-flash")
print("  Agent 1: provider=quasar, model=claude-sonnet-4")
