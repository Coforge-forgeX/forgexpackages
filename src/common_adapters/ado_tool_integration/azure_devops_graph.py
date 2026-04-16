"""
Azure DevOps LangGraph Implementation

This module provides the LangGraph-based agent workflow for Azure DevOps interactions.
"""

import logging
import traceback
from typing import Any
from langgraph.graph import START, StateGraph, MessagesState, add_messages
from langgraph.prebuilt import tools_condition, ToolNode
from langchain_core.messages import ToolMessage
import langchain_core

logger = logging.getLogger("azure_devops_graph")


class ReactGraphState(MessagesState):
    """State schema for the Azure DevOps reactive graph agent."""
    tools: list
    workspace_id: str
    user_id: str
    conversation_id: str
    azure_devops_tool_llm: langchain_core.runnables.base.RunnableBinding


async def initialize_state_history(state: ReactGraphState, session_manager, msgs: int) -> ReactGraphState:
    """
    Initialize the state with conversation history from session manager.
    
    Args:
        state: Current graph state
        session_manager: Session manager instance for loading history
        msgs: Number of messages to load from history
        
    Returns:
        Updated state with loaded messages
    """
    if session_manager is None:
        logger.warning("Session manager is None, skipping history initialization")
        return state
        
    workspace_id = state['workspace_id']
    user_id = state['user_id']
    conversation_id = state['conversation_id']
    history = session_manager.load_history(workspace_id, user_id, conversation_id, msgs)
    state['messages'] = add_messages(state['messages'], history)
    logger.info("Initialized state history with past messages.")
    return state


async def azure_devops_assistant(state: ReactGraphState) -> ReactGraphState:
    """
    Main assistant node that invokes the LLM with tools.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with LLM response
    """
    llm_with_tools = state.get('azure_devops_tool_llm', langchain_core.runnables.base.RunnableBinding)
    
    response = await llm_with_tools.ainvoke(state.get("messages", list))
    
    # only for debugging.
    # logger.info(f"azure_devops_assistant_response: {response}")
    
    state['messages'] = add_messages(state["messages"], [response])
    
    return state


async def execute_tools_with_error_handling(state: ReactGraphState) -> ReactGraphState:
    """
    Custom tool execution node that catches errors and returns them as messages
    so the agent can see the error and retry with corrected parameters.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with tool execution results or error messages
    """
    tool_node = ToolNode(state['tools'])
    
    try:
        # Execute the tools through the standard ToolNode
        result = await tool_node.ainvoke(state)
        return result
    except Exception as e:
        # Get the last AI message to find which tool was being called
        last_message = state['messages'][-1]
        
        # Create error messages for each tool call that failed
        error_messages = []
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                error_content = f"Error executing tool '{tool_call.get('name', 'unknown')}': {str(e)}\n\nPlease analyze the error and try again with corrected parameters or a different approach."
                
                # Log the full error for debugging
                logger.error(f"Tool execution error: {str(e)}\nTraceback: {traceback.format_exc()}")
                
                # Create a ToolMessage with the error that the agent can see
                error_msg = ToolMessage(
                    content=error_content,
                    tool_call_id=tool_call.get('id', 'unknown'),
                    status="error"
                )
                error_messages.append(error_msg)
        else:
            # Fallback if we can't determine the tool call
            error_content = f"Error during tool execution: {str(e)}\n\nPlease try again with a different approach."
            logger.error(f"Tool execution error (no tool_calls found): {str(e)}")
            error_messages.append(ToolMessage(content=error_content, tool_call_id="error"))
        
        # Add error messages to state so agent can see them and retry
        state['messages'] = add_messages(state['messages'], error_messages)
        return state


def create_azure_devops_graph_with_history(session_manager, msgs: int):
    """
    Create and compile the Azure DevOps reactive agent graph with history initialization.
    
    Args:
        session_manager: Session manager instance for loading conversation history
        msgs: Number of messages to load from history
        
    Returns:
        Compiled LangGraph agent with history initialization node
    """
    graph = StateGraph(ReactGraphState)

    # Create a wrapper function that injects session_manager and msgs
    async def initialize_state_history_wrapper(state: ReactGraphState) -> ReactGraphState:
        return await initialize_state_history(state, session_manager, msgs)

    # graph_nodes
    graph.add_node("assistant", azure_devops_assistant)
    graph.add_node("tools", execute_tools_with_error_handling)
    graph.add_node("initialize_state_history", initialize_state_history_wrapper)

    # graph_edges
    graph.add_edge(START, "initialize_state_history")
    graph.add_edge("initialize_state_history", "assistant")
    graph.add_conditional_edges("assistant", tools_condition,)
    graph.add_edge("tools", "assistant")

    # Compile with recursion limit to prevent infinite retries
    return graph.compile()
