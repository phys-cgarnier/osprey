# Middle Layer React Agent Pipeline

The middle_layer pipeline provides a React-style agent that explores a functional hierarchy database using query tools. This approach is based on the MATLAB Middle Layer (MML) pattern used in production accelerator control systems.

## Overview

Unlike the hierarchical pipeline which navigates a tree structure, the middle_layer pipeline uses an agent with database query tools to:
1. Explore available systems, families, and fields
2. Retrieve actual PV addresses from the database
3. Filter results by device/sector when needed

This pattern is ideal when:
- Your control system is organized by **function** (Monitor, Setpoint) rather than naming pattern
- PV names don't follow a strict hierarchical naming convention
- You want the agent to dynamically explore the database structure

## Database Structure

The middle layer database follows this functional hierarchy:

```
System (e.g., SR, BR, BTS)
  ├─ Family (e.g., BPM, HCM, VCM, DCCT)
      ├─ Field (e.g., Monitor, Setpoint)
          ├─ [Optional] Subfield (e.g., X, Y, Frequency, Voltage)
              └─ ChannelNames: ["PV1", "PV2", ...]
          └─ setup: {CommonNames: [...], DeviceList: [[sector, device], ...]}
```

### Example Database

```json
{
  "SR": {
    "BPM": {
      "Monitor": {
        "ChannelNames": ["SR01C:BPM1:X", "SR01C:BPM1:Y", ...]
      },
      "Setpoint": {
        "X": {
          "ChannelNames": ["SR01C:BPM1:XSet", ...]
        },
        "Y": {
          "ChannelNames": ["SR01C:BPM1:YSet", ...]
        }
      },
      "setup": {
        "CommonNames": ["BPM 1", "BPM 2"],
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

## Configuration

Add to your `config.yml`:

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
    model_id: gpt-4
    temperature: 0
```

## Available Tools

The agent has access to these database query tools:

### 1. `list_systems()`
Get all available systems.

**Returns:** `["SR", "BR", "BTS"]`

### 2. `list_families(system: str)`
Get families in a system.

**Example:** `list_families("SR")` → `["BPM", "HCM", "VCM", "DCCT"]`

### 3. `inspect_fields(system: str, family: str, field: str = None)`
Inspect field structure.

**Example:**
- `inspect_fields("SR", "BPM")` → `{"Monitor": "ChannelNames", "Setpoint": "dict (has subfields)"}`
- `inspect_fields("SR", "BPM", "Setpoint")` → `{"X": "ChannelNames", "Y": "ChannelNames"}`

### 4. `list_channel_names(system, family, field, subfield=None, sectors=None, devices=None)`
Retrieve PV addresses.

**Examples:**
- `list_channel_names("SR", "BPM", "Monitor")` → All BPM monitor PVs
- `list_channel_names("SR", "BPM", "Setpoint", subfield="X")` → BPM X setpoint PVs
- `list_channel_names("SR", "BPM", "Monitor", sectors=[1])` → BPM monitors in sector 1 only
- `list_channel_names("SR", "BPM", "Monitor", devices=[1])` → BPM monitors for device 1 only

### 5. `get_common_names(system: str, family: str)`
Get friendly device names.

**Example:** `get_common_names("SR", "BPM")` → `["BPM 1", "BPM 2", ...]`

## Usage Example

```python
from osprey.templates.apps.control_assistant.services.channel_finder import ChannelFinderService

# Initialize service
service = ChannelFinderService()

# Query examples
result = await service.find_channels("What is the beam current PV?")
# Agent will:
# 1. list_systems() → find "SR", "BR", "BTS"
# 2. list_families("SR") → find "DCCT"
# 3. inspect_fields("SR", "DCCT") → find "Monitor"
# 4. list_channel_names("SR", "DCCT", "Monitor") → return ["SR:DCCT:Current"]

result = await service.find_channels("Find BPM X positions for sector 1")
# Agent will:
# 1. Identify BPM family
# 2. Find Monitor or Setpoint fields (depending on query context)
# 3. Use sectors=[1] filter to get only sector 1 devices
```

