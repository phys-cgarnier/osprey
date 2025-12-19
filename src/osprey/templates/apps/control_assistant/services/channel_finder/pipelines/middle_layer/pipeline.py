"""
Middle Layer React Agent Pipeline

Implements channel finding using a React-style agent with database query tools.
This approach mimics production accelerator control systems where an agent
explores a functional hierarchy (System → Family → Field) using tools rather
than navigating a tree structure.

Key differences from hierarchical pipeline:
- Agent queries database using tools instead of navigating tree
- PV names are retrieved from database instead of built from selections
- Organization is by function (Monitor, Setpoint) not naming pattern
- Supports device/sector filtering and subfield navigation

This pipeline is based on the MATLAB Middle Layer (MML) pattern used in
production at facilities like ALS, ESRF, and others.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from osprey.models import get_chat_completion, get_model
from osprey.utils.config import _get_config
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext, Tool

from ...core.base_pipeline import BasePipeline
from ...core.models import ChannelFinderResult, ChannelInfo, QuerySplitterOutput
from ...utils.prompt_loader import load_prompts

logger = logging.getLogger(__name__)


# === Output Models ===


class PVQueryOutput(BaseModel):
    """Output from PV query agent."""

    pvs: List[str] = Field(description="List of found PV addresses")
    description: str = Field(description="Description of search process and results")


# === Tool Support Functions ===


def _save_prompt_to_file(prompt: str, stage: str, query: str = ""):
    """Save prompt to temporary file for inspection."""
    config_builder = _get_config()
    if not config_builder.get("debug.save_prompts", False):
        return

    prompts_dir = config_builder.get("debug.prompts_dir", "temp_prompts")
    project_root = Path(config_builder.get("project_root"))
    temp_dir = project_root / prompts_dir
    temp_dir.mkdir(exist_ok=True, parents=True)

    # Map stage names
    if stage == "query_split":
        filename = "prompt_stage1_query_split.txt"
    elif stage == "pv_query":
        filename = "prompt_stage2_pv_query.txt"
    else:
        filename = f"prompt_{stage}.txt"

    filepath = temp_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"=== STAGE: {stage.upper()} ===\n")
        f.write(f"=== TIMESTAMP: {datetime.now().isoformat()} ===\n")
        if query:
            f.write(f"=== QUERY: {query} ===\n")
        f.write("=" * 80 + "\n\n")
        f.write(prompt)

    logger.debug(f"  [dim]Saved prompt to: {filepath}[/dim]")


# === Pipeline Implementation ===


class MiddleLayerPipeline(BasePipeline):
    """
    Middle Layer React Agent Pipeline.

    Uses React-style agent with database query tools to find channels.
    """

    def __init__(
        self,
        database,  # MiddleLayerDatabase
        model_config: dict,
        facility_name: str = "control system",
        facility_description: str = "",
        **kwargs,
    ):
        """
        Initialize middle layer pipeline.

        Args:
            database: MiddleLayerDatabase instance
            model_config: LLM model configuration
            facility_name: Name of facility
            facility_description: Facility description for context
            **kwargs: Additional pipeline arguments
        """
        super().__init__(database, model_config, **kwargs)
        self.facility_name = facility_name
        self.facility_description = facility_description

        # Load query splitter prompt
        config_builder = _get_config()
        prompts_module = load_prompts(config_builder.raw_config)
        self.query_splitter = prompts_module.query_splitter

        # Create React agent with tools
        self._create_agent()

    @property
    def pipeline_name(self) -> str:
        """Return the pipeline name."""
        return "Middle Layer React Agent"

    def _create_agent(self):
        """Create the React agent with database query tools."""
        # Tool functions that access database
        def list_systems() -> List[Dict[str, str]]:
            """Get list of all available systems in the control system.

            Returns:
                List of dicts with 'name' and 'description' keys.
                Example: [
                    {'name': 'SR', 'description': 'Storage Ring - main synchrotron light source'},
                    {'name': 'BR', 'description': 'Booster Ring - accelerates beam to 1.9 GeV'},
                    {'name': 'BTS', 'description': ''}  # Empty string if no description
                ]
            """
            logger.info("Tool: list_systems() called")
            result = self.database.list_systems()
            logger.debug(f"  → Returned {len(result)} systems")
            return result

        def list_families(system: str) -> List[Dict[str, str]]:
            """Get list of device families in a specific system.

            Args:
                system: System name (e.g., 'SR', 'BR')

            Returns:
                List of dicts with 'name' and 'description' keys.
                Example: [
                    {'name': 'BPM', 'description': 'Beam Position Monitors - measure beam X/Y position'},
                    {'name': 'HCM', 'description': 'Horizontal Corrector Magnets'},
                    {'name': 'DCCT', 'description': ''}  # Empty string if no description
                ]
            """
            logger.info(f"Tool: list_families(system='{system}') called")
            try:
                result = self.database.list_families(system)
                logger.debug(f"  → Returned {len(result)} families")
                return result
            except ValueError as e:
                raise ModelRetry(str(e))

        def inspect_fields(system: str, family: str, field: str = None) -> Dict[str, Dict[str, str]]:
            """Inspect the structure of fields within a family.

            Use this to discover what fields and subfields are available
            before querying for channel names. Includes descriptions when available.

            Args:
                system: System name
                family: Family name
                field: Optional field name to inspect subfields (if None, shows top-level fields)

            Returns:
                Dict mapping field/subfield names to dicts with 'type' and 'description'.
                Example: {
                    'Monitor': {
                        'type': 'ChannelNames',
                        'description': 'Position readback values in mm'
                    },
                    'Setpoint': {
                        'type': 'dict (has subfields)',
                        'description': 'Position setpoint controls'
                    },
                    'OnControl': {
                        'type': 'ChannelNames',
                        'description': ''  # Empty string if no description provided
                    }
                }
            """
            logger.info(f"Tool: inspect_fields(system='{system}', family='{family}', field='{field}') called")
            try:
                result = self.database.inspect_fields(system, family, field)
                logger.debug(f"  → Returned {len(result)} fields")
                return result
            except ValueError as e:
                raise ModelRetry(str(e))

        def list_channel_names(
            system: str,
            family: str,
            field: str,
            subfield: str = None,
            sectors: List[int] = None,
            devices: List[int] = None,
        ) -> List[str]:
            """Get the actual PV addresses for a specific field or subfield.

            This is the main tool for retrieving channel names. Use after
            exploring the structure with inspect_fields.

            Args:
                system: System name (e.g., 'SR')
                family: Family name (e.g., 'BPM')
                field: Field name (e.g., 'Monitor', 'Setpoint')
                subfield: Optional subfield name (e.g., 'X', 'Y' under Setpoint)
                sectors: Optional list of sector numbers to filter by
                devices: Optional list of device numbers to filter by

            Returns:
                List of PV addresses (e.g., ['SR01C:BPM1:X', 'SR01C:BPM2:X'])
            """
            logger.info(
                f"Tool: list_channel_names(system='{system}', family='{family}', "
                f"field='{field}', subfield='{subfield}', sectors={sectors}, devices={devices}) called"
            )
            try:
                result = self.database.list_channel_names(
                    system, family, field, subfield, sectors, devices
                )
                logger.debug(f"  → Returned {len(result)} channels")
                return result
            except ValueError as e:
                raise ModelRetry(str(e))

        def get_common_names(system: str, family: str) -> List[str]:
            """Get friendly/common names for devices in a family.

            Useful for understanding what devices exist before filtering
            by sectors/devices.

            Args:
                system: System name
                family: Family name

            Returns:
                List of common names (e.g., ['BPM 1', 'BPM 2', ...])
                Returns empty list if not available.
            """
            logger.info(f"Tool: get_common_names(system='{system}', family='{family}') called")
            result = self.database.get_common_names(system, family)
            if result is None:
                logger.debug("  → No common names available")
                return []
            logger.debug(f"  → Returned {len(result)} common names")
            return result

        # Create agent with tools
        self.agent = Agent(
            model=get_model(model_config=self.model_config),
            tools=[
                Tool(list_systems, takes_ctx=False),
                Tool(list_families, takes_ctx=False),
                Tool(inspect_fields, takes_ctx=False),
                Tool(list_channel_names, takes_ctx=False),
                Tool(get_common_names, takes_ctx=False),
            ],
            result_type=PVQueryOutput,
            system_prompt=self._get_system_prompt(),
        )

    def _get_system_prompt(self) -> str:
        """Build system prompt for the React agent."""
        facility_context = ""
        if self.facility_description:
            facility_context = f"\nFacility Context:\n{self.facility_description}\n"

        prompt = f"""You are a specialized agent for finding process variable (PV) addresses in the {self.facility_name} control system.
{facility_context}
Your task is to explore the control system database using the provided tools and find the correct PV addresses that match the user's query.

