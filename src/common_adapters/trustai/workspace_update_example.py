"""
Example Usage: Workspace Agent Updates

Demonstrates how to handle workspace updates when agents are added or deleted.
"""

import asyncio
from workspace_integration import TrustAIWorkspaceIntegration
from database import TrustAIDatabaseManager


async def example_add_agents():
    """
    Example 1: Add new agents to an existing workspace
    """
    # Initialize components
    db = TrustAIDatabaseManager(database_url="postgresql://user:pass@host/db")
    workspace_integration = TrustAIWorkspaceIntegration(db)

    workspace_id = "123"
    new_agent_ids = [101, 102, 103]
    user_id = 1

    # Add new agents to workspace
    result = await workspace_integration.add_agents_to_workspace(
        workspace_id=workspace_id,
        agent_ids=new_agent_ids,
        created_by=user_id
    )

    print(f"Added agents: {result['added_agents']}")
    print(f"Failed agents: {result['failed_agents']}")
    print(f"Default model: {result['default_model']}")


async def example_remove_agents():
    """
    Example 2: Remove agents from a workspace
    """
    db = TrustAIDatabaseManager(database_url="postgresql://user:pass@host/db")
    workspace_integration = TrustAIWorkspaceIntegration(db)

    workspace_id = "123"
    agents_to_remove = [101, 102]

    # Remove agents from workspace
    result = workspace_integration.remove_agents_from_workspace(
        workspace_id=workspace_id,
        agent_ids=agents_to_remove
    )

    print(f"Removed agents: {result['removed_agents']}")
    print(f"Failed agents: {result['failed_agents']}")


async def example_sync_agents():
    """
    Example 3: Sync workspace with current agent list

    This automatically detects and handles:
    - New agents (adds them)
    - Deleted agents (removes them)
    - Unchanged agents (no action)
    """
    db = TrustAIDatabaseManager(database_url="postgresql://user:pass@host/db")
    workspace_integration = TrustAIWorkspaceIntegration(db)

    workspace_id = "123"
    # Current list of agents that should exist in workspace
    current_agents = [1, 2, 3, 4, 5]
    user_id = 1

    # Sync workspace agents
    result = await workspace_integration.update_workspace_agents(
        workspace_id=workspace_id,
        current_agent_ids=current_agents,
        created_by=user_id
    )

    print(f"Agents added: {result['agents_added']}")
    print(f"Agents removed: {result['agents_removed']}")
    print(f"Agents unchanged: {result['agents_unchanged']}")
    print(f"Failed operations: {result['failed_operations']}")


async def example_get_workspace_agents():
    """
    Example 4: Get all agents currently configured in a workspace
    """
    db = TrustAIDatabaseManager(database_url="postgresql://user:pass@host/db")

    workspace_id = "123"

    # Get current agent IDs
    agent_ids = db.get_workspace_agent_ids(workspace_id)

    print(f"Workspace {workspace_id} has {len(agent_ids)} agents: {agent_ids}")


async def example_webhook_handler():
    """
    Example 5: Webhook handler for agent changes

    Use this pattern when you receive webhooks about agent changes
    """
    db = TrustAIDatabaseManager(database_url="postgresql://user:pass@host/db")
    workspace_integration = TrustAIWorkspaceIntegration(db)

    # Simulated webhook payload
    webhook_data = {
        'workspace_id': '123',
        'event_type': 'agents_updated',
        'current_agents': [1, 2, 3, 4, 5, 6],  # New list from external system
        'user_id': 1
    }

    if webhook_data['event_type'] == 'agents_updated':
        # Sync workspace with new agent list
        result = await workspace_integration.update_workspace_agents(
            workspace_id=webhook_data['workspace_id'],
            current_agent_ids=webhook_data['current_agents'],
            created_by=webhook_data['user_id']
        )

        return {
            'status': 'success',
            'summary': {
                'added': len(result['agents_added']),
                'removed': len(result['agents_removed']),
                'unchanged': len(result['agents_unchanged']),
                'failed': len(result['failed_operations'])
            },
            'details': result
        }


