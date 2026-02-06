# Modernized Town Council Architecture (2026)

This document provides a technical overview of the system design, focusing on the high-performance data pipeline, structured civic data modeling, and security model.

## System Diagram

```mermaid
graph TD
    subgraph "External World"
        Web[City Portals]
        Legi[Legistar/Granicus]
        Gemini[Google Gemini 2.0 API]
    end

    subgraph "Ingestion Layer (Scrapy)"
        Crawler[Crawler Service]
        Delta[Delta Crawling Logic]
    end

    subgraph "Persistent Storage (PostgreSQL 15)"
        subgraph "OCD Hierarchy"
            Place[Place: Jurisdictions]
            Org[Organization: Bodies]
            Mem[Membership: Roles]
            Person[Person: Officials]
        end
        subgraph "Data Tables"
            Stage[Staging: URLs/Events]
            Prod[Production: Events]
            Items[Agenda Items: Deep-Links]
            Cat[Catalog: Text/AI Metadata]
        end
    end

    subgraph "Processing Pipeline (Python 3.12)"
        Downloader[Downloader: Parallel Streaming]
        Tika[Apache Tika: OCR/Text]
        Segmenter[Agenda Segmenter: AI Splitting]
        Linker[Person Linker: Entity Disambiguation]
        Workers[NLP/Topic/Table Workers]
    end

    subgraph "Search & Access"
        Meili[[Meilisearch 1.6]]
        FastAPI[FastAPI Backend]
        NextJS[Next.js 16 UI]
    end

    subgraph "Observability"
        Mon[Monitor Service]
        Prom[Prometheus]
        Graf[Grafana]
    end

    %% Flow: Ingestion
    Web & Legi --> Crawler
    Crawler --> Delta
    Delta --> Stage
    Stage -- "promote_stage.py" --> Prod

    %% Flow: Processing
    Prod --> Downloader
    Downloader -- "Absolute Paths" --> Postgres
    Downloader --> Tika
    Tika --> Segmenter
    Segmenter --> Items
    Items --> Workers
    Workers --> Linker
    Linker --> Mem & Person

    %% Flow: Access & On-Demand AI
    Cat --> Meili
    Meili <--> FastAPI
    NextJS -- "POST /summarize" --> FastAPI
    FastAPI -- "On-Demand" --> Gemini
    FastAPI -- "CORS Restricted" --> NextJS

    %% Flow: Metrics
    Postgres -.-> Mon
    Mon -- "tc_metrics" --> Prom
    Prom --> Graf
```

## Key Components & Design Principles

### 1. Ingestion Layer (Scrapy)
The system utilizes city-specific spiders to handle municipal website volatility. It supports multiple portal architectures:
*   **Table-Centric (Berkeley):** Directly parses modern city websites using high-precision XPaths.
*   **CivicPlus/Folder-Centric (Dublin):** Navigates standard government platforms that use metadata attributes (like `data-th`) for accessibility.
*   **API-Centric (Cupertino):** Communicates directly with modern platforms like **Legistar Web API**. This provides the highest reliability as it bypasses HTML complexity and bot detection.
*   **Delta Crawling:** All spiders implement a "look-back" check against the database to only fetch meetings that haven't been processed yet.

### 2. Structured Data Modeling (OCD Alignment)
The system follows the **Open Civic Data (OCD)** standard to ensure interoperability and accountability:
*   **Jurisdiction (Place):** The geographical scope (e.g., Berkeley, CA).
*   **Organization:** The legislative body or committee (e.g., Planning Commission).
*   **Membership:** The specific role an official holds within an organization.
*   **Person:** A unique identity for an official, tracked across different roles and cities.

### 3. Agenda Item Segmentation (Deep-Linking)
To solve the "Needle in a Haystack" problem, the system uses an AI-driven segmentation worker:
*   **Splitting Logic:** Gemini 2.0 Flash reads the full OCR text and identifies individual agenda items, extracting titles, descriptions, and results (e.g., "Passed").
*   **Granular Indexing:** These items are indexed in Meilisearch as separate, first-class entities.
*   **Benefit:** Search results can point users directly to the specific 1-page section of a 500-page packet, significantly improving accessibility.

### 4. Interoperable Identifiers (OCD-ID)
The system implements a standardized identifier generator (`ocd-[type]/[uuid]`) for all core entities:
*   **Avoids IDOR Attacks:** Random UUIDs prevent malicious enumeration of records.
*   **Federation Ready:** By following the OCD standard, the database is interoperable with other civic data projects like *Open States* or *Councilmatic*.

### 5. Hybrid AI/ML Strategy (Entity Resolution)
To balance performance and cost, the system utilizes a **Hybrid Strategy**:
*   **Traditional AI (Fuzzy Matching):** The system uses the **Levenshtein Distance** algorithm (via RapidFuzz) to resolve similar names (e.g., "John Smith" vs "John A. Smith") to the same unique official. This runs locally in milliseconds and is 100% free.
*   **Blocking:** Comparisons are "blocked" by city to ensure the algorithm scales to thousands of records without slowing down.
*   **LLM Fallback:** Complex tasks like summarization and agenda segmentation use **Gemini 2.0 Flash**, but are only triggered on-demand to minimize token usage.

### 6. Security Model
*   **CORS Restriction:** The API is hardened to only accept requests from the authorized frontend origin (`localhost:3000`).
*   **Dependency Injection:** Database sessions are managed via FastAPI's dependency system, ensuring every connection is strictly closed after a request to prevent connection leaks.
*   **Non-Root Execution:** All Docker containers run as a restricted `appuser`.
*   **Path Traversal Protection:** The `is_safe_path` validator ensures workers only interact with authorized data directories.

### 7. Container Optimization & Performance
To ensure fast developer iteration and secure production deployments, the system uses an optimized Docker architecture:
*   **Multi-Stage Builds:** Separates build-time dependencies (compilers, headers) from the final runtime image, reducing the attack surface and image size.
*   **BuildKit Cache Mounts:** Utilizes `--mount=type=cache` for both Python (pip) and Node.js (npm). This allows the system to cache package downloads across builds, making repeated installs up to 10x faster.
*   **Next.js Standalone Mode:** The frontend utilizes Next.js output tracing to create a minimal production server that only carries the absolute necessary files, resulting in a ~1GB reduction in image size.
*   **Strict Layering:** Dockerfiles are structured to copy dependency files (`requirements.txt`, `package.json`) before source code, maximizing layer reuse.

### 4. High-Performance Search & UX
*   **Unified Search Hub:** A segmented search bar integrating Keyword, Municipality, Body, and Type filters.
*   **Yield-Based Indexing:** The Meilisearch indexer uses Python's `yield_per` pattern to stream hundreds of thousands of documents with minimal memory footprint.
*   **Tiered Inspection:** A 3-tier UI flow (Snippet -> Full Text -> AI Insights) manages cognitive load.

### 5. AI Strategy
*   **On-Demand Summarization:** To prevent `429 Rate Limit` errors, summaries are only generated when requested by a user in the UI.
*   **Caching:** AI responses are permanently saved to the `catalog` table, making subsequent views instant and cost-free.
*   **Grounding:** Models use a temperature of 0.0 and strict instructional grounding to eliminate hallucinations.
