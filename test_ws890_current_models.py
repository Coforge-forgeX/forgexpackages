"""Test: workspace 890 - verify current_models gets populated correctly."""
import os
import sys

os.environ["MONGODB_DATABASE_URI"] = "mongodb+srv://admin:UrplSapIBJizyk3X@cluster0.b6i9x4z.mongodb.net/"

from common_adapters.configurableAI.llm_router_config_store import llm_router_config_store, _get_mongo_client, LLM_CONFIG_DB_NAME, LLM_CONFIG_COLLECTION_NAME
from datetime import datetime, timezone

WORKSPACE_ID = 890

print("=" * 60)
print("STEP 1: Check current state of workspace 890")
print("=" * 60)

client = _get_mongo_client()
col = client[LLM_CONFIG_DB_NAME][LLM_CONFIG_COLLECTION_NAME]
doc = col.find_one({"workspace_id": WORKSPACE_ID})

if not doc:
    print("ERROR: Workspace 890 not found in DB")
    sys.exit(1)

print(f"  Provider credentials: {list((doc.get('provider_credentials') or {}).keys())}")
azure_creds = (doc.get("provider_credentials") or {}).get("azure", {})
print(f"  Azure model: {azure_creds.get('model')}")
print(f"  Azure available_models: {azure_creds.get('available_models')}")

print("\n  Agent configs current_models (BEFORE fix):")
for key, cfg in (doc.get("agent_configs") or {}).items():
    print(f"    agent {key}: current_models={cfg.get('current_models')}")

print("\n" + "=" * 60)
print("STEP 2: Fix existing configs - populate current_models for all agents")
print("=" * 60)

# Get the Azure default model from provider credentials
creds = llm_router_config_store.get_provider_credentials(WORKSPACE_ID, "azure")
if not creds:
    print("ERROR: No Azure credentials found")
    sys.exit(1)

default_model = creds.get("model")
print(f"  Azure default model: {default_model}")

if not default_model:
    print("ERROR: No default model in Azure credentials")
    sys.exit(1)

# Update all agent configs that have empty current_models
for key, cfg in (doc.get("agent_configs") or {}).items():
    current_models = cfg.get("current_models") or {}
    if not current_models:
        agent_id = None if key == "__workspace_default__" else int(key)
        result = llm_router_config_store.create_or_update_configuration(
            workspace_id=WORKSPACE_ID,
            agent_id=agent_id,
            current_models={"azure": default_model},
            user_id=247,
        )
        print(f"  Updated agent {key}: current_models={result['current_models']}")
    else:
        print(f"  Agent {key} already has current_models: {current_models}")

print("\n" + "=" * 60)
print("STEP 3: Verify DB state after fix")
print("=" * 60)

doc = col.find_one({"workspace_id": WORKSPACE_ID})
print("  Agent configs current_models (AFTER fix):")
all_good = True
for key, cfg in (doc.get("agent_configs") or {}).items():
    models = cfg.get("current_models") or {}
    print(f"    agent {key}: current_models={models}")
    if not models.get("azure"):
        print(f"    FAIL: agent {key} still has no azure model!")
        all_good = False

print("\n" + "=" * 60)
print("STEP 4: Verify get_effective_configuration returns models")
print("=" * 60)

for key in (doc.get("agent_configs") or {}).keys():
    if key == "__workspace_default__":
        continue
    agent_id = int(key)
    config = llm_router_config_store.get_effective_configuration(WORKSPACE_ID, agent_id)
    print(f"  Agent {agent_id}: provider={config['current_provider']}, models={config['current_models']}")
    assert config["current_models"].get("azure") == default_model, f"Agent {agent_id} missing azure model"

print("\n" + "=" * 60)
print("STEP 5: Test bulk_create now populates current_models (simulate)")
print("=" * 60)

# Delete a test agent config, then re-create it to verify bulk_create works
TEST_AGENT_ID = 99  # Use a non-existent agent ID for testing
# First clean up any existing test config
col.update_one(
    {"workspace_id": WORKSPACE_ID},
    {"$unset": {f"agent_configs.{TEST_AGENT_ID}": ""}}
)

# Now use bulk_create_agent_configurations
created = llm_router_config_store.bulk_create_agent_configurations(
    workspace_id=WORKSPACE_ID,
    agent_ids=[TEST_AGENT_ID],
    configured_providers=["azure"],
    current_provider="azure",
    user_id=247,
)

assert len(created) == 1, f"Expected 1 created config, got {len(created)}"
print(f"  Created agent {TEST_AGENT_ID}: current_models={created[0]['current_models']}")
assert created[0]["current_models"].get("azure") == default_model, \
    f"bulk_create didn't populate current_models! Got: {created[0]['current_models']}"
print("  PASS: bulk_create now correctly populates current_models")

# Clean up test agent
col.update_one(
    {"workspace_id": WORKSPACE_ID},
    {"$unset": {f"agent_configs.{TEST_AGENT_ID}": ""}}
)

if all_good:
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print(f"Workspace {WORKSPACE_ID} now has current_models populated with azure={default_model}")
    print("=" * 60)
else:
    print("\nSOME TESTS FAILED!")
    sys.exit(1)
