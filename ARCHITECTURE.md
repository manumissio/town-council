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

    subgraph "Observability & Monitoring"
        Prom[Prometheus]
        Graf[Grafana]
        Mon[Monitor Worker]
    end

    %% Connections
    Web & Legi --> Crawler
    Crawler -- "Staging Data" --> Postgres
    
    Pipeline -- "Reads Staged" --> Postgres
    Pipeline -- "Downloads" --> Web
    Pipeline -- "OCR Requests" --> TikaServer
    Pipeline -- "AI Requests" --> Gemini
    Pipeline -- "Writes Metadata" --> Postgres
    Pipeline -- "Syncs Index" --> Meili
    
    Meili <--> API
    API <--> Frontend

    %% Monitoring flow
    Postgres -.-> Mon
    Mon -- "tc_metrics" --> Prom
    Prom --> Graf
```

## Key Components

1.  **Orchestrated Pipeline:** Instead of manual steps, `run_pipeline.py` coordinates all workers, ensuring data flows logically from raw PDF to searchable index.
2.  **Container Security:** All services run as **non-root users** within minimal Docker images, utilizing multi-stage builds to reduce attack surface and image size.
3.  **AI Accuracy:** The Summarization worker uses the modern `google-genai` SDK (Gemini 2.0 Flash) with deterministic settings (temp 0.0) and grounding instructions.
4.  **Search Performance:** Meilisearch provides instant, typo-tolerant search, offloading complex text queries from the primary Postgres database.
5.  **Real-time Monitoring:** A dedicated `Monitor` worker tracks data freshness and processing counts, exporting them to **Prometheus** and **Grafana** for dashboarding and alerts.
6.  **Robust Data Flow:** The pipeline implements race-condition handling and absolute path management to ensure reliable file processing across containers.
