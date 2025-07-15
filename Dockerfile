FROM python:3.10-slim

# Install Poetry
RUN pip install poetry

# Set working directory
WORKDIR /pilottai

# Copy and install dependencies
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root

# Copy source code
COPY . .

# Install the framework itself
RUN poetry install

# Default command shows the version
CMD ["python", "-c", "import pilottai; print(pilottai.__version__)"]
