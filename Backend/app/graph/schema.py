"""Graph labels, relationship types, and indexes. Import constants, never type strings."""
from app.db.falkor import graph

# Node labels
EMPLOYEE, SKILL, TEAM, CLIENT, PROJECT = "Employee", "Skill", "Team", "Client", "Project"
TASK, RESOURCE, DOCUMENT, DECISION = "Task", "Resource", "Document", "Decision"
REQUIREMENT, SESSION = "Requirement", "Session"
ALL_LABELS = [EMPLOYEE, SKILL, TEAM, CLIENT, PROJECT, TASK, RESOURCE,
              DOCUMENT, DECISION, REQUIREMENT, SESSION]

# Relationship types
HAS_SKILL, MEMBER_OF, MENTORS, ASSIGNED_TO, COMPLETED = "HAS_SKILL", "MEMBER_OF", "MENTORS", "ASSIGNED_TO", "COMPLETED"
FOR_CLIENT, REQUIRES_SKILL, HAS_NEED = "FOR_CLIENT", "REQUIRES_SKILL", "HAS_NEED"
PART_OF, NEEDS_SKILL, BLOCKED_BY = "PART_OF", "NEEDS_SKILL", "BLOCKED_BY"
TEACHES, PREREQUISITE_OF = "TEACHES", "PREREQUISITE_OF"
MADE_BY, DERIVED_FROM, AFFECTS, SUPERSEDES = "MADE_BY", "DERIVED_FROM", "AFFECTS", "SUPERSEDES"
ABOUT, ASKED_ABOUT = "ABOUT", "ASKED_ABOUT"


def create_indexes() -> None:
    """Index `id` on every label. Safe to call repeatedly."""
    for label in ALL_LABELS:
        try:
            graph.query(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
        except Exception as e:
            if "already indexed" not in str(e).lower():
                print(f"index {label}: {e}")


if __name__ == "__main__":
    create_indexes()
    print("indexes ready")
