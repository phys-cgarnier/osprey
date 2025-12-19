# Middle Layer Pipeline - Complete Implementation Guide

## Overview

The **middle_layer** pipeline is the third built-in channel finder pipeline in Osprey, providing a React agent-based approach to channel finding using database query tools. This implementation is based on the MATLAB Middle Layer (MML) pattern used in production at facilities like ALS, ESRF, and others.

## Key Features

✅ **React Agent Architecture**: Agent explores database using tools instead of navigating trees
✅ **Functional Organization**: System → Family → Field (not naming patterns)
✅ **Device/Sector Filtering**: Filter PVs by device numbers and sector numbers
✅ **Subfield Support**: Navigate nested field structures (e.g., X/Y positions)
✅ **Production-Proven Pattern**: Based on real accelerator control system deployments

## Architecture Comparison

### Three Pipeline Approaches

| Feature | In-Context | Hierarchical | Middle Layer |
|---------|-----------|--------------|--------------|
| **Approach** | Semantic search | Tree navigation | React agent + tools |
| **Database** | Flat list | Tree structure | Functional hierarchy |
| **PV Names** | Retrieved from DB | Built from selections | Retrieved from DB |
| **Best For** | Small DBs (<100) | Strict naming patterns | Functional organization |
| **Filtering** | N/A | By selection | By device/sector |
| **LLM Calls** | 3-5 per query | 5-8 per query | 4-10 per query |

### When to Use Middle Layer

✅ **Use middle_layer when:**
- Your system is organized by function (Monitor, Setpoint) not naming
- PV names don't follow strict hierarchical patterns
- You need to filter by device numbers or sector numbers
- Your production system uses MATLAB Middle Layer (MML)
- You want the agent to dynamically explore the database

❌ **Don't use middle_layer when:**
- You have <100 channels (use in_context instead)
- Your PVs follow strict naming patterns (use hierarchical instead)
- You don't need filtering capabilities

## Implementation Components

### 1. Database Class (`databases/middle_layer.py`)

```python
class MiddleLayerDatabase(BaseDatabase):
    """MML-style database with functional hierarchy."""

    # Core methods
    def list_systems() -> List[str]
    def list_families(system: str) -> List[str]
    def inspect_fields(system, family, field=None) -> Dict[str, str]
    def list_channel_names(system, family, field, subfield=None,
                          sectors=None, devices=None) -> List[str]
    def get_common_names(system, family) -> List[str]
```

**Key capabilities:**
- Loads JSON database with System→Family→Field hierarchy
- Builds flat channel map for O(1) validation
- Supports device/sector filtering using DeviceList metadata
- Handles nested subfields automatically

### 2. Pipeline Class (`pipelines/middle_layer/pipeline.py`)

```python
class MiddleLayerPipeline(BasePipeline):
    """React agent pipeline with database query tools."""

    async def process_query(query: str) -> ChannelFinderResult:
        # 1. Split query into atomic queries
        # 2. For each query: run React agent with tools
        # 3. Aggregate and deduplicate results
```

**Agent tools:**
- `list_systems()` - Get available systems
- `list_families(system)` - Get families in system
- `inspect_fields(system, family, field)` - Inspect structure
- `list_channel_names(...)` - Retrieve PV addresses
- `get_common_names(system, family)` - Get friendly names

### 3. Database Format

```json
{
  "SYSTEM": {
    "FAMILY": {
      "FIELD": {
        "ChannelNames": ["PV1", "PV2", ...]
      },
      "FIELD_WITH_SUBFIELDS": {
        "SUBFIELD1": {
          "ChannelNames": ["PV1", ...]
        },
        "SUBFIELD2": {
          "ChannelNames": ["PV2", ...]
        }
      },
      "setup": {
        "CommonNames": ["Device 1", "Device 2"],
        "DeviceList": [[sector, device], ...]
      }
    }
  }
}
```

**Required elements:**
- `ChannelNames`: List of PV addresses
- `setup.DeviceList`: For device/sector filtering (optional)
- `setup.CommonNames`: Friendly names (optional)

**Optional description fields:**
The database supports optional `_description` fields at any level (system, family, field, subfield). Descriptions are **opt-in** and the system works with or without them.

