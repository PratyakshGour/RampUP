"""Load data/*.json and docs/*.md into FalkorDB. Idempotent (MERGE).
Run from backend/:  python -m app.graph.loader [--reset]
"""
import json
import sys

import frontmatter

from app.config import settings
from app.db import falkor
from app.graph import schema as S

D = settings.data_path


import re


def _load(name: str, fallbacks: list[str] | None = None) -> list[dict]:
    candidates = [name] + (fallbacks or [])
    for candidate in candidates:
        p = D / f"{candidate}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return []


def _nodes(label: str, rows: list[dict]) -> None:
    if not rows:
        return
    seen = set()
    deduped = []
    for r in rows:
        rid = r.get("id")
        if rid and rid not in seen:
            seen.add(rid)
            deduped.append(r)
    if deduped:
        falkor.run(
            f"UNWIND $rows AS r MERGE (n:{label} {{id: r.id}}) SET n += r.props",
            {"rows": deduped},
        )


def _edges(src: str, rel: str, dst: str, rows: list[dict]) -> None:
    """rows: [{src, dst, props}]"""
    seen = set()
    deduped = []
    for r in rows:
        s, d = r.get("src"), r.get("dst")
        if not s or not d:
            continue
        props = r.get("props") or {}
        key = (s, d, tuple(sorted(props.items())))
        if key not in seen:
            seen.add(key)
            deduped.append({"src": s, "dst": d, "props": props})
    if deduped:
        falkor.run(
            f"UNWIND $rows AS r MATCH (a:{src} {{id: r.src}}), (b:{dst} {{id: r.dst}}) "
            f"MERGE (a)-[e:{rel}]->(b) SET e += r.props",
            {"rows": deduped},
        )


def _row(id_, **props) -> dict:
    return {"id": id_, "props": {"id": id_, **{k: v for k, v in props.items() if v is not None}}}


def _link(a, b, **props) -> dict:
    return {"src": a, "dst": b, "props": {k: v for k, v in props.items() if v is not None}}


