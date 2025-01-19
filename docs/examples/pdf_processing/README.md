# PDF Processing Pipeline Example

This example demonstrates how to build a hierarchical agent system using Pilott to process PDF documents. It showcases key features of the framework including agent orchestration, task delegation, and tool integration.

## Overview

The system consists of three specialized agents working together in a pipeline:

1. **Manager Agent**: Orchestrates the workflow and delegates tasks
2. **Extractor Agent**: Extracts content from PDF files
3. **Evaluator Agent**: Validates the extracted content format

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Manager   │ -> │  Extractor  │ -> │  Evaluator  │
│    Agent    │ <- │    Agent    │ <- │    Agent    │
└─────────────┘    └─────────────┘    └─────────────┘
```

## Features

- Hierarchical agent organization
- Asynchronous task processing
- PDF content extraction using PyPDF
- JSON validation
- Error handling and logging
- Task status monitoring

## Prerequisites

```bash
pip install pilott pypdf
```

## Usage

1. Import required components:
```python
from pdf_processing_pipeline import main
```

2. Process a PDF file:
```python
# Read PDF content
with open("sample.pdf", "rb") as f:
    pdf_content = f.read()

# Create and run pipeline
result = await main.process_pdf(pdf_content)
print(result)
```

## Project Structure

```
pdf-processing-pipeline/
├── agents/              # Agent implementations
│   ├── manager.py      # Manager agent
│   ├── extractor.py    # PDF extraction agent
│   └── evaluator.py    # JSON validation agent
├── tools/              # Custom tools
│   └── pdf_extractor.py # PDF processing tool
└── main.py            # Example runner
```

## How It Works

1. The Manager Agent receives a PDF processing task
2. It delegates the extraction task to the Extractor Agent
3. The Extractor Agent uses PyPDF to extract content
4. The extracted content is sent to the Evaluator Agent
5. The Evaluator Agent validates the JSON format
6. Results are collected and returned

## Sample Output

```json
{
  "status": "success",
  "extraction": {
    "status": "success",
    "total_pages": 2,
    "content": {
      "page_1": "Sample text from page 1",
      "page_2": "Sample text from page 2"
    }
  },
  "evaluation": {
    "status": "success",
    "is_valid_json": true,
    "timestamp": "2025-01-18T10:30:00Z"
  }
}
```

## Key Learning Points

1. **Agent Hierarchy**: How to structure agents in a parent-child relationship
2. **Task Delegation**: How managers delegate tasks to specialized agents
3. **Tool Integration**: How to integrate external tools (PyPDF)
4. **Pipeline Processing**: How to chain multiple agents for complex tasks
5. **Error Handling**: How to manage errors across multiple agents


[//]: # (## Further Reading)

[//]: # (- [Pilott Documentation]&#40;link-to-docs&#41;)

[//]: # (- [Agent System Guide]&#40;link-to-guide&#41;)

[//]: # (- [Tool Development]&#40;link-to-tool-guide&#41;)