Database Organization:
The database follows a Middle Layer (MML) functional hierarchy:
- **Systems**: Top-level accelerator systems (e.g., SR=Storage Ring, BR=Booster Ring, BTS=Booster-to-Storage transport)
- **Families**: Device families within systems (e.g., BPM=Beam Position Monitors, HCM=Horizontal Corrector Magnets, DCCT=Beam Current)
- **Fields**: Functional categories (e.g., Monitor=readback values, Setpoint=control values)
- **Subfields**: Optional nested organization within fields (e.g., X/Y positions, different signal types)
- **ChannelNames**: The actual EPICS PV addresses you need to return

Using Descriptions:
The database MAY include optional description fields at various levels (systems, families, fields, subfields).
When descriptions are present:
- READ THEM CAREFULLY - they provide crucial context about what each component does
- USE THEM to match user queries - descriptions often contain domain-specific terminology
- PRIORITIZE matches based on description content over just names
- Example: If query asks for "beam position readback", a field with description "Position readback values in mm" is likely correct

When descriptions are ABSENT (empty strings):
- Fall back to interpreting the names themselves
- Use common patterns and domain knowledge
- Descriptive names like "Monitor", "Setpoint", "X", "Y" are often self-explanatory

Strategy:
1. Start by exploring available systems with list_systems() - check descriptions if available
2. Find relevant families with list_families(system) - read family descriptions to understand device types
3. Inspect field structure with inspect_fields(system, family) - use descriptions to understand field purposes
4. For nested structures, use inspect_fields(system, family, field) to explore subfields
5. Retrieve channel names with list_channel_names(system, family, field, ...)
6. Use filtering (sectors, devices) when query specifies specific devices
7. Use subfield parameter when fields have nested structure