def load_all(reset: bool = False) -> None:
    if reset:
        falkor.clear_graph()
    S.create_indexes()

    skills = _load("skills", ["skill"])
    teams = _load("teams", ["team"])
    clients = _load("client", ["clients"])
    projects = _load("projects", ["project"])
    emps = _load("employees", ["employee"])
    tasks = _load("tasks", ["task"])
    resources = _load("resources", ["resource"])
    decisions = _load("decision", ["decisions"])

    # Synthesize teams from employees if teams.json does not exist
    if not teams:
        team_metadata = {
            "team_001": ("Backend Engineering", "Core APIs and backend services"),
            "team_002": ("AI / ML Engineering", "AI agents, models, and embeddings"),
            "team_003": ("Frontend Engineering", "User interfaces and design systems"),
            "team_004": ("Data Engineering", "Data pipelines and analytics"),
            "team_005": ("Platform & Cloud", "Cloud infrastructure and DevOps"),
        }
        unique_team_ids = sorted({e["team_id"] for e in emps if e.get("team_id")})
        teams = [
            {
                "id": tid,
                "name": team_metadata.get(tid, (tid.replace("_", " ").title(), ""))[0],
                "focus": team_metadata.get(tid, ("", ""))[1],
            }
            for tid in unique_team_ids
        ]

    # ---- nodes ----
    _nodes(S.SKILL, [_row(x["id"], name=x.get("name", ""), category=x.get("category")) for x in skills if x.get("id")])
    _nodes(S.TEAM, [_row(x["id"], name=x.get("name", ""), focus=x.get("focus")) for x in teams if x.get("id")])
    _nodes(S.CLIENT, [_row(x["id"], name=x.get("name", ""), industry=x.get("industry"),
                           tech_preferences=x.get("tech_preferences"),
                           contact_person=x.get("contact_person")) for x in clients if x.get("id")])
    _nodes(S.PROJECT, [_row(x["id"], name=x.get("name", ""), status=x.get("status"),
                            start_date=x.get("start_date")) for x in projects if x.get("id")])
    _nodes(S.EMPLOYEE, [_row(x["id"], name=x.get("name", ""), role=x.get("role"),
                             joined_date=x.get("joined_date"),
                             is_new_hire=x.get("is_new_hire", False)) for x in emps if x.get("id")])
    _nodes(S.TASK, [_row(x["id"], name=x.get("title", ""), description=x.get("description"),
                         difficulty=x.get("difficulty"), est_hours=x.get("est_hours"),
                         status=x.get("status")) for x in tasks if x.get("id")])
    _nodes(S.RESOURCE, [_row(x["id"], name=x.get("title", ""), type=x.get("type"), url=x.get("url"),
                             duration_hours=x.get("duration_hours")) for x in resources if x.get("id")])
    _nodes(S.DECISION, [_row(x["id"], name=x.get("title", ""), summary=x.get("summary"),
                             rationale=x.get("rationale"), date=x.get("date")) for x in decisions if x.get("id")])

    # client needs -> Requirement nodes
    reqs, has_need = [], []
    for c in clients:
        cid = c.get("id")
        if not cid:
            continue
        for i, need in enumerate(c.get("needs", [])):
            rid = f"req_{cid}_{i}"
            reqs.append(_row(rid, name=need))
            has_need.append(_link(cid, rid))
    _nodes(S.REQUIREMENT, reqs)

    # documents: markdown frontmatter + markdown sections + decision sources
    docs_map: dict[str, dict] = {}
    doc_about_client, doc_about_proj = [], []
    client_by_name = {c.get("name", "").lower(): c["id"] for c in clients if c.get("id") and c.get("name")}

    docs_dir = D / "docs"
    if docs_dir.exists():
        for p in sorted(docs_dir.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            post = frontmatter.loads(text)
            m = post.metadata or {}
            h1 = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            file_doc_id = str(m.get("id") or f"doc_{p.stem.lower()}")
            file_title = str(m.get("title") or (h1.group(1).strip() if h1 else p.stem.replace("_", " ").title()))
            file_author = str(m.get("author") or "Team")
            file_date = str(m.get("date", ""))

            docs_map[file_doc_id] = _row(file_doc_id, name=file_title, author=file_author, date=file_date)

            if m.get("about_client"):
                doc_about_client.append(_link(file_doc_id, str(m["about_client"])))
            if m.get("about_project"):
                doc_about_proj.append(_link(file_doc_id, str(m["about_project"])))

            # Check for client mentions
            for c_name, cid in client_by_name.items():
                if c_name and c_name in text.lower():
                    doc_about_client.append(_link(file_doc_id, cid))

            # Check for project mentions
            for proj_id in set(re.findall(r"proj_\d+", text)):
                doc_about_proj.append(_link(file_doc_id, proj_id))

            # Extract sections with Source ID
            sec_matches = re.finditer(
                r"##\s+(?:(?P<date>\d{4}-\d{2}-\d{2})\s*-\s*)?(?P<title>[^\n]+).*?\*\*Source ID:\*\*\s*`(?P<src_id>doc_[^`]+)`",
                text,
                re.DOTALL,
            )
            for sm in sec_matches:
                src_id = sm.group("src_id")
                sec_title = sm.group("title").strip()
                sec_date = sm.group("date") or file_date
                docs_map[src_id] = _row(src_id, name=sec_title, author=file_author, date=sec_date)
                proj_match = re.search(r"\(?(proj_\d+)\)?", sm.group(0))
                if proj_match:
                    doc_about_proj.append(_link(src_id, proj_match.group(1)))

    # Ensure all decision source documents exist
    for d in decisions:
        df = d.get("derived_from")
        if df:
            if df not in docs_map:
                docs_map[df] = _row(df, name=df.replace("doc_", "").replace("_", " ").title(), author="Team", date=d.get("date", ""))
            if d.get("affects_project_id"):
                doc_about_proj.append(_link(df, d["affects_project_id"]))

    _nodes(S.DOCUMENT, list(docs_map.values()))

    # ---- edges ----
    _edges(S.CLIENT, S.HAS_NEED, S.REQUIREMENT, has_need)
    _edges(S.DOCUMENT, S.ABOUT, S.CLIENT, doc_about_client)
    _edges(S.DOCUMENT, S.ABOUT, S.PROJECT, doc_about_proj)

    _edges(S.PROJECT, S.FOR_CLIENT, S.CLIENT,
           [_link(p["id"], p["client_id"]) for p in projects if p.get("id") and p.get("client_id")])
    _edges(S.PROJECT, S.REQUIRES_SKILL, S.SKILL,
           [_link(p["id"], s["skill_id"], level=s.get("level", 1))
            for p in projects if p.get("id")
            for s in p.get("requires_skills", []) if s.get("skill_id")])

    _edges(S.EMPLOYEE, S.MEMBER_OF, S.TEAM,
           [_link(e["id"], e["team_id"]) for e in emps if e.get("id") and e.get("team_id")])
    _edges(S.EMPLOYEE, S.HAS_SKILL, S.SKILL,
           [_link(e["id"], s["skill_id"], level=s.get("level", 1))
            for e in emps if e.get("id")
            for s in e.get("skills", []) if s.get("skill_id")])
    _edges(S.EMPLOYEE, S.MENTORS, S.EMPLOYEE,
           [_link(e["mentor_id"], e["id"]) for e in emps if e.get("id") and e.get("mentor_id")])
    _edges(S.EMPLOYEE, S.ASSIGNED_TO, S.PROJECT,
           [_link(e["id"], e["project_id"]) for e in emps if e.get("id") and e.get("project_id")])

    _edges(S.TASK, S.PART_OF, S.PROJECT,
           [_link(t["id"], t["project_id"]) for t in tasks if t.get("id") and t.get("project_id")])
    _edges(S.TASK, S.NEEDS_SKILL, S.SKILL,
           [_link(t["id"], s["skill_id"], level=s.get("level", 1))
            for t in tasks if t.get("id")
            for s in t.get("needs_skills", []) if s.get("skill_id")])
    _edges(S.TASK, S.BLOCKED_BY, S.TASK,
           [_link(t["id"], b) for t in tasks if t.get("id") for b in t.get("blocked_by", []) if b])

    _edges(S.RESOURCE, S.TEACHES, S.SKILL,
           [_link(r["id"], s["skill_id"], level=s.get("level", 1))
            for r in resources if r.get("id")
            for s in r.get("teaches", []) if s.get("skill_id")])
    _edges(S.RESOURCE, S.PREREQUISITE_OF, S.RESOURCE,
           [_link(q, r["id"]) for r in resources if r.get("id") for q in r.get("prerequisite_ids", []) if q])

    _edges(S.DECISION, S.MADE_BY, S.EMPLOYEE,
           [_link(d["id"], d["made_by"]) for d in decisions if d.get("id") and d.get("made_by")])
    _edges(S.DECISION, S.AFFECTS, S.PROJECT,
           [_link(d["id"], d["affects_project_id"]) for d in decisions if d.get("id") and d.get("affects_project_id")])
    _edges(S.DECISION, S.DERIVED_FROM, S.DOCUMENT,
           [_link(d["id"], d["derived_from"]) for d in decisions if d.get("id") and d.get("derived_from")])
    _edges(S.DECISION, S.SUPERSEDES, S.DECISION,
           [_link(d["id"], d["supersedes"]) for d in decisions if d.get("id") and d.get("supersedes")])

    print_counts()


def print_counts() -> None:
    try:
        print("\nNodes:")
        for r in falkor.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS c ORDER BY c DESC"):
            print(f"  {r.get('label', 'Node'):<12} {r.get('c', 0)}")
        print("Edges:")
        for r in falkor.run("MATCH ()-[e]->() RETURN type(e) AS t, count(e) AS c ORDER BY c DESC"):
            print(f"  {r.get('t', 'Edge'):<16} {r.get('c', 0)}")
    except Exception as e:
        print(f"Could not retrieve graph counts: {e}")


if __name__ == "__main__":
    load_all(reset="--reset" in sys.argv)