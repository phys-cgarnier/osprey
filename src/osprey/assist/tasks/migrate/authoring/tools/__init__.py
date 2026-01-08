# OSPREY Migration Tools
#
# This module provides tooling for generating, auditing, and applying
# migration documents for downstream facility implementations.
#
# Usage:
#   python -m osprey.assist.tasks.migrate.authoring.tools.migrate generate --from 0.9.5 --to 0.9.6
#   python -m osprey.assist.tasks.migrate.authoring.tools.migrate audit v0.9.6.yml
#   python -m osprey.assist.tasks.migrate.authoring.tools.migrate validate v0.9.6.yml
#   python -m osprey.assist.tasks.migrate.authoring.tools.migrate apply v0.9.6.yml --target /path/to/facility

__version__ = "0.1.0"