async def example_batch_update():
    """
    Example 6: Handle multiple workspace updates

    Use when syncing multiple workspaces at once
    """
    db = TrustAIDatabaseManager(database_url="postgresql://user:pass@host/db")
    workspace_integration = TrustAIWorkspaceIntegration(db)

    # Workspace updates from external system
    workspace_updates = [
        {'workspace_id': '123', 'agent_ids': [1, 2, 3]},
        {'workspace_id': '456', 'agent_ids': [4, 5, 6]},
        {'workspace_id': '789', 'agent_ids': [7, 8, 9]}
    ]

    results = []

    for update in workspace_updates:
        try:
            result = await workspace_integration.update_workspace_agents(
                workspace_id=update['workspace_id'],
                current_agent_ids=update['agent_ids'],
                created_by=1
            )
            results.append({
                'workspace_id': update['workspace_id'],
                'status': 'success',
                'result': result
            })
        except Exception as e:
            results.append({
                'workspace_id': update['workspace_id'],
                'status': 'error',
                'error': str(e)
            })

    return results


# API endpoint examples
async def api_add_agents_endpoint(workspace_id: str, agent_ids: list, user_id: int):
    """
    FastAPI endpoint example for adding agents

    @router.post("/workspaces/{workspace_id}/agents/add")
    async def add_agents(workspace_id: str, request: AddAgentsRequest, user_id: int):
        return await api_add_agents_endpoint(workspace_id, request.agent_ids, user_id)
    """
    db = TrustAIDatabaseManager(database_url="postgresql://user:pass@host/db")
    workspace_integration = TrustAIWorkspaceIntegration(db)

    result = await workspace_integration.add_agents_to_workspace(
        workspace_id=workspace_id,
        agent_ids=agent_ids,
        created_by=user_id
    )

    return {
        'success': len(result['failed_agents']) == 0,
        'data': result
    }


async def api_remove_agents_endpoint(workspace_id: str, agent_ids: list):
    """
    FastAPI endpoint example for removing agents

    @router.post("/workspaces/{workspace_id}/agents/remove")
    async def remove_agents(workspace_id: str, request: RemoveAgentsRequest):
        return await api_remove_agents_endpoint(workspace_id, request.agent_ids)
    """
    db = TrustAIDatabaseManager(database_url="postgresql://user:pass@host/db")
    workspace_integration = TrustAIWorkspaceIntegration(db)

    result = workspace_integration.remove_agents_from_workspace(
        workspace_id=workspace_id,
        agent_ids=agent_ids
    )

    return {
        'success': len(result['failed_agents']) == 0,
        'data': result
    }


async def api_sync_agents_endpoint(workspace_id: str, agent_ids: list, user_id: int):
    """
    FastAPI endpoint example for syncing agents

    @router.post("/workspaces/{workspace_id}/agents/sync")
    async def sync_agents(workspace_id: str, request: SyncAgentsRequest, user_id: int):
        return await api_sync_agents_endpoint(workspace_id, request.agent_ids, user_id)
    """
    db = TrustAIDatabaseManager(database_url="postgresql://user:pass@host/db")
    workspace_integration = TrustAIWorkspaceIntegration(db)

    result = await workspace_integration.update_workspace_agents(
        workspace_id=workspace_id,
        current_agent_ids=agent_ids,
        created_by=user_id
    )

    return {
        'success': len(result['failed_operations']) == 0,
        'data': result
    }


if __name__ == '__main__':
    # Run examples
    print("Example 1: Add agents")
    asyncio.run(example_add_agents())

    print("\nExample 2: Remove agents")
    asyncio.run(example_remove_agents())

    print("\nExample 3: Sync agents")
    asyncio.run(example_sync_agents())

    print("\nExample 4: Get workspace agents")
    asyncio.run(example_get_workspace_agents())
