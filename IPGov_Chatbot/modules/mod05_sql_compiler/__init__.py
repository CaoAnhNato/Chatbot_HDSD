"""
Module: IPGov_Chatbot/modules/mod05_sql_compiler/__init__.py
Chức năng: Public package re-exports cho Module 05 Text-to-SQL Compiler & Scatter-Gather Engine.
"""

from IPGov_Chatbot.modules.mod05_sql_compiler.ast_validator import (
    clean_sql_string,
    invariant_sql_validator,
    validate_ast_syntax,
    validate_data_contracts,
    validate_schema_grounding,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.archetype_patterns import (
    ArchetypePatternCatalog,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.compiler_facade import (
    SQLCompilerFacade,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.db_dry_run import (
    DatabaseDryRunner,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.error_cache_service import (
    RedisSQLErrorCache,
    map_postgres_error_to_constraint,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.prompt_templates import (
    STATIC_INVARIANT_PREFIX_PROMPT,
    build_3tier_text_to_sql_prompt,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.scatter_gather_dispatcher import (
    ScatterGatherDispatcher,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.track_a_compiler import (
    TrackACompiler,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.track_b_generator import (
    TrackBGenerator,
)
from IPGov_Chatbot.schemas.sql_compiler_schema import (
    GeneratedSQLDTO,
    MetricFilter,
    MetricSpecDTO,
    SQLExecutionMode,
    SubqueryTaskItem,
    TextToSQLStructuredOutput,
)

__all__ = [
    "SQLCompilerFacade",
    "TrackACompiler",
    "TrackBGenerator",
    "DatabaseDryRunner",
    "RedisSQLErrorCache",
    "ScatterGatherDispatcher",
    "ArchetypePatternCatalog",
    "STATIC_INVARIANT_PREFIX_PROMPT",
    "build_3tier_text_to_sql_prompt",
    "clean_sql_string",
    "validate_ast_syntax",
    "validate_schema_grounding",
    "validate_data_contracts",
    "invariant_sql_validator",
    "map_postgres_error_to_constraint",
    "TextToSQLStructuredOutput",
    "GeneratedSQLDTO",
    "SQLExecutionMode",
    "SubqueryTaskItem",
    "MetricFilter",
    "MetricSpecDTO",
]