```json
{
  "SR": {
    "_description": "Storage Ring - main synchrotron light source",
    "BPM": {
      "_description": "Beam Position Monitors - measure beam X/Y position",
      "Monitor": {
        "_description": "Position readback values in millimeters",
        "ChannelNames": ["SR01C:BPM1:X", ...]
      },
      "X": {
        "ChannelNames": ["SR01C:BPM1:X", ...]
      }
    }
  }
}
```

**When to use descriptions:**
- ✅ **Use descriptions** when names alone are not self-explanatory
- ✅ **Use descriptions** to provide technical context (units, physics, purpose)
- ✅ **Use descriptions** to help LLM match domain-specific terminology
- ❌ **Skip descriptions** when names like "Monitor", "Setpoint", "X", "Y" are clear
- ❌ **Skip descriptions** for well-known abbreviations in your facility

**How the agent uses descriptions:**
- When present: Descriptions are the **primary** source for understanding what each component does
- When absent: Agent falls back to interpreting names and using domain knowledge
- Descriptions are returned by all navigation tools (`list_systems`, `list_families`, `inspect_fields`)

**Naming conventions:**
- Systems: Upper case abbreviations (SR, BR, BTS, LN)
- Families: Upper case device types (BPM, HCM, VCM, DCCT, RF)
- Fields: CamelCase functions (Monitor, Setpoint, Status)
- Subfields: CamelCase or single letters (X, Y, Frequency, Voltage)

## Configuration

### Basic Config

```yaml
channel_finder:
  pipeline_mode: "middle_layer"

  pipelines:
    middle_layer:
      database:
        type: "middle_layer"
        path: "data/channel_databases/middle_layer.json"

models:
  channel_finder:
    provider: openai
    model_id: gpt-4-turbo-preview
    temperature: 0
```

### Advanced Config

```yaml
channel_finder:
  pipeline_mode: "middle_layer"

  pipelines:
    middle_layer:
      database:
        type: "middle_layer"
        path: "data/channel_databases/my_facility.json"

facility:
  name: "My Accelerator Facility"

models:
  channel_finder:
    provider: openai
    model_id: gpt-4-turbo-preview
    temperature: 0
    max_tokens: 4096
```

## Sample Queries and Agent Behavior

### Query: "What is the beam current PV?"

**Agent strategy:**
1. `list_systems()` → finds ["SR", "BR", "BTS"]
2. `list_families("SR")` → finds "DCCT" family
3. `inspect_fields("SR", "DCCT")` → finds "Monitor" field
4. `list_channel_names("SR", "DCCT", "Monitor")` → returns `["SR:DCCT:Current"]`

### Query: "Find BPM X positions for sector 1"

**Agent strategy:**
1. Identifies BPM family across systems
2. Inspects BPM fields, finds "Monitor" or "Setpoint"
3. Checks for subfields, finds "X" and "Y"
4. Uses `sectors=[1]` filter:
   - `list_channel_names("SR", "BPM", "Monitor", sectors=[1])`
   - OR `list_channel_names("SR", "BPM", "Setpoint", subfield="X", sectors=[1])`
5. Returns filtered PVs for sector 1 only

### Query: "All RF frequency readbacks"

**Agent strategy:**
1. Finds RF family
2. Inspects fields, identifies Monitor field with Frequency subfield
3. Retrieves all: `list_channel_names("SR", "RF", "Monitor", subfield="Frequency")`
4. Returns all RF frequency monitor PVs

## Example Database Creation

### Step 1: Define Your Hierarchy

```
SR (Storage Ring)
  ├─ BPM (Beam Position Monitors)
  │   ├─ Monitor (readback values)
  │   └─ Setpoint (control values)
  │       ├─ X (horizontal setpoints)
  │       └─ Y (vertical setpoints)
  ├─ HCM (Horizontal Corrector Magnets)
  │   ├─ Monitor
  │   └─ Setpoint
  └─ DCCT (Beam Current Monitor)
      └─ Monitor
```

### Step 2: Create JSON

```json
{
  "SR": {
    "BPM": {
      "Monitor": {
        "ChannelNames": [
          "SR01C:BPM1:X", "SR01C:BPM1:Y",
          "SR01C:BPM2:X", "SR01C:BPM2:Y"
        ]
      },
      "Setpoint": {
        "X": {
          "ChannelNames": ["SR01C:BPM1:XSet", "SR01C:BPM2:XSet"]
        },
        "Y": {
          "ChannelNames": ["SR01C:BPM1:YSet", "SR01C:BPM2:YSet"]
        }
      },
      "setup": {
        "CommonNames": ["BPM 1-1", "BPM 1-2"],
        "DeviceList": [[1, 1], [1, 2]]
      }
    },
    "DCCT": {
      "Monitor": {
        "ChannelNames": ["SR:DCCT:Current"]
      }
    }
  }
}
```

