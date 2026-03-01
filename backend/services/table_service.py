import re
import logging
import decimal
import pandas as pd
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from services.ollama_service import generate_response_sync

logger = logging.getLogger(__name__)


def preprocess_and_store_table(
    df: pd.DataFrame,
    table_name: str,
    db: Session,
    is_spreadsheet: bool = False
) -> str:
    """Preprocess a DataFrame and store it in PostgreSQL."""
    # Check if headers are missing (Docling sometimes returns default integer columns)
    # If columns are ['0', '1', '2'...] then the first row might be the header
    is_default_cols = all(str(col).isdigit() for col in df.columns)
    
    if is_default_cols and not df.empty:
        # Promote first row to headers
        new_header = df.iloc[0]
        df = df[1:].copy()  # Use .copy() to avoid SettingWithCopyWarning
        df.columns = new_header
        logger.info(f"Promoted first row to headers for table {table_name}")

    # Sanitize column names: Lowercase, replace spaces/hyphens with underscores, remove non-alphanumeric
    def sanitize_col(col):
        col = str(col).lower().strip()
        col = col.replace(" ", "_").replace("-", "_")
        col = re.sub(r'[^a-z0-9_]', '', col)
        if not col or col == 'nan':
            return 'column'
        return col

    df.columns = [sanitize_col(col) for col in df.columns]
    
    # Handle duplicate columns by appending _1, _2 etc.
    cols = []
    counts = {}
    for col in df.columns:
        if col in counts:
            counts[col] += 1
            cols.append(f"{col}_{counts[col]}")
        else:
            counts[col] = 0
            cols.append(col)
    df.columns = cols

    # Dynamic numeric conversion and cleaning
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]):
            # Strip spaces
            cleaned = df[col].astype(str).str.strip()
            
            # Remove all characters except digits, minus sign, and decimal point
            cleaned = cleaned.str.replace(r'[^\d\.-]', '', regex=True)
            
            # Handle (123) as -123
            mask_paren = cleaned.str.startswith('(') & cleaned.str.endswith(')')
            cleaned.loc[mask_paren] = "-" + cleaned.loc[mask_paren].str[1:-1]
            
            # Convert to numeric
            numeric_col = pd.to_numeric(cleaned, errors='coerce')
            
            # Keep as numeric if more than 50% valid
            if numeric_col.notna().sum() > (len(df) * 0.5):
                df[col] = numeric_col
                logger.info(f"Converted column '{col}' to numeric")
            else:
                # Fallback to string cleaning
                df[col] = df[col].astype(str).str.lower().str.strip().str.replace(" ", "_")

    # Create table in PostgreSQL
    from sqlalchemy import create_engine
    from config import DATABASE_URL
    engine = create_engine(DATABASE_URL)

    # Store the table
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    logger.info(f"Stored table '{table_name}' with {len(df)} rows and columns: {list(df.columns)}")

    return table_name


def to_serializable_dict(row_mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Convert RowMapping to a dictionary with JSON-serializable types."""
    serializable_row = {}
    for key, value in row_mapping.items():
        if isinstance(value, decimal.Decimal):
            serializable_row[key] = float(value)
        elif isinstance(value, (decimal.Decimal, float, int)):
            # Handle possible NaNs or other types if needed, but Decimal is the main culprit
            serializable_row[key] = value
        else:
            serializable_row[key] = value
    return serializable_row


def get_table_schema(table_name: str, db: Session) -> Dict[str, Any]:
    """Get schema and sample rows for a table."""
    try:
        db.rollback()
        result = db.execute(text(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = :table_name
            ORDER BY ordinal_position
        """), {"table_name": table_name})
        columns = [{"name": row[0], "type": row[1]} for row in result]

        sample_result = db.execute(text(f'SELECT * FROM "{table_name}" LIMIT 5'))
        sample_rows = [to_serializable_dict(dict(row._mapping)) for row in sample_result]

        return {
            "table_name": table_name,
            "columns": columns,
            "sample_rows": sample_rows
        }
    except Exception as e:
        logger.error(f"Error getting table schema for {table_name}: {e}")
        db.rollback()
        return {"table_name": table_name, "columns": [], "sample_rows": []}


async def generate_sql(
    table_schemas: List[Dict],
    user_query: str
) -> str:
    """Use LLM to generate SQL query from table schema and user question."""
    schema_text = ""
    for schema in table_schemas:
        cols = ", ".join([f"{col['name']} ({col['type']})" for col in schema["columns"]])
        sample_rows = schema.get("sample_rows", [])
        sample_text = ""
        if sample_rows:
            sample_text = f"\nSample rows: {sample_rows[:2]}"
        schema_text += f"\nTable: {schema['table_name']}\nColumns: {cols}{sample_text}\n"

    logger.debug(f"Schema text for SQL generation: {schema_text}")

    messages = [
        {
            "role": "system",
            "content": """You are a PostgreSQL SQL expert. Generate a valid PostgreSQL SQL query based on the user's question and the provided table schema.

RULES:
- Return ONLY the SQL query, no explanations or markdown formatting.
- Use DOUBLE QUOTES (") around all table names and column names (e.g., "table_name"."column_name").
- Use SINGLE QUOTES (') ONLY for string literals/values in WHERE clauses (e.g., WHERE "status" = 'active').
- NEVER use single quotes for identifiers like column names or table names.
- All string values used in WHERE clauses comparison should be lowercase with underscores instead of spaces.
- Use proper PostgreSQL syntax.
- Do NOT use LIMIT unless asked.
- Be precise and match column names exactly as shown in the schema.
- IMPORTANT: When performing calculations (SUM, AVG, division), do NOT cast numeric results to TEXT. Perform all math on numeric types first. Only cast to TEXT at the very end if absolutely necessary for formatting a specific string output, but generally keep data as numeric for further processing."""
        },
        {
            "role": "user",
            "content": f"Table schema:\n{schema_text}\n\nQuestion: {user_query}"
        }
    ]

    sql = await generate_response_sync(messages)
    sql = sql.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    
    # Post-processing to fix common quoting issues with Ollama models
    # If the model used 'column_name' instead of "column_name", we try to fix it.
    for schema in table_schemas:
        t_name = schema["table_name"]
        # Fix table name if single quoted
        sql = sql.replace(f"'{t_name}'", f'"{t_name}"')
        for col in schema["columns"]:
            c_name = col["name"]
            # Fix column name if single quoted
            sql = sql.replace(f"'{c_name}'", f'"{c_name}"')
    
    logger.info(f"Generated SQL: {sql}")
    return sql


def execute_sql(sql: str, db: Session) -> Dict[str, Any]:
    """Execute SQL query and return results."""
    try:
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            return {"error": "Only SELECT queries are allowed", "data": []}

        result = db.execute(text(sql))
        columns = list(result.keys())
        rows = [to_serializable_dict(dict(row._mapping)) for row in result]

        logger.info(f"SQL executed successfully. Returned {len(rows)} rows.")

        return {
            "columns": columns,
            "data": rows,
            "row_count": len(rows),
            "sql": sql
        }
    except Exception as e:
        logger.error(f"SQL execution error: {e}")
        db.rollback()
        return {"error": str(e), "data": [], "sql": sql}


def drop_tables(table_names: List[str], db: Session):
    """Drop dynamic tables from PostgreSQL."""
    for table_name in table_names:
        try:
            db.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
            db.commit()
            logger.info(f"Dropped table: {table_name}")
        except Exception as e:
            logger.error(f"Error dropping table {table_name}: {e}")
            db.rollback()