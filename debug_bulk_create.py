import os
os.environ['MONGODB_DATABASE_URI'] = 'mongodb+srv://admin:UrplSapIBJizyk3X@cluster0.b6i9x4z.mongodb.net/'
from common_adapters.configurableAI.llm_router_config_store import llm_router_config_store, _get_mongo_client, LLM_CONFIG_DB_NAME, LLM_CONFIG_COLLECTION_NAME

WORKSPACE_ID = 890
client = _get_mongo_client()
col = client[LLM_CONFIG_DB_NAME][LLM_CONFIG_COLLECTION_NAME]

# Clean up agent 99 first
col.update_one({"workspace_id": WORKSPACE_ID}, {"$unset": {"agent_configs.99": ""}})

# Test get_provider_credentials
creds = llm_router_config_store.get_provider_credentials(WORKSPACE_ID, "azure")
print(f"Provider creds: model={creds.get('model') if creds else None}")

# Test bulk_create
created = llm_router_config_store.bulk_create_agent_configurations(
    workspace_id=WORKSPACE_ID,
    agent_ids=[99],
    configured_providers=["azure"],
    current_provider="azure",
    user_id=247,
)
print(f"Created count: {len(created)}")
if created:
    print(f"current_models: {created[0]['current_models']}")
else:
    print("Nothing created! Agent 99 config may still exist.")
    cfg = llm_router_config_store.get_configuration(WORKSPACE_ID, 99)
    print(f"Existing config for 99: {cfg}")

# Clean up
col.update_one({"workspace_id": WORKSPACE_ID}, {"$unset": {"agent_configs.99": ""}})
