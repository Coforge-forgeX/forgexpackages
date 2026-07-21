from atlassian import Jira
from typing import Any, Dict, List, Optional, Union
import logging
import json
import os

logger = logging.getLogger("jira_client")
logger.setLevel(logging.INFO)

# Create a handler for your logger only
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "%(asctime)s @ %(name)s @ %(levelname)s @ %(message)s"
))
logger.addHandler(handler)

SYSTEM_LINK_TYPES = {
    "epic-story link",
    "parent-child link",
    "parent link",
    "subtask",
    "jira portfolio parent link",
}

class JiraLLMWrapper:
    """
    A wrapper class for the Atlassian Jira client that provides enhanced documentation
    for all Jira methods. This class automatically adds descriptive docstrings to methods
    that lack proper documentation and handles Jira client initialization.
    """
    
    def __init__(self, url: str, username: str, password: str, cloud: bool = True):
        """
        Initialize the Jira client with connection parameters.
        
        Args:
            url: The Jira server URL (e.g., "https://your-domain.atlassian.net/")
            username: Jira username/email
            password: API token or password for authentication
            cloud: Whether this is a cloud instance. Default: True
        """
        logger.info(f"Initializing JiraLLMWrapper with URL: {url}, username: {username}, cloud: {cloud}")
        self.jira_fields  = os.getenv("JIRA_SELECTED_FIELDS","parent link,issue type,description,comment,assignee,epic link,sprint,flagged,priority,dod,label,parent,project,summary,dor,dependencies,acceptance criteria")
        # Create an unordered set from the comma-separated string
        # Store all field names in lowercase for efficient lookup
        self.jira_fields_set = {f.strip().lower() for f in self.jira_fields.split(",") if f.strip()}
        
        self._jira = Jira(
            url=url,
            username=username,
            password=password,
            cloud=cloud
        )
        
        
    def get_field_to_key_mapping(self) -> Dict[str, str]:
        """
        Returns a mapping of Jira field display names to Jira field keys.

        Example:
        {
            "Summary": "summary",
            "Description": "description",
            "Epic Link": "customfield_10014",
            "Parent Link": "customfield_10016",
            "Acceptance Criteria": "customfield_10231"
        }

        This method is intended for LLM workflows where the model must
        determine which Jira field key corresponds to a user-facing field name.

        Returns:
            Dict[str, str]: Mapping of field display name -> Jira field key.
        """
        logger.info("Fetching Jira field to key mapping")

        fields = self._jira.get("rest/api/3/field")
        
        fields_ = {
            field["name"].strip().lower(): field["id"]
            for field in fields
        }
        
        # logger.info("Fetched jira fields are:\n%s",fields_)
        return fields_
        
    def create_issue_link(self, data: dict):
        """
        Create an issue link between two issues. 
        
        This method creates a bidirectional link between two issues using the specified link type.
        The user must have the link issue permission for the issue being linked.
        
        Example:
            data = {
                'type': {'name': 'Duplicate'},
                'inwardIssue': {'key': 'HSP-1'},
                'outwardIssue': {'key': 'MKY-1'},
                'comment': {
                    'body': 'Linked related issue!',
                    'visibility': {'type': 'group', 'value': 'jira-software-users'}
                }
            }
        
        Common link types: 'Duplicate', 'Blocks', 'Relates', 'Clones'
        
        Args:
            data: Dictionary containing link information with required keys: type, inwardIssue, outwardIssue, and optional comment
        """

        link_name = (
            data.get("type", {})
                .get("name", "")
                .strip()
                .lower()
        )

        if link_name in SYSTEM_LINK_TYPES:
            raise ValueError(
                f"'{data['type']['name']}' is a Jira system hierarchy link "
                f"and cannot be created using create_issue_link().\n\n"
                "Resolution:\n"
                "- Use 'Parent' field for parent-child relationships.\n"
                "- Use 'Parent Link' field for Advanced Roadmaps hierarchy.\n"
                "- Use 'Epic Link' field where applicable.\n"
                "- Set these fields using create_issue() or issue_update().\n"
                "- Do NOT use create_issue_link() for hierarchy creation."
            )

        logger.info(f"Creating issue link with data: {data}")
        
        try:
            self._jira.create_issue_link(data=data)
        except Exception as e:
            return f"{e} occured when creating issues links for {data}"

        return f"Successfully created issue links for {data}"
    
    def create_parent_relationship(
        self,
        child_issue_key: str,
        parent_issue_key: str
    ):
        """
        Create a Jira Parent relationship.

        Use ONLY for Parent-child relationships.

        note: only epic issue type can be the parent_issue_key. To establish the relationship between 
        other issue types use create_issue_link() tool.

        Args:
            child_issue_key:
                Child issue key.

            parent_issue_key:
                Parent issue key.

        Returns:
            Jira update response.
        """

        logger.info(
            f"Setting Parent relationship: "
            f"{child_issue_key} -> {parent_issue_key}"
        )
        

        response = self._jira.issue_update(
                issue_key=child_issue_key,
                fields={
                    "parent": {
                        "key": parent_issue_key
                    }
                }
            )
        
        return f"Created {parent_issue_key} parent of {child_issue_key}  successfully!"

    
    # def create_hierarchy_link(
    #     self,
    #     child_issue_key: str,
    #     parent_issue_key: str
    # ):
    #     """
    #     Use for Epic/Feature/Story hierarchy.
    #     Uses Parent Link or Epic Link fields.
    #     Never use create_issue_link for hierarchy creation.

    #     Args:
    #         child_issue_key:
    #             Child issue key.

    #         parent_issue_key:
    #             Parent issue key.

    #     Returns:
    #         Jira update response.

    #     Raises:
    #         ValueError:
    #             If neither Parent Link nor Epic Link
    #             is present for the issue.
    #     """

    #     logger.info(
    #         f"Creating hierarchy relationship: "
    #         f"{child_issue_key} -> {parent_issue_key}"
    #     )

    #     edit_meta = self._jira.issue_editmeta(child_issue_key)

    #     fields = edit_meta.get("fields", {})

    #     #
    #     # Parent Link
    #     #
    #     for field_id, field_info in fields.items():

    #         field_name = (
    #             field_info.get("name", "")
    #             .strip()
    #             .lower()
    #         )

    #         if field_name == "parent link":

    #             logger.info(
    #                 f"Using Parent Link field "
    #                 f"{field_id}"
    #             )

    #             return self._jira.issue_update(
    #                 issue_key=child_issue_key,
    #                 fields={
    #                     field_id: {
    #                         "key": parent_issue_key
    #                     }
    #                 }
    #             )

    #     #
    #     # Epic Link
    #     #
    #     for field_id, field_info in fields.items():

    #         field_name = (
    #             field_info.get("name", "")
    #             .strip()
    #             .lower()
    #         )

    #         if field_name == "epic link":

    #             logger.info(
    #                 f"Using Epic Link field "
    #                 f"{field_id}"
    #             )

    #             return self._jira.issue_update(
    #                 issue_key=child_issue_key,
    #                 fields={
    #                     field_id: parent_issue_key
    #                 }
    #             )

    #     raise ValueError(
    #         f"Could not locate Parent Link or Epic Link "
    #         f"field for issue '{child_issue_key}'. "
    #         f"Use issue_editmeta() to inspect available "
    #         f"hierarchy fields."
    #     )
    
    def issue_editmeta(self, key: str):
        """
        Get the edit metadata for an issue to understand what fields can be edited.
        
        This method returns the schema and allowed values for all editable fields
        on an issue, which is essential before calling issue_update to ensure you
        provide valid field values.
        
        Args:
            key: The issue key (e.g., 'SCRUM-123') or numeric issue ID (must be int, not str)
        """
        logger.info(f"Fetching edit metadata for issue: {key}")
        meta = self._jira.issue_editmeta(key)
        if not meta or 'fields' not in meta:
            return meta
        # filtered_fields = {
        #     k: v for k, v in meta['fields'].items()
        #     if v.get('name') and v['name'].strip().lower() in self.jira_fields_set
        # }
        return {'fields': meta}
    
    def safe_json_loads(self,json_string):
        # Replace real newlines and tabs with escaped versions
        logger.debug("Parsing JSON string with safe_json_loads")
        fixed = json_string.replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')
        return json.loads(fixed)
    
    def issue_update(
        self,
        issue_key: str,
        fields: Union[str, dict],
        update: Optional[Dict[Any, Any]] = None,
        history_metadata: Optional[Dict[Any, Any]] = None,
        properties: Optional[List[Any]] = None,
        notify_users: bool = True
    ):
        """
        Update an existing Jira issue with new field values.
        
        This method modifies the fields of an existing issue. Only the fields specified in the
        fields dictionary will be updated; other fields remain unchanged.
        Example Usage:
            # Update issue fields and history metadata
            issue_key="PROJECT-123",
            fields={"summary": "Updated summary", "priority": {"id": "2"}},
            update={
                "labels": [{"add": "triaged"}, {"remove": "blocker"}],
                "timetracking": [{"edit": {"originalEstimate": "2d", "remainingEstimate": "1d"}}]
            },
            history_metadata={
                "activityDescription": "Updated via API",
                "actor": {"id": "user123", "type": "application-user"},
                "type": "custom-update"
            },
            properties=[
                {"key": "customKey1", "value": "Custom Value 1"}
            ]
            jira.issue_update(issue_key: str, fields: Union[str, dict], update: dict = None, history_metadata: dict = None, properties: list = None, notify_users: bool = True)
        
        Args:
            issue_key: The key or ID of the issue to update (e.g., 'SCRUM-123'). If using numeric ID, it must be int, not str.
            fields: Python Dictionary of fields to update. Only include fields you want to change.
            update: Python Dictionary containing advanced updates (e.g., add/remove operations for labels). Default: None
            history_metadata: Metadata for tracking the history of changes. Default: None
            properties: List of properties to add or update on the issue. Default: None
            notify_users: Whether to notify watchers about the update. Default: True
        """
        
        logger.info(f"Updating issue {issue_key} with {fields}.")
        
        if isinstance(fields,str):
            fields = self.safe_json_loads(fields)
        
        return self._jira.issue_update(
            issue_key=issue_key,
            fields=fields,
            update=update,
            history_metadata=history_metadata,
            properties=properties,
            notify_users=notify_users,
        )
    
    def create_issue(self, fields: Union[str, dict], update_history: bool = False, update: Optional[dict] = None):
        """
        Create a new issue in Jira with specified fields.
        
        This method creates a new Jira issue (Story, Task, Bug, Epic, etc.) based on the provided
        fields dictionary. The fields must conform to the Jira issue schema for the target project
        and issue type. Mandatory keys in fields are: issuetype, summary, and project.
        
        **IMPORTANT**: When specifying the project in the fields dictionary, always use the 'key' parameter 
        (e.g., {'project': {'key': 'SCRUM'}}) instead of the numeric 'id' parameter. Using project keys 
        makes the code more readable and maintainable. Similarly, for issue types, prefer using 'name' 
        (e.g., {'issuetype': {'name': 'Story'}}) over numeric IDs.
        
        Example:
            fields = {
                'project': {'key': 'SCRUM'},  # Use key, not id
                'summary': 'User login feature',
                'issuetype': {'name': 'Story'},  # Use name, not id
                'description': 'As a user, I want to log in...',
                'priority': {'name': 'High'},
                'parent': {'key':'SCRUM-12'},
                ...
            }
        
        Args:
            fields: Python Dictionary containing issue fields including project key, summary, issuetype, description, priority, and other custom fields as needed
            update_history: Whether to update the user's project history. Default: False
            update: JSON data to link issues or update worklog. Default: None
        """
        logger.info(f"Creating issue {fields} of type {type(fields)} in jira.")
        
        if isinstance(fields,str):
            fields = self.safe_json_loads(fields)
        
        return self._jira.create_issue(fields=fields, update_history=update_history, update=update)
    
    def issue_createmeta_issuetypes(self, project: str, start: Optional[int] = None, limit: Optional[int] = None):
        """
        Get all available issue types for a specific project.
        
        This method returns metadata about what types of issues (Story, Task, Bug, Epic, etc.)
        can be created in the specified project, including their IDs and properties.
        Use this information to populate the requests in create_issue and create_issues.
        
        Args:
            project: The project key (e.g., 'SCRUM')
            start: Starting index for pagination (must be int, not str). Default: None (starts at 0)
            limit: Maximum number of results to return (must be int, not str). Default: None (returns 50)
        """
        logger.info(f"Fetching issue types for project: {project}, start: {start}, limit: {limit}")
        return self._jira.issue_createmeta_issuetypes(project, start=start, limit=limit)
    
    def issue_createmeta_fieldtypes(
        self, project: str, issue_type_id: str, start: Optional[int] = None, limit: Optional[int] = None
    ):
        """
        Get the field schema for creating an issue of a specific type in a project.
        
        This is crucial before calling create_issue as it tells you what fields are available,
        what fields are required, what data types each field expects, and what allowed values exist.
        Use this information to populate the requests in create_issue and create_issues.
        
        Args:
            project: The project key (e.g., 'SCRUM')
            issue_type_id: The numeric ID of the issue type (get from issue_createmeta_issuetypes). Pass as string representation of the numeric ID.
            start: Starting index for pagination (must be int, not str). Default: None (starts at 0)
            limit: Maximum number of results to return (must be int, not str). Default: None (returns 50)
        """
        logger.info(f"Fetching field types for project: {project}, issue_type_id: {issue_type_id}, start: {start}, limit: {limit}")
        result = self._jira.issue_createmeta_fieldtypes(project, issue_type_id, start=start, limit=limit)
        if not result or 'fields' not in result or not isinstance(result['fields'], list):
            return result
        # filtered_fields = [
        #     field for field in result['fields']
        #     if field.get('name') and field['name'].strip().lower() in self.jira_fields_set
        # ]
        # Return the same structure but with filtered fields
        filtered_result = dict(result)
        # filtered_result['fields'] = filtered_fields
        return filtered_result
    
    def get_issue(
        self,
        issue_id_or_key: str,
        fields: Union[str, list, tuple, set, None] = None,
        properties: Optional[str] = None,
        update_history: bool = True,
        expand: Optional[str] = None
    ):
        """
        Retrieve detailed information about a specific Jira issue.
        
        Returns a full representation of the issue for the given issue key.
        By default, all fields are returned in this get-issue resource.
        
        Args:
            issue_id_or_key: The issue key (e.g., 'SCRUM-123') or numeric issue ID (must be int, not str)
            fields: Comma-separated string, list, tuple, or set of field names to return. If None, returns all fields. Default: None
            properties: Properties to include in the response. Default: None
            update_history: Whether to update the issue's view history. Default: True
            expand: Additional data to expand in the response (e.g., 'changelog', 'renderedFields'). Default: None
        """
        logger.info(f"Fetching issue: {issue_id_or_key}, fields: {fields}, expand: {expand}")
        return self._jira.get_issue(
            issue_id_or_key=issue_id_or_key,
            fields=fields,
            properties=properties,
            update_history=update_history,
            expand=expand
        )
    
    def projects(self, included_archived: Optional[bool] = None, expand: Optional[str] = None):
        """
        Get a list of all projects accessible to the authenticated user.
        
        Returns all projects which are visible for the currently logged-in user.
        If no user is logged in, it returns the list of projects that are visible when using anonymous access.
        
        Args:
            included_archived: Whether to include archived projects in response. Default: None (excludes archived)
            expand: Additional data to expand in the response. Default: None
        """
        logger.info(f"Fetching projects, included_archived: {included_archived}, expand: {expand}")
        return self._jira.projects(included_archived=included_archived, expand=expand)
    
    def get_all_project_issues(
        self, project_jql: str, fields: Union[str, List[str]] = "*all", nextPageToken: Optional[str] = None,limit: Optional[int] = None
    ):
        """
        Retrieve all issues from a specific project with pagination support.
        
        This method is useful for searching issues by project, getting issue lists,
        or finding issues by their summary/title. Issues are returned ordered by key.
        You have to enter your requirement specific project_jql and then for the first request you can keep the 
        nextPageToken as None , and you will get subsequent tokens in the previous request response.
        The isLast value in the response tells if you have more issues left or not.
        
        Args:
            project_jql: Jql query to fetch project from a specific project (e.g., 'SCRUM')
            fields: Fields to include in response. Use '*all' for all fields, or specify comma-separated field names or list of field names. Default: '*all'
            nextPageToken (Optional[str]): Token for paginated results. Default: None.
            limit: OPTIONAL: The limit of the number of issues to return, this may be restricted by
                fixed system limits.
        """
        logger.info(f"Fetching project issues with JQL: {project_jql}, fields: {fields}, limit: {limit}, nextPageToken: {nextPageToken}")
        return self._jira.enhanced_jql(jql=project_jql, fields=fields, nextPageToken=nextPageToken, limit=limit)
    
    def get_all_agile_boards(
        self,
        board_name: Optional[str] = None,
        project_key: Optional[str] = None,
        start: int = 0,
        limit: int = 50
    ):
        """
        Get all Agile boards accessible to the user.
        
        Returns all boards that the user has permission to view. This includes both
        Scrum and Kanban boards.
        
        Args:
            board_name: Filter by board name. Default: None (all boards)
            project_key: Filter by project key or numeric ID (must be int, not str). Default: None (all projects)
            start: Starting index for pagination (must be int, not str). Default: 0
            limit: Maximum number of boards to return (must be int, not str). Default: 50
        """
        logger.info(f"Fetching agile boards, board_name: {board_name}, project_key: {project_key}, start: {start}, limit: {limit}")
        return self._jira.get_all_agile_boards(
            board_name=board_name,
            project_key=project_key,
            start=start,
            limit=limit
        )
    
    def get_agile_board(self, board_id: int):
        """
        Get detailed information about a specific Agile board.
        
        Retrieves comprehensive information about a single Agile board including
        its name, type, location, and configuration.
        
        Args:
            board_id: The numeric ID of the board (must be int, not str)
        """
        logger.info(f"Fetching agile board with ID: {board_id}")
        return self._jira.get_agile_board(board_id)
    
    def get_all_sprints_from_board(
        self, board_id: int, state: Optional[str] = None, start: int = 0, limit: int = 50
    ):
        """
        Get all sprints associated with a specific Agile board.
        
        Returns all sprints from a board that the user has permission to view.
        Sprints can be filtered by state (future, active, closed).
        
        Args:
            board_id: The numeric ID of the board (must be int, not str)
            state: Filter results to sprints in specified states. Valid values: 'future', 'active', 'closed'. You can define multiple states separated by commas (e.g., 'active,closed'). Default: None (all states)
            start: Starting index for pagination (base index: 0) (must be int, not str). Default: 0
            limit: Maximum number of sprints to return per page (must be int, not str). Default: 50
        """
        logger.info(f"Fetching sprints from board: {board_id}, state: {state}, start: {start}, limit: {limit}")
        return self._jira.get_all_sprints_from_board(board_id, state=state, start=start, limit=limit)
    
    def get_all_issues_for_sprint_in_board(
        self,
        board_id: int,
        sprint_id: int,
        jql: str = "",
        validateQuery: bool = True,
        fields: str = "",
        expand: str = "",
        start: int = 0,
        limit: int = 50
    ):
        """
        Get all issues assigned to a specific sprint on a specific board.
        
        This is useful for sprint planning, viewing sprint contents, or generating sprint reports.
        Issues returned from this resource contain additional fields like: sprint, closedSprints, 
        flagged and epic. Issues are returned ordered by rank. JQL order has higher priority than default rank.
        
        Args:
            board_id: The numeric ID of the board (must be int, not str)
            sprint_id: The numeric ID of the sprint (must be int, not str)
            jql: Filter results using a JQL query. If you define an order in your JQL query, it will override the default order. Default: "" (no filter)
            validateQuery: Specifies whether to validate the JQL query or not. Default: True
            fields: The list of fields to return for each issue. By default, all navigable and Agile fields are returned. Default: "" (all fields)
            expand: A comma-separated list of parameters to expand. Default: "" (no expansion)
            start: Starting index for pagination (base index: 0) (must be int, not str). Default: 0
            limit: Maximum number of issues to return per page (must be int, not str). Default: 50
        """
        logger.info(f"Fetching issues for sprint {sprint_id} in board {board_id}, JQL: {jql}, start: {start}, limit: {limit}")
        return self._jira.get_all_issues_for_sprint_in_board(
            board_id=board_id,
            sprint_id=sprint_id,
            jql=jql,
            validateQuery=validateQuery,
            fields=fields,
            expand=expand,
            start=start,
            limit=limit
        )
        
    def add_issues_to_sprint(self, sprint_id: int, issues: List[str]):
        """
        Add one or multiple issues to a sprint.
        
        This method allows you to add issues to an active or open sprint. The sprint must
        not be in a closed state. Issues are provided as a list of issue keys.
        
        Args:
            sprint_id: The numeric ID of the sprint (must be int, not str). Sprint must be Active or Open only (e.g., 104)
            issues: List of issue keys to add to the sprint (e.g., ['APA-1', 'APA-2'])
        """
        logger.info(f"Adding {len(issues)} issues to sprint {sprint_id}: {issues}")
        return self._jira.add_issues_to_sprint(sprint_id=sprint_id, issues=issues)
    
    def get_project(self, project_key: str, expand: Optional[str] = None):
        """
        Get detailed information about a specific project.
        
        Args:
            project_key: The project key (e.g., 'SCRUM')
            expand: Additional data to expand.
                
        """
        logger.info(f"Fetching project details for: {project_key}, expand: {expand}")
        return self._jira.get_project(project_key, expand=expand)
    
    def get_issue_transitions_full(
        self, issue_key: str, transition_id: Optional[str] = None, expand: Optional[str] = None
    ):
        """
        Get a list of the transitions possible for this issue by the current user,
        along with fields that are required and their types.
        
        Fields will only be returned if expand = 'transitions.fields'.
        The fields in the metadata correspond to the fields in the transition screen for that transition.
        Fields not in the screen will not be in the metadata.
        
        Args:
            issue_key: The issue key (e.g., 'SCRUM-123')
            transition_id: Optional transition ID to get details for a specific transition
            expand: Optional expand parameter (e.g., 'transitions.fields' to get field information)
        """
        logger.info(f"Fetching transitions for issue: {issue_key}, transition_id: {transition_id}, expand: {expand}")
        return self._jira.get_issue_transitions_full(issue_key, transition_id=transition_id, expand=expand)
    
    def get_issue_status(self, issue_key: str):
        """
        Get the current status of an issue.
        
        Returns the status name of the specified issue.
        
        Args:
            issue_key: The issue key (e.g., 'SCRUM-123')
        """
        logger.info(f"Fetching status for issue: {issue_key}")
        return self._jira.get_issue_status(issue_key)
    
    def get_transition_id_to_status_name(self, issue_key: str, status_name: str):
        """
        Get the transition ID needed to move an issue to a specific status.
        
        This method finds the transition ID that will move the issue to the target status.
        Returns None if no matching transition is found.
        
        Args:
            issue_key: The issue key (e.g., 'SCRUM-123')
            status_name: The target status name (e.g., 'In Progress', 'Done')
        """
        logger.info(f"Finding transition ID for issue {issue_key} to status: {status_name}")
        return self._jira.get_transition_id_to_status_name(issue_key, status_name)
    
    def set_issue_status_by_transition_id(self, issue_key: str, transition_id: str):
        """
        Set the status of an issue using a transition ID.
        
        This method performs a transition on the issue using the provided transition ID.
        Use get_issue_transitions_full or get_transition_id_to_status_name to find valid transition IDs.
        
        Args:
            issue_key: The issue key (e.g., 'SCRUM-123')
            transition_id: The numeric transition ID (as a string)
        """
        logger.info(f"Setting status for issue {issue_key} using transition ID: {transition_id}")
        return self._jira.set_issue_status_by_transition_id(issue_key, transition_id)
    
    def get_issue_status_changelog(self, issue_id: str):
        """
        Get the status change history for an issue.
        
        Returns a list of all status changes that have occurred on the issue, including
        the from status, to status, and the date of each change.
        
        Args:
            issue_id: The issue key or numeric ID
        """
        logger.info(f"Fetching status changelog for issue: {issue_id}")
        return self._jira.get_issue_status_changelog(issue_id)
    
    def issue_get_watchers(self, issue_key: str):
        """
        Get the list of watchers for an issue.
        
        Returns information about all users watching the specified issue.
        
        Args:
            issue_key: The issue key (e.g., 'SCRUM-123')
        """
        logger.info(f"Fetching watchers for issue: {issue_key}")
        return self._jira.issue_get_watchers(issue_key)
    
    def get_all_assignable_users_for_project(self, project_key: str, start: int = 0, limit: int = 50):
        """
        Get all users who can be assigned to issues in a project.
        
        Returns a list of users who have permission to be assigned issues in the specified project.
        This is useful for populating assignee dropdowns or validating assignee selections.
        
        Args:
            project_key: The project key (e.g., 'SCRUM')
            start: Starting index for pagination. Default: 0
            limit: Maximum number of users to return. Default: 50
        """
        logger.info(f"Fetching assignable users for project: {project_key}, start: {start}, limit: {limit}")
        return self._jira.get_all_assignable_users_for_project(project_key, start=start, limit=limit)
    
    def assign_issue(self, issue: str, account_id: Optional[str] = None):
        """
        Assign an issue to a user.
        
        Assigns the specified issue to a user by their account ID (for Jira Cloud) or username (for Jira Server/DC).
        Pass None to unassign the issue, or -1 to set it to Automatic assignment.
        
        Args:
            issue: The issue key or numeric ID (e.g., 'SCRUM-123')
            account_id: The account ID of the user to assign (Jira Cloud) or username (Jira Server/DC). 
                       Use None to unassign or '-1' for automatic assignment.
        """
        logger.info(f"Assigning issue {issue} to account: {account_id}")
        return self._jira.assign_issue(issue, account_id=account_id)
    
    def myself(self):
        """
        Get information about the currently authenticated user.
        
        This is useful for testing connections and getting the current user's details.
        Returns the currently logged-in user resource.
        """
        logger.info("Fetching current user information")
        return self._jira.myself()
    
    
    def get_project_hierarchy(self, project_key: str) -> dict:
        """
        Get project hierarchy information.

        Args:
            project_key: Jira project key

        Returns:
            Hierarchy metadata extracted from the project's issue types.
        """

        project = self.get_project(project_key)

        issue_types = {}
        hierarchy_levels = {}

        for issue_type in project.get("issueTypes", []):

            level = issue_type.get("hierarchyLevel", 0)
            name = issue_type["name"]

            issue_types[name] = {
                "id": issue_type.get("id"),
                "level": level,
                "subtask": issue_type.get("subtask", False),
                "description": issue_type.get("description", "")
            }

            hierarchy_levels.setdefault(level, []).append(name)

        return {
            "project_key": project.get("key"),
            "project_name": project.get("name"),
            "project_type": project.get("projectTypeKey"),
            "project_style": (
                "team-managed"
                if project.get("simplified", False)
                else "company-managed"
            ),
            "hierarchy_levels": hierarchy_levels,
            "issue_types": issue_types
        }
        
    def get_project_relationship_rules(
        self,
        project_key: str
    ) -> dict:
        """
        This rule gives details on the hierarchy/issue link relationships among the jira issue types.
        Use it before you create any hierarchial or issue links relationships between any issues.

        Useful for deciding whether to use:
        - parent field
        - create_issue_link
        - reject relationship
        """

        hierarchy_data = self.get_project_hierarchy(project_key)

        issue_types = hierarchy_data["issue_types"]

        levels = {
            issue_type: metadata["level"]
            for issue_type, metadata in issue_types.items()
        }

        parent_child_relationships = {}
        issue_link_relationships = {}

        for parent_type, parent_level in levels.items():

            children = []
            peers = []

            for other_type, other_level in levels.items():

                if other_type == parent_type:
                    continue

                # Direct child level
                if other_level == parent_level - 1:
                    children.append(other_type)

                # Same level
                elif other_level == parent_level:
                    peers.append(other_type)

            if children:
                parent_child_relationships[parent_type] = {
                    "can_be_parent_of": sorted(children)
                }

            if peers:
                issue_link_relationships[parent_type] = sorted(peers)

        return {
            "project_key": project_key,
            "parent_child_relationships": parent_child_relationships,
            "issue_link_relationships": issue_link_relationships
        }
    
    def __getattr__(self, name: str):
        """
        Dynamically proxy any method calls not explicitly defined to the underlying Jira client.
        
        Args:
            name: The method name being accessed
        """
        logger.debug(f"Proxying method call to underlying Jira client: {name}")
        return getattr(self._jira, name)
