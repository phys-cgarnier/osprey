# Osprey Framework - Latest Release (v0.9.0)

🎉 **Major Feature Release** - Control Assistant Template, Comprehensive Tutorials, and Control Systems Integration

## What's New in v0.9.0

### 🚀 Major New Features

**Control System Connectors:**
- Two-layer pluggable abstraction for control systems and archivers
- **MockConnector**: Development/R&D mode - works with any PV names, no hardware required
- **EPICSConnector**: Production EPICS Channel Access with gateway support (requires `pyepics`)
- **MockArchiverConnector**: Generates synthetic historical time series data
- **EPICSArchiverConnector**: EPICS Archiver Appliance integration (requires `archivertools`)
- **ConnectorFactory**: Centralized creation with automatic registration via registry system
- **Pattern Detection**: Config-based regex patterns for detecting control system operations in generated code
- **Plugin Architecture**: Custom connectors (LabVIEW, Tango, etc.) via `ConnectorRegistration`
- Seamless switching between mock and production via config.yml `type` field

**Control Assistant Template:**
- Production-ready template for accelerator control applications
- Complete multi-capability system with PV value retrieval, archiver integration, and Channel Finder
- Dual-mode support (mock for R&D, production for control room)
- 4-part tutorial series (setup, Channel Finder integration, production deployment, customization)
- Python execution service with read/write container separation and approval workflows

**Prompt Customization System:**
- Flexible inheritance for domain-specific prompt builders
- Added `include_default_examples` parameter to `DefaultTaskExtractionPromptBuilder`
- Applications can now choose to extend or replace framework examples
- Exported `TaskExtractionExample` and `ExtractedTask` from `osprey.prompts.defaults` for custom builders
- Weather template includes 8 domain-specific examples for conversational context handling

**Conceptual Tutorial:**
- New comprehensive tutorial introducing Osprey's core concepts and design patterns
- Explains Osprey's foundation on LangGraph with link to upstream framework
- Compares ReAct vs Planning agents with clear advantages/disadvantages
- Introduces capabilities and contexts with architectural motivation
- Walks through designing a weather assistant as practical example
- Step-by-step orchestration examples showing how capabilities chain together
- Location: `docs/source/getting-started/conceptual-tutorial.rst`

**Domain Adaptation Tutorial:**
- Comprehensive Step 5 in hello-world tutorial
- Explains why domain-specific examples improve conversational AI
- 8 weather-specific task extraction examples covering location carry-forward, temporal references, etc.
- Shows complete implementation with code examples and explanations

### 🔧 API Changes

**FrameworkPromptProviderRegistration API Simplification:**
- Removed `application_name` parameter (no longer used by framework)
- Removed `description` parameter (no longer used by framework)
- Framework now uses `module_path` as the provider key
- **Backward Compatible**: Old parameters still accepted with deprecation warnings until v0.10

### 🗑️ Deprecations

**FrameworkPromptProviderRegistration fields:**
- `application_name` and `description` parameters are now deprecated
- Will be removed in v0.10
- Migration: Simply remove these parameters from your `FrameworkPromptProviderRegistration` calls

### ✂️ Removed Features

**Migration Guides:**
- Removed version-specific migration documentation (v0.6→v0.8, v0.7→v0.8)
- Superseded by conceptual tutorial which provides better onboarding
- Historical information still available in git history if needed

**Wind Turbine Template:**
- Removed deprecated wind turbine application template
- Replaced by Control Assistant template with better real-world applicability

### 📝 Documentation Improvements

**Hello World Tutorial:**
- Simplified and improved tutorial UX
- Removed unnecessary container deployment steps
- Added "Ready to Dive In?" admonition for quick starters
- Added comprehensive API key dropdown matching Control Assistant format
- Simplified prerequisites and streamlined setup

**Hello World Weather Template:**
- Simplified template to match minimal tutorial scope
- Removed container runtime configuration
- Removed safety controls and execution infrastructure
- Template system now conditionally generates config sections based on template type

**Channel Finder Presentation Mode:**
- Renamed `presentation_mode` value from "compact" to "template"
- Updated all config files, documentation, and database implementations

**Environment Template:**
- Updated `env.example` with clearer API key guidance
- Fixed typo: `ANTHROPIC_API_KEY_o` → `ANTHROPIC_API_KEY`

## Upgrading from v0.8.5

**Mostly backward compatible.** This release adds significant new features while maintaining compatibility with existing applications.

### Action Required

If you use `FrameworkPromptProviderRegistration`:
- Remove `application_name` and `description` parameters to avoid deprecation warnings
- These parameters will be removed in v0.10

### New Capabilities Available

1. **Control System Integration**: If you're building control system applications, check out the new Control Assistant template
2. **Prompt Customization**: You can now customize task extraction prompts for your domain
3. **Conceptual Tutorial**: Start with `docs/source/getting-started/conceptual-tutorial.rst` for a comprehensive introduction

## Installation

```bash
pip install --upgrade osprey-framework
```

## Getting Started

```bash
# Interactive setup
osprey

# Or create a new project directly
osprey init my-project --template hello_world_weather

# For control system applications
osprey init my-control-assistant --template control_assistant
```

## Full Changelog

See [CHANGELOG.md](https://github.com/als-apg/osprey/blob/main/CHANGELOG.md) for the complete list of changes.

## Documentation

- 📚 [Full Documentation](https://als-apg.github.io/osprey)
- 🎓 [Conceptual Tutorial](https://als-apg.github.io/osprey/getting-started/conceptual-tutorial.html)
- 🏃 [Quick Start Tutorial](https://als-apg.github.io/osprey/getting-started/hello-world-tutorial.html)
- 🎛️ [Control Assistant Tutorial](https://als-apg.github.io/osprey/getting-started/control-assistant-tutorial-part1.html)
- 📖 [API Reference](https://als-apg.github.io/osprey/api_reference/index.html)

## Links

- 🐙 [GitHub Repository](https://github.com/als-apg/osprey)
- 📦 [PyPI Package](https://pypi.org/project/osprey-framework/)
- 📄 [Research Paper](https://arxiv.org/abs/2508.15066)
- 🐛 [Report Issues](https://github.com/als-apg/osprey/issues)
