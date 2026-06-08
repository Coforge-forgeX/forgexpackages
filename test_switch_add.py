"""Test: switch_provider and add_provider populate current_models automatically."""
import os
os.environ['MONGODB_DATABASE_URI'] = 'mongodb+srv://admin:UrplSapIBJizyk3X@cluster0.b6i9x4z.mongodb.net/'
from common_adapters.configurableAI.llm_router_config_store import llm_router_config_store, _get_mongo_client, LLM_CONFIG_DB_NAME, LLM_CONFIG_COLLECTION_NAME

WORKSPACE_ID = 890

print("=" * 60)
print("TEST: switch_provider auto-populates current_models")
print("=" * 60)

# Switch agent 1 to quasar without explicit model
result = llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID,
    provider="quasar",
    agent_id=1,
    user_id=247,
)
print(f"  Agent 1 after switch to quasar:")
print(f"    current_provider: {result['current_provider']}")
print(f"    current_models: {result['current_models']}")
assert result["current_provider"] == "quasar"
assert result["current_models"].get("quasar") == "claude-sonnet-4", \
    f"Expected quasar=claude-sonnet-4, got: {result['current_models']}"
assert result["current_models"].get("azure") == "gpt-4.1", \
    f"Expected azure=gpt-4.1 to persist, got: {result['current_models']}"
print("  PASS: quasar model auto-populated from provider credentials")

print("\n" + "=" * 60)
print("TEST: add_provider auto-populates current_models")
print("=" * 60)

# Add quasar to agent 3 (which currently only has azure)
result = llm_router_config_store.add_provider(
    workspace_id=WORKSPACE_ID,
    provider="quasar",
    agent_id=3,
    set_as_current=True,
    user_id=247,
)
print(f"  Agent 3 after add_provider quasar:")
print(f"    current_provider: {result['current_provider']}")
print(f"    current_models: {result['current_models']}")
assert result["current_models"].get("quasar") == "claude-sonnet-4", \
    f"Expected quasar=claude-sonnet-4, got: {result['current_models']}"
assert result["current_models"].get("azure") == "gpt-4.1", \
    f"Expected azure=gpt-4.1 to persist, got: {result['current_models']}"
print("  PASS: quasar model auto-populated when adding provider")

# Revert agent 3 back to azure only
llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID,
    provider="azure",
    agent_id=3,
    user_id=247,
)

print("\n" + "=" * 60)
print("TEST: switch_provider keeps existing model when already set")
print("=" * 60)

# Agent 1 already has quasar=claude-sonnet-4, switch to azure and back
llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID, provider="azure", agent_id=1, user_id=247
)
result = llm_router_config_store.switch_provider(
    workspace_id=WORKSPACE_ID, provider="quasar", agent_id=1, user_id=247
)
print(f"  Agent 1 after switch azure->quasar:")
print(f"    current_models: {result['current_models']}")
assert result["current_models"].get("quasar") == "claude-sonnet-4", \
    f"Should retain prior quasar selection, got: {result['current_models']}"
print("  PASS: prior model selection retained")

print("\n" + "=" * 60)
print("ALL SWITCH/ADD TESTS PASSED!")
print("=" * 60)
