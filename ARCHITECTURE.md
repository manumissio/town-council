# Modernized Town Council Architecture (2026)

This document provides a visual and technical overview of the current system architecture.

## System Diagram

```mermaid
graph TD
    subgraph "External Data Sources"
        Web[City Meeting Portals]
        Legi[Legistar / Granicus]
    end

    subgraph "Crawler Layer (Scrapy)"
        Spiders[City-Specific Spiders]
        Delta[Delta Crawling Logic]
        CModels[Crawler Models]
    end

    subgraph "Persistent Storage"
        DB[(PostgreSQL 15)]
        subgraph "Database Tables"
            Stage[Staging: Event/Url]
            Prod[Production: Event/Place]
            Cat[Catalog: Text/AI Metadata]
        end
    end

    subgraph "Automated Pipeline (run_pipeline.py)"
        Down[Downloader: Parallel Streaming]
        Tika[Apache Tika: OCR & Text]
        Tables[Camelot: Budget Tables]
        Topics[Scikit-Learn: LDA Themes]
        NLP[SpaCy: Entity Recognition]
        Gemini[Google GenAI: AI Summaries]
    end

    subgraph "Search & API Layer"
        Meili[[Meilisearch Engine]]
        FastAPI[FastAPI Backend]
    end

    subgraph "Presentation Layer"
        UI[Next.js 14 Web Interface]
    end

    subgraph "Verification & Observability"
        Tests[Pytest Suite: 11+ Cases]
        Prom[Prometheus Metrics]
        Graf[Grafana Dashboards]
    end

    %% Connections
    Web & Legi --> Spiders
    Spiders --> Delta
    Delta --> Stage
    Stage -- "promote_stage.py" --> Prod
    
    Prod --> Down
    Down --> Tika
    Tika --> Tables
    Tables --> Topics
    Topics --> NLP
    NLP --> Gemini
    
    %% Indexing flow
    Gemini & NLP & Tables & Topics --> Cat
    Cat & Prod --> Meili
    
    %% User Access
    Meili <--> FastAPI
    FastAPI <--> UI
    
    %% Reliability
    Tests -.-> Spiders & Down & Gemini & NLP
    Cat & Prod -.-> Prom --> Graf
```

## Key Components

1.  **Orchestrated Pipeline:** Instead of manual steps, `run_pipeline.py` coordinates all workers, ensuring data flows logically from raw PDF to searchable index.
2.  **AI Accuracy:** The Summarization worker uses the modern `google-genai` SDK with deterministic settings (temp 0.0) and grounding instructions to prevent hallucinations.
3.  **Search Performance:** Meilisearch provides instant, typo-tolerant search, offloading complex text queries from the primary Postgres database.
4.  **Security First:** The system includes path-traversal protection, secure dependency management, and safe credential handling via environment variables.
5.  **Self-Verifying:** A `pytest` suite covers critical logic including date parsing, URL hashing, security checks, and AI mocking.
