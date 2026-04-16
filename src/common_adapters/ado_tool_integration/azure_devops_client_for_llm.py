from azure.devops.connection import Connection
from azure.devops.v7_1.work.models import TeamContext  
from msrest.authentication import BasicAuthentication
from typing import Any, Dict, List, Optional, Union
import logging
import json

logger = logging.getLogger("azure_devops_client")
logger.setLevel(logging.INFO)

# Create a handler for your logger only
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "%(asctime)s @ %(name)s @ %(levelname)s @ %(message)s"
))
logger.addHandler(handler)

class AzureDevOpsLLMWrapper:
        
    """
    A wrapper class for Azure DevOps REST API that provides enhanced documentation
    for all Azure DevOps operations. This class handles work items, boards, sprints.
    """
    
    def __init__(self, base_url: str, access_token: str, organization: str, project: str):
        """
        Initialize the Azure DevOps client with connection parameters.
        
        Args:
            base_url: The Azure DevOps organization URL (e.g., "https://dev.azure.com/your-org")
            access_token: Personal Access Token for authentication
            organization: Azure DevOps organization name
            project: Project name or ID
        """
        if not all([base_url, access_token, organization, project]):
            raise ValueError("base_url, access_token, organization, and project are all required.")

        logger.info(f"Initializing AzureDevOpsLLMWrapper with URL: {base_url}, organization: {organization}, project: {project}")
        
        self.base_url = base_url
        self.organization = organization
        self.project = project
        
        try:
            credentials = BasicAuthentication('', access_token)
            self.connection = Connection(base_url=base_url, creds=credentials)
            
            # Initialize clients
            self.work_item_client = self.connection.clients.get_work_item_tracking_client()
            self.work_client = self.connection.clients.get_work_client()  # Needed for boards/sprints
            self.core_client = self.connection.clients.get_core_client()
            # self.git_client = self.connection.clients.get_git_client()  # Uncomment if git is needed
        except Exception as e:
            logger.error(f"Failed to initialize Azure DevOps connection: {e}")
            raise
    
    def _make_team_context(self, team_id: str) -> TeamContext:
        
        return TeamContext(project=self.project, team=team_id)

    def safe_json_loads(self, json_string: str) -> dict:
        """Parse JSON string safely by handling newlines and tabs."""
        logger.debug("Parsing JSON string with safe_json_loads")
        fixed = json_string.replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')
        return json.loads(fixed)
    
    def get_board_users(self) -> List[Dict]:
        """
        Retrieve all users who are members of any team board within the current Azure DevOps project.

        This method aggregates all unique users across all teams in the specified project. Each user is represented
        with their identity details and the team they belong to. Users who are members of multiple teams will only
        appear once in the result, associated with the last team processed.

        Returns:
            List[Dict]: A list of dictionaries, each containing user identity information and team name.
                Example:
                    [
                        {
                            "id": "user-guid",
                            "displayName": "Jane Doe",
                            "uniqueName": "jane.doe@domain.com",
                            "descriptor": "vssgp.Uy0xLTktMTIzNDU2Nzg5",
                            "team": "Team Alpha"
                        },
                        ...
                    ]
        """
        logger.info(f"Fetching Board users for project: {self.project}")

        users = {}
        try:
            # 1️⃣ Get all teams in the project
            teams = self.core_client.get_teams(project_id=self.project)

            for team in teams:
                logger.info(f"Fetching members for team: {team.name}")

                # 2️⃣ Get team members
                members = self.core_client.get_team_members_with_extended_properties(
                    project_id=self.project,
                    team_id=team.id
                )
                
                for member in members:
                    identity = member.identity

                    # Avoid duplicates (users can be in multiple teams)
                    users[identity.id] = {
                        "id": identity.id,
                        "displayName": identity.display_name,
                        "uniqueName": identity.unique_name,
                        "descriptor": identity.descriptor,
                        "team": team.name
                    }

            logger.info(f"Total Board users found: {len(users)}")
            return list(users.values())

        except Exception as e:
            logger.error(f"Failed to fetch board users: {e}")
            return []

    def get_board_user(self, team_id: str) -> List[Dict]:
        """
        Retrieve all users who are members of a specific team board within the current Azure DevOps project.

        Args:
            team_id (str): The ID or name of the team whose members are to be retrieved.

        Returns:
            List[Dict]: A list of dictionaries, each containing user identity information and the team ID.
                Example:
                    [
                        {
                            "id": "user-guid",
                            "displayName": "Jane Doe",
                            "uniqueName": "jane.doe@domain.com",
                            "descriptor": "vssgp.Uy0xLTktMTIzNDU2Nzg5",
                            "team": "team-id"
                        },
                        ...
                    ]
        """
        logger.info(f"Fetching Board users for project: {self.project}")

        users = {}
        try:
            # 2️⃣ Get team members
            members = self.core_client.get_team_members_with_extended_properties(
                project_id=self.project,
                team_id = team_id
            )
            
            for member in members:
                identity = member.identity

                # Avoid duplicates (users can be in multiple teams)
                users[identity.id] = {
                    "id": identity.id,
                    "displayName": identity.display_name,
                    "uniqueName": identity.unique_name,
                    "descriptor": identity.descriptor,
                    "team": team_id
                }

            logger.info(f"Total Board users found: {len(users)}")
            return list(users.values())

        except Exception as e:
            logger.error(f"Failed to fetch board users: {e}")
            return []
    def create_work_item(self, work_item_type: str, fields: Union[str, dict], relations: Optional[List[dict]] = None):
        """
        Create a new work item in Azure DevOps.
        
        This method creates a new work item (User Story, Task, Bug, Epic, etc.) based on the provided
        fields dictionary. The work item type and title are mandatory.
        
        Example:
            fields = {
                'System.Title': 'User login feature',
                'System.Description': 'As a user, I want to log in...',
                'System.AssignedTo': 'user@domain.com',
                'Microsoft.VSTS.Common.Priority': 2,
                'Microsoft.VSTS.Common.Severity': '2 - High'
            }
        
        Args:
            work_item_type: Type of work item (e.g., 'User Story', 'Task', 'Bug', 'Epic')
            fields: Dictionary containing work item fields or JSON string
            relations: Optional list of relations to other work items
        """
        logger.info(f"Creating work item of type {work_item_type} with fields: {fields}")
        
        if isinstance(fields, str):
            fields = self.safe_json_loads(fields)
        
        if 'System.Title' not in fields:
            raise ValueError("'System.Title' is required to create a work item.")

        document = []
        
        for field_name, field_value in fields.items():
            document.append({
                "op": "add",
                "path": f"/fields/{field_name}",
                "value": field_value
            })
        
        if relations:
            for relation in relations:
                document.append({
                    "op": "add",
                    "path": "/relations/-",
                    "value": relation
                })
        
        try:
            result = self.work_item_client.create_work_item(
                document=document,
                project=self.project,
                type=work_item_type
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to create work item: {e}")
            raise
    
    def update_work_item(self, work_item_id: int, fields: Union[str, dict], relations: Optional[List[dict]] = None):
        """
        Update an existing work item with new field values.
        
        This method modifies the fields of an existing work item. Only the fields specified
        in the fields dictionary will be updated; other fields remain unchanged.
        
        Args:
            work_item_id: The ID of the work item to update
            fields: Dictionary of fields to update or JSON string
            relations: Optional list of relations to add/update
        """
        logger.info(f"Updating work item {work_item_id} with fields: {fields}")
        
        if isinstance(fields, str):
            fields = self.safe_json_loads(fields)
        
        document = []
        
        for field_name, field_value in fields.items():
            document.append({
                "op": "replace",
                "path": f"/fields/{field_name}",
                "value": field_value
            })
        
        if relations:
            for relation in relations:
                document.append({
                    "op": "add",
                    "path": "/relations/-",
                    "value": relation
                })
        
        try:
            result = self.work_item_client.update_work_item(
                document=document,
                id=work_item_id,
                project=self.project
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to update work item {work_item_id}: {e}")
            raise
    
    def get_work_item(self, work_item_id: int, fields: Optional[List[str]] = None, expand: Optional[str] = None):
        """
        Retrieve detailed information about a specific work item.
        
        Returns a full representation of the work item for the given ID.
        By default, all fields are returned.
        
        Args:
            work_item_id: The ID of the work item to retrieve
            fields: List of field names to return. If None, returns all fields
            expand: Additional data to expand (e.g., 'relations', 'links')
        """
        logger.info(f"Fetching work item: {work_item_id}, fields: {fields}, expand: {expand}")
        
        try:
            result = self.work_item_client.get_work_item(
                id=work_item_id,
                project=self.project,
                fields=fields,
                expand=expand
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to fetch work item {work_item_id}: {e}")
            raise
    
    def get_work_items_by_query(self, wiql_query: str, top: Optional[int] = None) -> List:
        """
        Query work items using WIQL (Work Item Query Language).
        
        **Use this method for:**
        - Filtering by state, priority, work item type, or any field
        - Complex queries with multiple conditions
        - Queries that search_work_items() cannot handle
        
        
        Example WIQL Queries:
        
        2. Find by work item type:
           ```
           SELECT [System.Id], [System.Title] 
           FROM WorkItems 
           WHERE [System.WorkItemType] = 'User Story'
           ```
        
        3. Find by state and priority:
           ```
           SELECT [System.Id], [System.Title] 
           FROM WorkItems 
           WHERE [System.State] = 'Active' 
           AND [Microsoft.VSTS.Common.Priority] = 1
           ```
        
        Args:
            wiql_query: WIQL query string
            top: Maximum number of work items to return. 
                 If None, returns up to 20000 (Azure DevOps maximum).
                 Default Azure DevOps limit when not specified is typically 200.
        
        Note:
            - Azure DevOps default limit (when top=None): ~200 work items
            - Azure DevOps maximum allowed: 20000 work items per query
            - This method fetches work items in batches of 200 for efficiency
            - Returns list of work items matching the query with all requested fields
        """
        # Set explicit default to get all results (up to Azure DevOps max)
        query_top = top if top is not None else 20000
        
        logger.info(f"Executing WIQL query with top={query_top}: {wiql_query}")
        
        try:
            wiql = {"query": wiql_query}
            team_context = TeamContext(project_id=None, project=self.project, team=None)
            query_result = self.work_item_client.query_by_wiql(
                wiql=wiql,
                team_context=team_context,
                top=query_top
            )
            
            if not query_result.work_items:
                logger.info("No work items found matching the query")
                return []
            
            work_item_ids = [item.id for item in query_result.work_items]
            logger.info(f"Query returned {len(work_item_ids)} work item IDs")
            
            # Azure DevOps get_work_items has a limit of 200 items per request
            # Split into batches for reliability
            batch_size = 200
            all_work_items = []
            
            for i in range(0, len(work_item_ids), batch_size):
                batch_ids = work_item_ids[i:i + batch_size]
                
                work_items = self.work_item_client.get_work_items(
                    ids=batch_ids,
                    project=self.project
                )
                all_work_items.extend([wi.as_dict() if hasattr(wi, 'as_dict') else wi for wi in work_items])
            
            return all_work_items

        except Exception as e:
            logger.error(f"Failed to execute WIQL query: {e}")
            return []
    
    def get_work_item_types(self):
        """
        Get all available work item types for the project.
        
        Returns metadata about what types of work items (User Story, Task, Bug, Epic, etc.)
        can be created in the project.
        """
        logger.info("Fetching work item types for project")
        
        result = self.work_item_client.get_work_item_types(project=self.project)
        return [wit.as_dict() if hasattr(wit, 'as_dict') else wit for wit in result]
    
    def get_work_item_fields(self):
        """
        Get all available fields for work items in the project.
        
        Returns information about all fields that can be used in work items,
        including their types, allowed values, and whether they're required.
        """
        logger.info("Fetching work item fields")
        
        result = self.work_item_client.get_fields(project=self.project)
        return [field.as_dict() if hasattr(field, 'as_dict') else field for field in result]
    
    def create_work_item_link(self, source_id: int, target_id: int, link_type: str, comment: Optional[str] = None):
        """
        Create a link between two work items.
        
        Common link types: 'System.LinkTypes.Related', 'System.LinkTypes.Dependency-Forward', 
        'System.LinkTypes.Hierarchy-Forward', 'Microsoft.VSTS.Common.TestedBy-Forward'
        
        Args:
            source_id: ID of the source work item
            target_id: ID of the target work item
            link_type: Type of link to create
            comment: Optional comment for the link
        """
        logger.info(f"Creating work item link from {source_id} to {target_id} with type: {link_type}")
        
        document = [{
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": link_type,
                "url": f"{self.base_url}/_apis/wit/workItems/{target_id}",
                "attributes": {
                    "comment": comment or ""
                }
            }
        }]
        
        try:
            result = self.work_item_client.update_work_item(
                document=document,
                id=source_id,
                project=self.project
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to create link between {source_id} and {target_id}: {e}")
            raise
    
    def get_teams(self):
        """
        Get all teams in the project.
        
        Returns a list of all teams that exist in the current project.
        """
        logger.info("Fetching teams for project")
        response = self.core_client.get_teams(project_id=self.project)
        logger.info(f"Fetched teams: {len(response)} team(s)")
        return [team.as_dict() if hasattr(team, 'as_dict') else team for team in response]

    
    def get_team_boards(self, team_id: str) -> List:
        """
        Get all boards for a specific team.
        
        Returns all boards (Kanban, Scrum, etc.) associated with the specified team.
        
        Args:
            team_id: The ID or name of the team
        """
        logger.info(f"Fetching boards for team: {team_id}")
        
        try:
            boards = self.work_client.get_boards(
                team_context=self._make_team_context(team_id)
            )
            return [board.as_dict() if hasattr(board, 'as_dict') else board for board in boards] if boards else []
        except Exception as e:
            logger.error(f"Failed to fetch boards for team {team_id}: {e}")
            raise
    
    def get_board(self, team_id: str, board_id: str):
        """
        Get detailed information about a specific board.
        
        Args:
            team_id: The ID or name of the team
            board_id: The ID of the board
        """
        logger.info(f"Fetching board {board_id} for team: {team_id}")
        
        try:
            result = self.work_client.get_board(
                team_context=self._make_team_context(team_id),
                id=board_id
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to fetch board {board_id}: {e}")
            raise
    
    def get_board_columns(self, team_id: str, board_id: str):
        """
        Get all columns for a specific board.
        
        Args:
            team_id: The ID or name of the team
            board_id: The ID of the board
        """
        logger.info(f"Fetching columns for board {board_id} in team: {team_id}")
        
        try:
            result = self.work_client.get_board_columns(
                team_context=self._make_team_context(team_id),
                board=board_id
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to fetch columns for board {board_id}: {e}")
            raise
    
    def get_board_rows(self, team_id: str, board_id: str):
        """
        Get all rows (swimlanes) for a specific board.
        
        Args:
            team_id: The ID or name of the team
            board_id: The ID of the board
        """
        logger.info(f"Fetching rows for board {board_id} in team: {team_id}")
        
        try:
            result = self.work_client.get_board_rows(
                team_context=self._make_team_context(team_id),
                board=board_id
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to fetch rows for board {board_id}: {e}")
            raise
    
    def get_team_iterations(self, team_id: str, timeframe: Optional[str] = None):
        """
        Get all iterations (sprints) for a team.
        
        Args:
            team_id: The ID or name of the team
            timeframe: Filter by timeframe ('current', 'past', 'future'). Default: None (all)
        """
        logger.info(f"Fetching iterations for team: {team_id}, timeframe: {timeframe}")
        
        try:
            result = self.work_client.get_team_iterations(
                team_context=self._make_team_context(team_id),
                timeframe=timeframe
            )
            return [iteration.as_dict() if hasattr(iteration, 'as_dict') else iteration for iteration in result]
        except Exception as e:
            logger.error(f"Failed to fetch iterations for team {team_id}: {e}")
            raise
    
    def get_iteration(self, team_id: str, iteration_id: str):
        """
        Get detailed information about a specific iteration.
        
        Args:
            team_id: The ID or name of the team
            iteration_id: The ID of the iteration
        """
        logger.info(f"Fetching iteration {iteration_id} for team: {team_id}")
        
        try:
            result = self.work_client.get_team_iteration(
                team_context=self._make_team_context(team_id),
                id=iteration_id
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to fetch iteration {iteration_id}: {e}")
            raise
    
    def get_iteration_work_items(self, team_id: str, iteration_id: str):
        """
        Get all work items in a specific iteration with complete details.
        
        Args:
            team_id: The ID or name of the team
            iteration_id: The ID of the iteration
        
        Note:
            Returns dictionary with 'work_items' (list of complete work item dictionaries),
            'total_count' (total number of work items), and 'work_item_relations' 
            (original hierarchical structure showing parent-child relationships).
        """
        logger.info(f"Fetching work items for iteration {iteration_id} in team: {team_id}")
        
        try:
            result = self.work_client.get_iteration_work_items(
                team_context=self._make_team_context(team_id),
                iteration_id=iteration_id
            )
            result_dict = result.as_dict() if hasattr(result, 'as_dict') else result
            
            # Extract all unique work item IDs from both source and target
            work_item_ids = set()
            work_item_relations = result_dict.get('work_item_relations', []) if isinstance(result_dict, dict) else []
            
            for relation in work_item_relations:
                # Add target work item ID
                if 'target' in relation and relation['target'].get('id'):
                    work_item_ids.add(relation['target']['id'])
                
                # Add source work item ID (for parent-child relationships)
                if 'source' in relation and relation['source'].get('id'):
                    work_item_ids.add(relation['source']['id'])
            
            work_item_ids = list(work_item_ids)
            total_count = len(work_item_ids)
            logger.info(f"Found {total_count} unique work items in iteration {iteration_id}")
            
            if not work_item_ids:
                return {
                    'work_items': [],
                    'total_count': 0,
                    'work_item_relations': work_item_relations
                }
            
            # Fetch detailed information for all work items
            work_items = self.get_work_items_by_ids(work_item_ids)
            
            return {
                'work_items': work_items,
                'total_count': total_count,
                'work_item_relations': work_item_relations
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch work items for iteration {iteration_id}: {e}")
            raise
    
    def add_work_items_to_iteration(self, team_id: str, iteration_id: str, work_item_ids: List[int]) -> List:
        """
        Add work items to an iteration (sprint).
        
        Args:
            team_id: The ID or name of the team
            iteration_id: The ID of the iteration
            work_item_ids: List of work item IDs to add to the iteration
        """
        logger.info(f"Adding {len(work_item_ids)} work items to iteration {iteration_id} in team: {team_id}")
        
        iteration = self.get_iteration(team_id, iteration_id)
        iteration_path = iteration.get('path') if isinstance(iteration, dict) else iteration.path
        
        results = []
        for work_item_id in work_item_ids:
            try:
                document = [{
                    "op": "replace",
                    "path": "/fields/System.IterationPath",
                    "value": iteration_path
                }]
                result = self.work_item_client.update_work_item(
                    document=document,
                    id=work_item_id,
                    project=self.project
                )
                results.append(result.as_dict() if hasattr(result, 'as_dict') else result)
            except Exception as e:
                logger.error(f"Failed to update work item {work_item_id} iteration: {e}")
        
        return results
    
    def get_team_capacity(self, team_id: str, iteration_id: str):
        """
        Get team capacity for a specific iteration.
        
        Args:
            team_id: The ID or name of the team
            iteration_id: The ID of the iteration
        """
        logger.info(f"Fetching team capacity for iteration {iteration_id} in team: {team_id}")
        
        try:
            result = self.work_client.get_capacities_with_identity_ref_and_totals(
                team_context=self._make_team_context(team_id),
                iteration_id=iteration_id
            )
            capacities = result.team_members if hasattr(result, 'team_members') else []
            return [capacity.as_dict() if hasattr(capacity, 'as_dict') else capacity for capacity in capacities]
        except Exception as e:
            logger.error(f"Failed to fetch capacity for iteration {iteration_id}: {e}")
            raise
    
    def update_team_member_capacity(self, team_id: str, iteration_id: str, team_member_id: str, capacity_per_day: float, days_off: Optional[List[dict]] = None):
        """
        Update capacity for a specific team member in an iteration.
        
        Args:
            team_id: The ID or name of the team
            iteration_id: The ID of the iteration
            team_member_id: The ID of the team member
            capacity_per_day: Available capacity per day (in hours)
            days_off: List of days off with start and end dates
        """
        logger.info(f"Updating capacity for team member {team_member_id} in iteration {iteration_id}")
        
        capacity_patch = {
            "activities": [{
                "capacityPerDay": capacity_per_day,
                "name": None
            }],
            "daysOff": days_off or []
        }
        
        try:
            result = self.work_client.update_capacity_with_identity_ref(
                patch=capacity_patch,
                team_context=self._make_team_context(team_id),
                iteration_id=iteration_id,
                team_member_id=team_member_id
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to update capacity for team member {team_member_id}: {e}")
            raise
    
    def get_work_item_revisions(self, work_item_id: int, top: Optional[int] = None, skip: Optional[int] = None):
        """
        Get the revision history for a work item.
        
        Args:
            work_item_id: The ID of the work item
            top: Maximum number of revisions to return.
                 If None, returns up to 1000 revisions (reasonable default for most work items).
                 Set explicitly to a higher value if needed.
            skip: Number of revisions to skip (for pagination)
        
        Note:
            - Azure DevOps default limit (when top=None): Varies, typically ~200
            - This method sets default to 1000 to capture comprehensive history
            - Use skip parameter for pagination if work item has extensive history
        """
        # Set explicit default to get comprehensive revision history
        query_top = top if top is not None else 1000
        
        logger.info(f"Fetching revision history for work item: {work_item_id}, top={query_top}, skip={skip}")
        
        try:
            result = self.work_item_client.get_revisions(
                id=work_item_id,
                project=self.project,
                top=query_top,
                skip=skip
            )
            revisions = [revision.as_dict() if hasattr(revision, 'as_dict') else revision for revision in result]
            logger.info(f"Fetched {len(revisions)} revisions for work item {work_item_id}")
            return revisions
        except Exception as e:
            logger.error(f"Failed to fetch revisions for work item {work_item_id}: {e}")
            raise
    
    def get_work_item_comments(self, work_item_id: int, top: Optional[int] = None, continuation_token: Optional[str] = None):
        """
        Get all comments for a work item.
        
        Args:
            work_item_id: The ID of the work item
            top: Maximum number of comments to return (1-200).
                 If None, returns up to 200 comments (Azure DevOps maximum).
            continuation_token: Token for pagination to get additional comments beyond 200
        
        Note:
            - Azure DevOps maximum limit: 200 comments per request
            - This method defaults to 200 to get as many comments as possible
            - Use continuation_token for pagination if work item has more than 200 comments
            - Returns a dictionary with 'comments' array and pagination info
        """
        # Azure DevOps limits comments API to maximum 200 per request
        query_top = top if top is not None else 200
        
        # Enforce Azure DevOps limit
        if query_top > 200:
            query_top = 200
        
        logger.info(f"Fetching comments for work item: {work_item_id}, top={query_top}")
        
        try:
            result = self.work_item_client.get_comments(
                project=self.project,
                work_item_id=work_item_id,
                top=query_top,
                continuation_token=continuation_token
            )
            result_dict = result.as_dict() if hasattr(result, 'as_dict') else result
            comment_count = len(result_dict.get('comments', [])) if isinstance(result_dict, dict) else 0
            logger.info(f"Fetched {comment_count} comments for work item {work_item_id}")
            return result_dict
        except Exception as e:
            logger.error(f"Failed to fetch comments for work item {work_item_id}: {e}")
            raise
    
    def add_work_item_comment(self, work_item_id: int, comment_text: str):
        """
        Add a comment to a work item.
        
        Args:
            work_item_id: The ID of the work item
            comment_text: The text of the comment to add
        """
        logger.info(f"Adding comment to work item {work_item_id}")
        
        if not comment_text or not comment_text.strip():
            raise ValueError("comment_text cannot be empty.")

        # Add comment via System.History field (most reliable method)
        document = [{
            "op": "add",
            "path": "/fields/System.History",
            "value": comment_text
        }]
        
        try:
            result = self.work_item_client.update_work_item(
                document=document,
                id=work_item_id,
                project=self.project
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to add comment to work item {work_item_id}: {e}")
            raise
    
    def get_work_item_attachments(self, work_item_id: int):
        """
        Get all attachments for a work item.
        
        Args:
            work_item_id: The ID of the work item
        """
        logger.info(f"Fetching attachments for work item: {work_item_id}")
        
        work_item = self.get_work_item(work_item_id, expand="relations")
        attachments = []
        
        if isinstance(work_item, dict):
            relations = work_item.get('relations', [])
        else:
            relations = work_item.relations if hasattr(work_item, 'relations') and work_item.relations else []
        
        for relation in relations:
            rel_data = relation if isinstance(relation, dict) else (relation.as_dict() if hasattr(relation, 'as_dict') else relation)
            rel_type = rel_data.get('rel') if isinstance(rel_data, dict) else getattr(rel_data, 'rel', None)
            if rel_type == "AttachedFile":
                attachments.append(rel_data if isinstance(rel_data, dict) else rel_data)
        
        return attachments
    
    def get_project_areas(self, depth: Optional[int] = None):
        """
        Get all area paths for the project.
        
        Args:
            depth: Depth of the area tree to return. Default: None (all levels)
        """
        logger.info(f"Fetching area paths for project, depth: {depth}")
        
        try:
            result = self.work_item_client.get_classification_node(
                project=self.project,
                structure_group='areas',
                depth=depth
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to fetch area paths: {e}")
            raise
    
    def get_project_iterations(self, depth: Optional[int] = None):
        """
        Get all iteration paths for the project.
        
        Args:
            depth: Depth of the iteration tree to return. Default: None (all levels)
        """
        logger.info(f"Fetching iteration paths for project, depth: {depth}")
        
        try:
            result = self.work_item_client.get_classification_node(
                project=self.project,
                structure_group='iterations',
                depth=depth
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to fetch iteration paths: {e}")
            raise
    
    def get_work_item_states(self, work_item_type: str):
        """
        Get all possible states for a work item type.
        
        Args:
            work_item_type: The type of work item (e.g., 'User Story', 'Task', 'Bug')
        
        Note:
            Returns list of state dictionaries with 'name', 'category', 'color' fields.
        """
        logger.info(f"Fetching states for work item type: {work_item_type}")
        
        try:
            work_item_type_obj = self.work_item_client.get_work_item_type_states(
                project=self.project,
                type=work_item_type
            )
            
            # Check if work_item_type_obj itself is a list (some Azure DevOps versions return the list directly)
            if isinstance(work_item_type_obj, list):
                states = work_item_type_obj
            else:
                states = work_item_type_obj.states if hasattr(work_item_type_obj, 'states') else []
            
            result = [state.as_dict() if hasattr(state, 'as_dict') else state for state in states]
          
            
            return result
        except Exception as e:
            logger.error(f"Failed to fetch states for work item type '{work_item_type}': {e}")
            raise
    
    def get_work_item_transitions(self, work_item_id: int):
        """
        Get all possible state transitions for a work item from its current state.
        
        Returns information about the current state and all available states that the
        work item can potentially transition to.
        
        Args:
            work_item_id: The ID of the work item
        
        Note:
            Returns dictionary with 'current_state', 'work_item_type', 'available_states' 
            (list of all possible states for this work item type), and 'work_item_id'.
        """
        logger.info(f"Fetching transitions for work item: {work_item_id}")
        
        try:
            work_item = self.get_work_item(work_item_id)
            fields = work_item.get('fields') if isinstance(work_item, dict) else work_item.fields
            current_state = fields.get('System.State') if isinstance(fields, dict) else getattr(fields, 'System.State', None)
            work_item_type = fields.get('System.WorkItemType') if isinstance(fields, dict) else getattr(fields, 'System.WorkItemType', None)
            
            all_states = self.get_work_item_states(work_item_type)
            
            # Extract state names and info
            available_states = []
            for state in all_states:
                state_dict = state if isinstance(state, dict) else (state.as_dict() if hasattr(state, 'as_dict') else {'name': str(state)})
                state_name = state_dict.get('name', str(state))
                
                # Add state with indication if it's the current state
                available_states.append({
                    'name': state_name,
                    'is_current': state_name == current_state,
                    'category': state_dict.get('category'),
                    'color': state_dict.get('color')
                })
            
            result = {
                'work_item_id': work_item_id,
                'current_state': current_state,
                'work_item_type': work_item_type,
                'available_states': available_states,
                'total_states': len(available_states)
            }
            
            logger.info(f"Work item {work_item_id} is in state '{current_state}' with {len(available_states)} possible states")
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch transitions for work item {work_item_id}: {e}")
            raise
    
    def update_work_item_state(self, work_item_id: int, new_state: str, reason: Optional[str] = None):
        """
        Update the state of a work item.
        
        Args:
            work_item_id: The ID of the work item
            new_state: The target state name
            reason: Optional reason for the state change
        """
        logger.info(f"Updating work item {work_item_id} state to: {new_state}")
        
        document = [{
            "op": "replace",
            "path": "/fields/System.State",
            "value": new_state
        }]
        
        if reason:
            document.append({
                "op": "replace",
                "path": "/fields/System.Reason",
                "value": reason
            })
        
        try:
            result = self.work_item_client.update_work_item(
                document=document,
                id=work_item_id,
                project=self.project
            )
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to update state for work item {work_item_id}: {e}")
            raise
    
    def assign_work_item(self, work_item_id: int, assignee: str):
        """
        Assign a work item to a specific user.
        
        Args:
            work_item_id: The ID of the work item to assign
            assignee: Email address (e.g., "user@company.com") or display name (e.g., "John Smith") of the person to assign to
        
        Note:
            Email addresses are more reliable than display names when multiple people have similar names. The assignee value should be validated against the list of board users (from get_board_users) to ensure
            that the provided name, email, or unique identifier matches an existing user in the project. 
            
        
        Example:
            # Assign by email (recommended)
            client.assign_work_item(123, "john.smith@company.com")
            
            # Assign by display name
            client.assign_work_item(123, "John Smith")
        """
        logger.info(f"Assigning work item {work_item_id} to: {assignee}")
        
        document = [{
            "op": "replace",
            "path": "/fields/System.AssignedTo",
            "value": assignee
        }]
        
        try:
            result = self.work_item_client.update_work_item(
                document=document,
                id=work_item_id,
                project=self.project
            )
            logger.info(f"Successfully assigned work item {work_item_id} to {assignee}")
            return result.as_dict() if hasattr(result, 'as_dict') else result
        except Exception as e:
            logger.error(f"Failed to assign work item {work_item_id} to {assignee}: {e}")
            raise
    
    def get_project_info(self):
        """
        Get detailed information about the current project.
        """
        logger.info(f"Fetching project information for: {self.project}")
        
        result = self.core_client.get_project(project_id=self.project)
        return result.as_dict() if hasattr(result, 'as_dict') else result
    
    def search_work_items(self, search_text: str, top: Optional[int] = None):
        """
        Search for work items by text content in TITLE and DESCRIPTION fields ONLY.
        
        **IMPORTANT: This method does NOT search the following fields:**
        - System.AssignedTo (use get_work_items_by_query with WIQL instead)
        - System.Tags
        - System.State
        - Custom fields
        
        **Use this method when:**
        - Searching for keywords in work item titles or descriptions
        - Finding work items by feature names, bug descriptions, or task content
        
        **DO NOT use this method when:**
        - Searching for work items assigned to a specific person (use get_work_items_by_query)
        - Filtering by state, priority, or other fields (use get_work_items_by_query)
        
        **Example for finding assigned work items:**
        ```python
        # Instead of: search_work_items("John Doe")  # ❌ Won't work
        # Use this:
        query = "SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.AssignedTo] = 'John Doe'"
        items = get_work_items_by_query(query)  # ✅ Correct
        ```
        
        Args:
            search_text: Text to search for in title and description
            top: Maximum number of results to return.
                 If None, returns all matching results (up to Azure DevOps limit of 20000).
        
        Note:
            Returns list of work items matching the search text in title or description.
        """
        logger.info(f"Searching work items for text: {search_text}, top: {top}")
        
        safe_text = search_text.replace("'", "''")

        wiql_query = f"""
        SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State]
        FROM WorkItems
        WHERE [System.TeamProject] = '{self.project}'
        AND ([System.Title] CONTAINS '{safe_text}' OR [System.Description] CONTAINS '{safe_text}')
        """
        
        return self.get_work_items_by_query(wiql_query, top=top)
    
    def get_work_items_by_assignee(self, assignee: str, state: Optional[str] = None, work_item_type: Optional[str] = None, top: Optional[int] = None):
        """
        Get all work items assigned to a specific user.
        
        You can use either display name OR email address to identify the user.
        Email addresses are more reliable when multiple people have the same name.
        
        Args:
            assignee: Email address (e.g., "user@company.com") or display name (e.g., "John Smith")
            state: Optional filter by state (e.g., "Active", "In Progress", "Done")
            work_item_type: Optional filter by work item type (e.g., "Task", "User Story", "Bug")
            top: Maximum number of results to return. If None, returns all (up to 20000).
        
        Note:
            Returns list of work items assigned to the specified user. The assignee value should be validated against the list of board users (from get_board_users) to ensure
            that the provided name, email, or unique identifier matches an existing user in the project. 
            
        
        Example:
            # By email (recommended for uniqueness)
            items = client.get_work_items_by_assignee("john.smith@company.com")
            
            # By display name
            items = client.get_work_items_by_assignee("John Smith")
            
            # With filters
            items = client.get_work_items_by_assignee("john.smith@company.com", state="In Progress", work_item_type="Task")
        """
        logger.info(f"Fetching work items assigned to: {assignee}, state: {state}, type: {work_item_type}")
        
        # Escape single quotes in the assignee
        safe_assignee = assignee.replace("'", "''")
        
        # Build the WIQL query
        where_clauses = [f"[System.TeamProject] = '{self.project}'"]
        where_clauses.append(f"[System.AssignedTo] = '{safe_assignee}'")
        
        if state:
            safe_state = state.replace("'", "''")
            where_clauses.append(f"[System.State] = '{safe_state}'")
        
        if work_item_type:
            safe_type = work_item_type.replace("'", "''")
            where_clauses.append(f"[System.WorkItemType] = '{safe_type}'")
        
        wiql_query = f"""
        SELECT [System.Id], [System.Title], [System.State], [System.WorkItemType], [System.AssignedTo]
        FROM WorkItems
        WHERE {' AND '.join(where_clauses)}
        ORDER BY [System.Id] DESC
        """
        
        return self.get_work_items_by_query(wiql_query, top=top)
    
    def get_work_items_by_ids(self, work_item_ids: List[int], fields: Optional[List[str]] = None) -> List:
        """
        Get multiple work items by their IDs.
        
        Args:
            work_item_ids: List of work item IDs to retrieve
            fields: List of field names to return. If None, returns all fields
        """
        logger.info(f"Fetching {len(work_item_ids)} work items by IDs")
        
        if not work_item_ids:
            return []

        work_items = self.work_item_client.get_work_items(
            ids=work_item_ids,
            project=self.project,
            fields=fields
        )
        return [wi.as_dict() if hasattr(wi, 'as_dict') else wi for wi in work_items]
    
    # def delete_work_item(self, work_item_id: int, destroy: bool = False):
    #     """
    #     Delete a work item (recycle bin by default, permanent if destroy=True).
        
    #     Args:
    #         work_item_id: The ID of the work item to delete
    #         destroy: Whether to permanently delete (True) or move to recycle bin (False)
    #     """
    #     logger.info(f"Deleting work item {work_item_id}, destroy: {destroy}")
        
    #     try:
    #         return self.work_item_client.delete_work_item(
    #             id=work_item_id,
    #             project=self.project,
    #             destroy=destroy
    #         )
    #     except Exception as e:
    #         logger.error(f"Failed to delete work item {work_item_id}: {e}")
    #         raise
    
    # def restore_work_item(self, work_item_id: int):
    #     """
    #     Restore a work item from the recycle bin.
        
    #     Args:
    #         work_item_id: The ID of the work item to restore
    #     """
    #     logger.info(f"Restoring work item {work_item_id} from recycle bin")
        
    #     try:
    #         return self.work_item_client.restore_work_item(
    #             id=work_item_id,
    #             project=self.project
    #         )
    #     except Exception as e:
    #         logger.error(f"Failed to restore work item {work_item_id}: {e}")
    #         raise
    
    # def get_current_user(self):
    #     """
    #     Get information about the currently authenticated user.
    #     """
    #     logger.info("Fetching current user information")
        
    #     return self.connection.get_client('ms.vss-web.location-service').get_connection_data()
    
    def get_current_user(self):
        """
        Get information about the authenticated Azure DevOps user.
        """
        logger.info("Fetching current user information")

        location_client = self.connection.clients.get_location_client()
        data = location_client.get_connection_data()
        
        user = data.authenticated_user
        return user.as_dict() if hasattr(user, 'as_dict') else user

    def __getattr__(self, name: str):
        """
        Dynamically proxy method calls not explicitly defined to the underlying clients.
        
        Args:
            name: The method name being accessed
        """
        if name in ('work_item_client', 'work_client', 'core_client', 'connection'):
            raise AttributeError(f"Client '{name}' is not initialized.")

        logger.debug(f"Proxying method call: {name}")
        
        for client in [self.work_item_client, self.work_client, self.core_client]:
            if hasattr(client, name):
                return getattr(client, name)
        
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