## Common Query Patterns

| Query | Agent Strategy |
|-------|----------------|
| "beam current" | DCCT family, Monitor field |
| "BPM positions" | BPM family, Monitor field, may explore X/Y subfields |
| "horizontal corrector setpoints" | HCM family, Setpoint field |
| "RF frequency readback" | RF family, Monitor field, Frequency subfield |
| "BPM 1 readback" | BPM family, filter devices=[1] |
| "sector 2 correctors" | Corrector families, filter sectors=[2] |

## Device/Sector Filtering

The `DeviceList` in setup metadata enables filtering:

```json
{
  "setup": {
    "CommonNames": ["BPM 1-1", "BPM 1-2", "BPM 2-1", "BPM 2-2"],
    "DeviceList": [[1, 1], [1, 2], [2, 1], [2, 2]]
  }
}
```

Each `[sector, device]` pair maps to the corresponding index in ChannelNames. The agent can filter by:
- **Sectors:** `sectors=[1]` → Only devices in sector 1
- **Devices:** `devices=[1]` → Only device number 1 across all sectors
- **Both:** `sectors=[1], devices=[1]` → Specific device in specific sector

## Comparison with Other Pipelines

### vs. Hierarchical Pipeline
- **Hierarchical:** Navigates tree structure, builds PV names from selections
- **Middle Layer:** Queries database with tools, retrieves pre-existing PV names
- **Use Hierarchical when:** PVs follow strict naming pattern (e.g., `{system}-{subsystem}:{device}_{signal}`)
- **Use Middle Layer when:** PVs don't follow patterns, organization is functional

### vs. In-Context Pipeline
- **In-Context:** Puts entire database in LLM context, semantic search
- **Middle Layer:** Agent explores database dynamically with tools
- **Use In-Context when:** Small database (<100 channels), simple queries
- **Use Middle Layer when:** Large database, complex queries, need filtering

## Best Practices

1. **Organize by function**: Group by what devices do (Monitor, Setpoint) not by name patterns
2. **Use subfields wisely**: For multi-dimensional data (X/Y positions, different signal types)
3. **Include setup metadata**: CommonNames and DeviceList enable better querying
4. **Keep field names standard**: Use consistent names across families (Monitor, Setpoint, etc.)
5. **Leverage filtering**: Use DeviceList for sector/device filtering when queries specify devices

## Creating Your Own Database

1. **Identify your hierarchy:**
   - Systems: Major control system sections (e.g., SR, BR, Linac)
   - Families: Device types (e.g., BPM, Correctors, RF)
   - Fields: Functions (e.g., Monitor, Setpoint, Status)
   - Subfields: Multi-dimensional data (e.g., X/Y, different signal types)

2. **Structure your JSON:**
```json
{
  "YOUR_SYSTEM": {
    "YOUR_FAMILY": {
      "Monitor": {
        "ChannelNames": ["PV1", "PV2", ...]
      },
      "setup": {
        "CommonNames": ["Device 1", "Device 2"],
        "DeviceList": [[1, 1], [1, 2]]
      }
    }
  }
}
```

3. **Test with queries:**
   - Start with simple queries: "beam current", "BPM positions"
   - Add complexity: "BPM 1 X position", "sector 2 correctors"
   - Verify agent strategy matches expectations

## Troubleshooting

**Q: Agent can't find PVs that exist in the database**
- Check that ChannelNames are at the correct nesting level
- Verify setup metadata exists for families with filtering
- Ensure no typos in field/subfield names

**Q: Filtering by sector/device returns errors**
- Ensure DeviceList exists in setup
- Check that DeviceList length matches ChannelNames length
- Verify DeviceList format: `[[sector, device], ...]`

**Q: Agent explores wrong families/fields**
- Add more descriptive CommonNames in setup
- Use consistent field names across families
- Consider adding facility description in config for context

## Next Steps

- See `examples/middle_layer_queries.py` for more query examples
- Check `tests/services/channel_finder/test_middle_layer_pipeline.py` for implementation details
- Explore extending with custom tools for your facility's needs

