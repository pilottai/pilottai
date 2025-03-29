import pandas as pd
import numpy as np
from typing import Any, Dict, List, Optional
from datetime import datetime
import io

from pilott.knowledge.source.base_input import BaseInputSource


class StructuredInput(BaseInputSource):
    """
    Input source for processing structured data like CSV, Excel, or database tables.
    Converts structured data into a text representation for knowledge extraction.
    """

    def __init__(
        self,
        name: str,
        data: Optional[Any] = None,
        file_path: Optional[str] = None,
        file_content: Optional[bytes] = None,
        format: str = "csv",  # csv, excel, pandas, dict
        include_headers: bool = True,
        include_statistics: bool = True,
        max_rows: Optional[int] = None,
        column_filters: Optional[List[str]] = None,
        table_description: Optional[str] = None,
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.data = data
        self.file_path = file_path
        self.file_content = file_content
        self.format = format.lower()
        self.include_headers = include_headers
        self.include_statistics = include_statistics
        self.max_rows = max_rows
        self.column_filters = column_filters
        self.table_description = table_description

        # Storage
        self.text_content = None
        self.dataframe = None
        self.column_stats = None

    async def connect(self) -> bool:
        """Load the structured data into a pandas DataFrame"""
        try:
            # If data is already a DataFrame
            if isinstance(self.data, pd.DataFrame):
                self.dataframe = self.data
                self.is_connected = True
                return True

            # If data is a dict or list
            if isinstance(self.data, (dict, list)):
                self.dataframe = pd.DataFrame(self.data)
                self.is_connected = True
                return True

            # Handle file content
            if self.file_content is not None:
                if self.format == "csv":
                    self.dataframe = pd.read_csv(io.BytesIO(self.file_content))
                elif self.format == "excel":
                    self.dataframe = pd.read_excel(io.BytesIO(self.file_content))
                else:
                    raise ValueError(f"Unsupported format for binary content: {self.format}")

                self.is_connected = True
                return True

            # Handle file path
            if self.file_path:
                if not await self._check_file_access():
                    return False

                if self.format == "csv":
                    self.dataframe = pd.read_csv(self.file_path)
                elif self.format == "excel":
                    self.dataframe = pd.read_excel(self.file_path)
                else:
                    raise ValueError(f"Unsupported file format: {self.format}")

                self.is_connected = True
                return True

            self.logger.error("No data source provided")
            self.is_connected = False
            return False

        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            self.is_connected = False
            return False

    async def _check_file_access(self) -> bool:
        """Check if file is accessible"""
        import os

        if not os.path.exists(self.file_path):
            self.logger.error(f"File not found: {self.file_path}")
            return False

        if not os.access(self.file_path, os.R_OK):
            self.logger.error(f"File not readable: {self.file_path}")
            return False

        return True

    async def query(self, query: str) -> Any:
        """Query the structured data"""
        if not self.is_connected or self.dataframe is None:
            if not await self.connect():
                raise ValueError("Could not connect to data source")

        self.access_count += 1
        self.last_access = datetime.now()

        # Check if query looks like a SQL-like query
        if "select" in query.lower() and "from" in query.lower():
            return await self._execute_sql_like_query(query)

        # Check if query looks like a column reference
        if query in self.dataframe.columns:
            return self._get_column_info(query)

        # Default to text search
        return await self._search_in_data(query)

    async def _execute_sql_like_query(self, query: str) -> Dict[str, Any]:
        """Execute a SQL-like query on the DataFrame"""
        try:
            # This is a basic implementation that handles simple queries
            # For a full SQL implementation, consider using libraries like pandasql

            # Parse the query (very simplified)
            query = query.lower()

            # Extract requested columns
            if "select * from" in query:
                columns = list(self.dataframe.columns)
            else:
                select_part = query.split("from")[0].replace("select", "").strip()
                columns = [col.strip() for col in select_part.split(",")]

            # Extract where condition if present
            if "where" in query:
                where_part = query.split("where")[1].strip()
                # Very simplified condition handling - only handles single equality
                if "=" in where_part:
                    parts = where_part.split("=")
                    column = parts[0].strip()
                    value = parts[1].strip().strip("'").strip('"')

                    filtered_df = self.dataframe[self.dataframe[column] == value]
                else:
                    filtered_df = self.dataframe
            else:
                filtered_df = self.dataframe

            # Extract limit if present
            if "limit" in query:
                limit_part = query.split("limit")[1].strip()
                try:
                    limit = int(limit_part)
                    filtered_df = filtered_df.head(limit)
                except ValueError:
                    pass

            # Select only requested columns
            if columns[0] != "*":
                try:
                    result_df = filtered_df[columns]
                except KeyError:
                    # Handle nonexistent columns
                    valid_columns = [col for col in columns if col in filtered_df.columns]
                    result_df = filtered_df[valid_columns] if valid_columns else filtered_df
            else:
                result_df = filtered_df

            return {
                "data": result_df.to_dict(orient="records"),
                "columns": list(result_df.columns),
                "row_count": len(result_df)
            }

        except Exception as e:
            self.logger.error(f"Error executing SQL-like query: {str(e)}")
            return {
                "error": str(e),
                "query": query
            }

    def _get_column_info(self, column_name: str) -> Dict[str, Any]:
        """Get information about a specific column"""
        if column_name not in self.dataframe.columns:
            return {"error": f"Column '{column_name}' not found"}

        column_data = self.dataframe[column_name]

        # Get basic stats
        try:
            stats = {
                "count": len(column_data),
                "non_null": column_data.count(),
                "null_count": column_data.isna().sum(),
                "dtype": str(column_data.dtype)
            }

            # Add numeric stats if applicable
            if np.issubdtype(column_data.dtype, np.number):
                stats.update({
                    "min": column_data.min(),
                    "max": column_data.max(),
                    "mean": column_data.mean(),
                    "median": column_data.median(),
                    "std": column_data.std()
                })

            # Add string stats if applicable
            elif column_data.dtype == object:
                # Check if values are strings
                if column_data.dropna().apply(lambda x: isinstance(x, str)).all():
                    stats.update({
                        "min_length": column_data.str.len().min(),
                        "max_length": column_data.str.len().max(),
                        "avg_length": column_data.str.len().mean()
                    })

            # Add sample values
            stats["sample_values"] = column_data.dropna().sample(
                min(5, len(column_data.dropna()))
            ).tolist()

            return {
                "column": column_name,
                "stats": stats
            }

        except Exception as e:
            return {
                "column": column_name,
                "error": str(e)
            }

    async def _search_in_data(self, query: str) -> List[Dict[str, Any]]:
        """Search for a string in the data"""
        results = []

        # Convert data to strings for searching
        string_df = self.dataframe.astype(str)

        # Search in each column
        for column in string_df.columns:
            # Find rows where the column contains the query
            matching_rows = string_df[string_df[column].str.contains(query, case=False, na=False)]

            for index, row in matching_rows.iterrows():
                results.append({
                    "column": column,
                    "row_index": index,
                    "matched_value": row[column],
                    "row_data": row.to_dict()
                })

        return results

    async def validate_content(self) -> bool:
        """Validate that data can be loaded and processed"""
        if not self.is_connected:
            if not await self.connect():
                return False

        return self.dataframe is not None and not self.dataframe.empty

    async def _process_content(self) -> None:
        """Process structured data into text representation"""
        if not self.is_connected or self.dataframe is None:
            if not await self.connect():
                return

        # Apply column filters if specified
        df = self.dataframe
        if self.column_filters:
            available_columns = [col for col in self.column_filters if col in df.columns]
            df = df[available_columns] if available_columns else df

        # Apply row limit if specified
        if self.max_rows and len(df) > self.max_rows:
            df = df.head(self.max_rows)

        text_parts = []

        # Add table description if available
        if self.table_description:
            text_parts.append(f"# {self.name} - {self.table_description}")
        else:
            text_parts.append(f"# {self.name}")

        # Add metadata
        text_parts.append(f"Rows: {len(df)}")
        text_parts.append(f"Columns: {len(df.columns)}")

        # Add column info
        if self.include_headers:
            column_info = []
            for column in df.columns:
                dtype = str(df[column].dtype)
                column_info.append(f"{column} ({dtype})")
            text_parts.append("Columns: " + ", ".join(column_info))

        # Calculate statistics
        if self.include_statistics:
            self.column_stats = {}
            stats_text = []

            for column in df.columns:
                stats = {"name": column, "dtype": str(df[column].dtype)}

                # Basic stats for all columns
                stats["null_count"] = int(df[column].isna().sum())
                stats["non_null_count"] = int(df[column].count())

                # Numeric column stats
                if pd.api.types.is_numeric_dtype(df[column]):
                    stats.update({
                        "min": float(df[column].min()) if not df[column].isna().all() else None,
                        "max": float(df[column].max()) if not df[column].isna().all() else None,
                        "mean": float(df[column].mean()) if not df[column].isna().all() else None,
                        "median": float(df[column].median()) if not df[column].isna().all() else None
                    })

                    stats_text.append(
                        f"{column}: min={stats['min']}, max={stats['max']}, "
                        f"mean={stats['mean']:.2f}, median={stats['median']:.2f}, "
                        f"null={stats['null_count']}"
                    )

                # String column stats
                elif pd.api.types.is_string_dtype(df[column]) or df[column].dtype == object:
                    if not df[column].isna().all():
                        # Get value counts for top values
                        value_counts = df[column].value_counts().head(3)
                        top_values = [f"{val} ({count})" for val, count in value_counts.items()]
                        stats["top_values"] = top_values

                        stats_text.append(
                            f"{column}: top values=[{', '.join(top_values)}], "
                            f"null={stats['null_count']}"
                        )
                    else:
                        stats_text.append(f"{column}: all null values")

                # Date column stats
                elif pd.api.types.is_datetime64_dtype(df[column]):
                    if not df[column].isna().all():
                        stats.update({
                            "min": df[column].min().isoformat(),
                            "max": df[column].max().isoformat()
                        })

                        stats_text.append(
                            f"{column}: min={stats['min']}, max={stats['max']}, "
                            f"null={stats['null_count']}"
                        )
                    else:
                        stats_text.append(f"{column}: all null values")

                # Boolean column stats
                elif pd.api.types.is_bool_dtype(df[column]):
                    if not df[column].isna().all():
                        true_count = int(df[column].sum())
                        false_count = int((~df[column]).sum())
                        stats.update({
                            "true_count": true_count,
                            "false_count": false_count
                        })

                        stats_text.append(
                            f"{column}: true={true_count}, false={false_count}, "
                            f"null={stats['null_count']}"
                        )
                    else:
                        stats_text.append(f"{column}: all null values")

                self.column_stats[column] = stats

            text_parts.append("\n## Statistics:")
            text_parts.extend(stats_text)

        # Format data as text table
        text_parts.append("\n## Data:")

        # Convert DataFrame to a text table
        if self.format == "csv":
            buffer = io.StringIO()
            df.to_csv(buffer, index=False)
            text_parts.append(buffer.getvalue())
        else:
            # Use a more readable format for other types
            text_parts.append(df.to_string(index=False))

        self.text_content = "\n\n".join(text_parts)
        self.chunks = self._chunk_text(self.text_content)

        source_desc = self.file_path if self.file_path else "structured data"
        self.logger.info(f"Created {len(self.chunks)} chunks from {source_desc}")
