import google.auth
from google.adk.agents import Agent
from google.adk.tools.bigquery import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig
from google.adk.tools.data_agent.data_agent_toolset import DataAgentToolset
from google.adk.tools.data_agent.config import DataAgentToolConfig
from google.adk.tools.data_agent.credentials import DataAgentCredentialsConfig

from config import settings
from .prompt import build_system_prompt

_bq_toolset = BigQueryToolset(
    bigquery_tool_config=BigQueryToolConfig(max_query_result_rows=200)
)

_adc, _ = google.auth.default()
_da_toolset = DataAgentToolset(
    credentials_config=DataAgentCredentialsConfig(credentials=_adc),
    data_agent_tool_config=DataAgentToolConfig(max_query_result_rows=200),
    tool_filter=["list_accessible_data_agents", "get_data_agent_info", "ask_data_agent"],
)

root_agent = Agent(
    model="gemini-2.5-flash",
    name="aircraft_agent",
    description="Aircraft data intelligence agent with BigQuery insights and CAA API",
    instruction=build_system_prompt(
        settings.project_id, settings.dataset_id, settings.table_id
    ),
    tools=[_bq_toolset, _da_toolset],
)