### Step 3: Test

```python
from osprey.templates.apps.control_assistant.services.channel_finder import ChannelFinderService

service = ChannelFinderService(pipeline_mode="middle_layer")

# Test basic query
result = await service.find_channels("beam current")
assert "SR:DCCT:Current" in [ch.channel for ch in result.channels]

# Test with filtering
result = await service.find_channels("BPM in sector 1")
# Should only return BPMs from sector 1
```

## Extending the Implementation

### Custom Tools

You can extend the agent with custom tools:

```python
from pydantic_ai import Tool

def get_device_status(system: str, family: str, device: int) -> str:
    """Custom tool to get device status."""
    # Your implementation
    pass

# In your custom pipeline subclass:
self.agent = Agent(
    tools=[
        # ... existing tools ...
        Tool(get_device_status, takes_ctx=False),
    ]
)
```

### Custom Database Backend

You can create a custom database that fetches from a live system:

```python
class LiveMMLDatabase(MiddleLayerDatabase):
    """Fetch MML data from live control system."""

    def load_database(self):
        # Fetch from your control system API
        self.data = fetch_from_control_system()
        self.channel_map = self._build_channel_map()
```

## Migration from ALS Production

If you're migrating from the ALS assistant production system:

1. **Database conversion:**
   - Export AO data from MongoDB
   - Transform to JSON format: `System → Family → Field → ChannelNames`
   - Include setup.DeviceList for filtering

2. **Configuration:**
   - Set `pipeline_mode: "middle_layer"`
   - Point to your JSON database file
   - Configure the channel_finder model

3. **Testing:**
   - Use existing test queries from production
   - Verify filtering works correctly
   - Check agent tool usage patterns

## Performance Considerations

- **LLM Calls:** Typically 4-10 calls per query (split + agent tool calls)
- **Database Size:** Works well up to ~10,000 channels
- **Filtering:** Filtering happens in-memory after retrieval (fast)
- **Caching:** Consider caching database in memory for repeated queries

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Agent can't find PVs | Check ChannelNames nesting, verify field names |
| Filtering errors | Ensure DeviceList exists and matches ChannelNames length |
| Wrong families explored | Add CommonNames, improve field naming consistency |
| Slow queries | Reduce database size, check LLM call patterns |

## Files Created

```
osprey/
├── src/osprey/templates/apps/control_assistant/services/channel_finder/
│   ├── databases/
│   │   ├── middle_layer.py          # Database implementation
│   │   └── __init__.py              # Updated exports
│   ├── pipelines/
│   │   └── middle_layer/
│   │       ├── __init__.py          # Pipeline exports
│   │       └── pipeline.py          # Pipeline implementation
│   └── service.py                   # Updated with middle_layer support
├── src/osprey/templates/project/
│   ├── data/channel_databases/
│   │   └── middle_layer.json        # Sample database
│   └── docs/tutorials/
│       ├── middle_layer_pipeline.md # User guide
│       └── MIDDLE_LAYER_PIPELINE_GUIDE.md  # This file
└── tests/services/channel_finder/
    └── test_middle_layer_pipeline.py   # Database tests
```

## Next Steps

1. **Try it out:**
   ```bash
   cd osprey
   python -m pytest tests/services/channel_finder/test_middle_layer_pipeline.py
   ```

2. **Create your database:**
   - Copy `middle_layer.json` as template
   - Add your systems, families, and PVs
   - Include setup metadata for filtering

3. **Test queries:**
   - Start with simple: "beam current"
   - Add complexity: "BPM X positions in sector 1"
   - Verify agent behavior

4. **Integrate:**
   - Update your `config.yml`
   - Deploy to your application
   - Monitor agent tool usage

## Support

For questions or issues:
- Check the documentation: `docs/tutorials/middle_layer_pipeline.md`
- Review tests: `tests/services/channel_finder/test_middle_layer_pipeline.py`
- See examples: `data/channel_databases/middle_layer.json`