Common Patterns (when descriptions are not available):
- "beam current" → Usually in DCCT family, Monitor field
- "BPM positions" → BPM family, Monitor or Setpoint fields, may have X/Y subfields
- "corrector magnets" → HCM (horizontal) or VCM (vertical) families
- "readback" or "monitor" → Use Monitor field
- "setpoint" or "control" → Use Setpoint field
- Specific device numbers (e.g., "BPM 1") → Use devices parameter for filtering

Important:
- Always use tools to explore the database - don't guess PV names
- Descriptions are OPTIONAL - some databases have them, some don't
- When available, descriptions are the BEST source of information
- If query mentions specific systems/devices, focus your search there
- Return ALL matching PVs if query is general (e.g., "all BPM positions")
- Use filtering to narrow down when query specifies particular devices
- Provide clear description of what you found and how

Your response must include:
- pvs: List of found PV addresses (can be empty if none found)
- description: Explanation of search process and what was found
"""
        return prompt

    async def process_query(self, query: str) -> ChannelFinderResult:
        """
        Execute middle layer pipeline.

        Stages:
        1. Split query (if needed)
        2. For each sub-query, run React agent with tools
        3. Aggregate results

        Args:
            query: Natural language query

        Returns:
            ChannelFinderResult with found channels
        """
        # Handle empty query
        if not query or not query.strip():
            return ChannelFinderResult(
                query=query, channels=[], total_channels=0, processing_notes="Empty query provided"
            )

        # Stage 1: Split query into atomic queries
        atomic_queries = await self._split_query(query)
        logger.info(
            f"[bold cyan]Stage 1:[/bold cyan] Split into {len(atomic_queries)} atomic quer{'y' if len(atomic_queries) == 1 else 'ies'}"
        )

        if len(atomic_queries) > 1:
            for i, aq in enumerate(atomic_queries, 1):
                logger.info(f"  → Query {i}: {aq}")

        # Stage 2: Process each query with React agent
        all_pvs = []
        for i, atomic_query in enumerate(atomic_queries, 1):
            if len(atomic_queries) == 1:
                logger.info(f"[bold cyan]Stage 2:[/bold cyan] Querying database with React agent...")
            else:
                logger.info(
                    f"[bold cyan]Stage 2 - Query {i}/{len(atomic_queries)}:[/bold cyan] {atomic_query}"
                )

            try:
                result = await self._query_with_agent(atomic_query)
                all_pvs.extend(result.pvs)
                logger.info(f"  → Found {len(result.pvs)} PV(s)")
                logger.debug(f"  → {result.description}")
            except Exception as e:
                logger.error(f"  [red]✗[/red] Error processing query: {e}")
                continue

        # Stage 3: Deduplicate and build result
        unique_pvs = list(dict.fromkeys(all_pvs))  # Preserve order while deduplicating

        return self._build_result(query, unique_pvs)

    async def _split_query(self, query: str) -> List[str]:
        """Split query into atomic sub-queries."""
        prompt = self.query_splitter.get_prompt(facility_name=self.facility_name)
        message = f"{prompt}\n\nQuery to process: {query}"

        _save_prompt_to_file(message, "query_split", query)

        # Set caller context for API call logging
        from osprey.models import set_api_call_context

        set_api_call_context(
            function="_split_query",
            module="middle_layer.pipeline",
            class_name="MiddleLayerPipeline",
            extra={"stage": "query_split"},
        )

        response = await asyncio.to_thread(
            get_chat_completion,
            message=message,
            model_config=self.model_config,
            output_model=QuerySplitterOutput,
        )

        return response.queries

    async def _query_with_agent(self, query: str) -> PVQueryOutput:
        """Query database using React agent with tools."""
        # Set caller context for API call logging
        from osprey.models import set_api_call_context

        set_api_call_context(
            function="_query_with_agent",
            module="middle_layer.pipeline",
            class_name="MiddleLayerPipeline",
            extra={"stage": "pv_query"},
        )

        # Run agent
        result = await self.agent.run(query)

        return result.data

    def _build_result(self, query: str, pvs: List[str]) -> ChannelFinderResult:
        """Build final result object."""
        channel_infos = []

        for pv in pvs:
            channel_data = self.database.get_channel(pv)
            if channel_data:
                channel_infos.append(
                    ChannelInfo(
                        channel=pv,
                        address=channel_data.get("address", pv),
                        description=channel_data.get("description"),
                    )
                )

        notes = (
            f"Processed query using React agent with database tools. " f"Found {len(channel_infos)} channels."
        )

        return ChannelFinderResult(
            query=query,
            channels=channel_infos,
            total_channels=len(channel_infos),
            processing_notes=notes,
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Return pipeline statistics."""
        db_stats = self.database.get_statistics()
        return {
            "total_channels": db_stats.get("total_channels", 0),
            "systems": db_stats.get("systems", 0),
            "families": db_stats.get("families", 0),
        }

