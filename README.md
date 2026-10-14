# RampUp: A Company Brain for Onboarding
 
> A new hire asks: *what should I work on, who do I ask, and what do I learn first?*
> RampUp answers from a graph of people, skills, clients, projects, and decisions, and shows the exact path it followed.
 
Built for **Graph Hacks: Context for AI Agents** (Track 03: Company Brain), powered by FalkorDB.
 
## Problem
 
In large service companies, new hires take weeks to get meaningful tasks, find the right mentor, and locate upskilling resources. Knowledge is scattered across docs, tickets, and chats, and nobody can explain why past decisions were made.
 
## Solution
 
RampUp puts company knowledge into a graph (FalkorDB) alongside a vector index (Qdrant). An agent combines both (GraphRAG) to give answers that are:
 
- **Personalized:** based on the employee's skills vs. project requirements
- **Sourced:** every claim cites a document, ticket, or decision
- **Traceable:** the UI highlights the subgraph path behind each answer
## Features
 
1. **Skill-gap analysis and 30/60/90 plan**
2. **First-task recommender** with reasons
3. **"Who do I ask?"** expert and mentor finder
4. **Client brief and decision trace** back to the source
5. **Live ingestion:** upload a doc and watch the graph update
## Architecture
 
```
React (Vite)  <-->  FastAPI  <-->  FalkorDB (graph)
                       |
                       +-------->  Qdrant (vectors)
                       |
                       +-------->  LLM + Embedding model
```
 
**Query flow:** question → intent routing → vector search (Qdrant) → seed graph nodes → Cypher expansion (FalkorDB) → LLM answer with citations → `{answer, citations, subgraph}`
 
## Graph Schema
 
**Nodes:** Employee, Skill, Role, Team, Client, Project, Task, Resource, Document, Decision, Ticket, Session
 
**Key relationships:**
- `(Employee)-[:HAS_SKILL]->(Skill)`
- `(Employee)-[:ASSIGNED_TO]->(Project)-[:FOR_CLIENT]->(Client)`
- `(Project)-[:REQUIRES_SKILL]->(Skill)`
- `(Task)-[:NEEDS_SKILL]->(Skill)`
- `(Resource)-[:TEACHES]->(Skill)`
- `(Decision)-[:DERIVED_FROM]->(Document)`
- `(Decision)-[:SUPERSEDES]->(Decision)`
## Tech Stack
 
| Layer | Tech |
|---|---|
| Frontend | React, Vite, react-force-graph-2d |
| Backend | FastAPI (Python) |
| Graph DB | FalkorDB |
| Vector DB | Qdrant |
| AI | LLM + embedding model (see `.env`) |
 
## Setup
 
```bash
# 1. Configure
cp .env.example .env        # add your API keys
 
# 2. Start databases
docker compose up -d
 
# 3. Backend
cd backend
pip install -r requirements.txt
python -m app.graph.loader  # load seed data into the graph
uvicorn app.main:app --reload
 
# 4. Frontend
cd frontend
npm install
npm run dev
```
 
Open http://localhost:5173
 
## Demo Flow
 
1. Select a new hire (e.g. Riya, Java developer on the Acme Bank project)
2. View the skill-gap chart and 30/60/90 plan
3. Ask *"Why are we using Kafka on this project?"* and see the cited decision and highlighted path
4. Ask *"Who can help me with payments APIs?"*
5. Upload a new client doc and watch new nodes appear
## Project Structure
 
```
rampup/
├── docker-compose.yml
├── .env.example
├── data/        # synthetic company data + docs
├── backend/     # FastAPI, ingestion, agent, graph queries
└── frontend/    # React + Vite UI
```
 
## Team: TrioScale
 
- Pratyaksh Gour: backend and agent
- Ayush Rawat: frontend
- Sahil Kaushik: data and ingestion
