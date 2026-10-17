import hashlib
import shutil
from datetime import date

from app.config import PROJECT_DIR, settings
from app.models.schema import (
    DecisionExtraction,
    FactExtraction,
    MeetingMetadata,
    PersonExtraction,
    ProjectExtraction,
    SystemExtraction,
    TaskExtraction,
    TranscriptExtraction,
)
from app.services import graph_store

SAMPLE_DIR = PROJECT_DIR / "data" / "sample-transcripts"


def _fixtures():
    common_project_excerpt = (
        "Priya assigned Riya to the Atlas Payments project, and the team uses Kafka "
        "for payment events and PostgreSQL for transactional payment records."
    )
    return [
        (
            "01-new-employee-onboarding.md",
            MeetingMetadata(
                title="New employee onboarding",
                meeting_date=date(2026, 10, 1),
                participants=["Priya Nair", "Riya Sharma", "Arjun Mehta"],
                project_name="Atlas Payments",
                source_name="01-new-employee-onboarding.md",
            ),
            TranscriptExtraction(
                people=[
                    PersonExtraction(
                        name="Priya Nair",
                        role="Payments team lead",
                        team="Payments",
                        attended=True,
                        source_excerpt="Priya Nair, the Payments team lead, welcomed Riya Sharma.",
                    ),
                    PersonExtraction(
                        name="Riya Sharma",
                        role="Backend engineer",
                        team="Payments",
                        attended=True,
                        new_hire=True,
                        works_on=["Atlas Payments"],
                        source_excerpt="Priya assigned Riya to the Atlas Payments project.",
                    ),
                    PersonExtraction(
                        name="Arjun Mehta",
                        role="Platform engineer",
                        team="Payments",
                        attended=True,
                        source_excerpt="Arjun will pair with Riya on the Kafka consumer runbook.",
                    ),
                ],
                projects=[
                    ProjectExtraction(
                        name="Atlas Payments",
                        description="Payment processing and event-delivery project.",
                        systems=["Kafka", "PostgreSQL"],
                        source_excerpt=common_project_excerpt,
                    )
                ],
                systems=[
                    SystemExtraction(
                        name="Kafka",
                        description="Asynchronous payment event platform.",
                        source_excerpt="The team uses Kafka for payment events.",
                    ),
                    SystemExtraction(
                        name="PostgreSQL",
                        description="Transactional payment record store.",
                        source_excerpt="The team uses PostgreSQL for transactional payment records.",
                    ),
                ],
                decisions=[
                    DecisionExtraction(
                        summary="Validate access tokens inside the Payments API",
                        status="proposed",
                        rationale="An earlier proposal suggested local token validation, but it was not approved.",
                        project="Atlas Payments",
                        systems=["OAuth2", "Payments API"],
                        source_excerpt="The team has not approved that proposal; the authentication handoff will resolve the boundary.",
                        source_section="Section 3",
                    )
                ],
                tasks=[
                    TaskExtraction(
                        description="Review the payment event flow before the first sprint",
                        owner="Riya Sharma",
                        project="Atlas Payments",
                        source_excerpt="Priya assigned Riya to review the payment event flow before her first sprint.",
                        source_section="Section 2",
                    ),
                    TaskExtraction(
                        description="Pair with Riya on the Kafka consumer runbook",
                        owner="Arjun Mehta",
                        project="Atlas Payments",
                        source_excerpt="Arjun will pair with Riya on the Kafka consumer runbook.",
                        source_section="Section 2",
                    ),
                ],
                facts=[
                    FactExtraction(
                        content="The Atlas Payments team uses Kafka for payment events.",
                        category="architecture",
                        people=["Priya Nair", "Riya Sharma", "Arjun Mehta"],
                        projects=["Atlas Payments"],
                        systems=["Kafka"],
                        source_excerpt="The team uses Kafka for payment events.",
                        source_section="Section 2",
                    )
                ],
            ),
        ),
        (
            "02-payments-architecture-sync.md",
            MeetingMetadata(
                title="Payments architecture sync",
                meeting_date=date(2026, 10, 3),
                participants=["Priya Nair", "Arjun Mehta", "Riya Sharma"],
                project_name="Atlas Payments",
                source_name="02-payments-architecture-sync.md",
            ),
            TranscriptExtraction(
                people=[
                    PersonExtraction(
                        name="Priya Nair",
                        role="Payments team lead",
                        team="Payments",
                        attended=True,
                        source_excerpt="Priya Nair, Arjun Mehta, and Riya Sharma attended the Atlas Payments architecture sync.",
                    ),
                    PersonExtraction(
                        name="Arjun Mehta",
                        role="Platform engineer",
                        team="Payments",
                        attended=True,
                        source_excerpt="Arjun will add bounded retries and a dead-letter topic to the Kafka consumer.",
                    ),
                    PersonExtraction(
                        name="Riya Sharma",
                        role="Backend engineer",
                        team="Payments",
                        attended=True,
                        new_hire=True,
                        works_on=["Atlas Payments"],
                        source_excerpt="Priya Nair, Arjun Mehta, and Riya Sharma attended the Atlas Payments architecture sync.",
                    ),
                ],
                projects=[
                    ProjectExtraction(
                        name="Atlas Payments",
                        description="Payment processing project.",
                        systems=["Kafka", "PostgreSQL", "Payments API", "Fraud service", "Audit service"],
                        owner="Priya Nair",
                        source_excerpt="Priya Nair owns the Atlas Payments project.",
                    )
                ],
                systems=[
                    SystemExtraction(
                        name="Kafka",
                        description="Asynchronous payment event platform.",
                        source_excerpt="The team confirmed Kafka for asynchronous payment events because synchronous calls between payment, fraud, and audit services reached a latency knee at approximately 450 transactions per second.",
                    ),
                    SystemExtraction(
                        name="PostgreSQL",
                        description="Relational transactional database.",
                        source_excerpt="The team confirmed PostgreSQL for payment records because the workflow needs transactions and relational constraints.",
                    ),
                    SystemExtraction(
                        name="Payments API",
                        source_excerpt="The team confirmed Kafka for asynchronous payment events because synchronous calls between payment, fraud, and audit services reached a latency knee at approximately 450 transactions per second.",
                    ),
                    SystemExtraction(
                        name="Fraud service",
                        source_excerpt="The team confirmed Kafka for asynchronous payment events because synchronous calls between payment, fraud, and audit services reached a latency knee at approximately 450 transactions per second.",
                    ),
                    SystemExtraction(
                        name="Audit service",
                        source_excerpt="The team confirmed Kafka for asynchronous payment events because synchronous calls between payment, fraud, and audit services reached a latency knee at approximately 450 transactions per second.",
                    ),
                ],
                decisions=[
                    DecisionExtraction(
                        summary="Use Kafka for asynchronous payment events",
                        status="confirmed",
                        rationale="Synchronous calls reached a latency knee at approximately 450 transactions per second. Kafka buffers bursts, separates consumers, and supports replay, with additional broker and partition operations as a trade-off.",
                        project="Atlas Payments",
                        systems=["Kafka", "Payments API", "Fraud service", "Audit service"],
                        source_excerpt="The team confirmed Kafka for asynchronous payment events because synchronous calls between payment, fraud, and audit services reached a latency knee at approximately 450 transactions per second.",
                        source_section="Section 2",
                    ),
                    DecisionExtraction(
                        summary="Use PostgreSQL for transactional payment records",
                        status="confirmed",
                        rationale="The workflow needs transactions and relational constraints; MongoDB was considered but not selected for the primary transactional store.",
                        project="Atlas Payments",
                        systems=["PostgreSQL"],
                        source_excerpt="The team confirmed PostgreSQL for payment records because the workflow needs transactions and relational constraints.",
                        source_section="Section 3",
                    ),
                ],
                tasks=[
                    TaskExtraction(
                        description="Add bounded retries and a dead-letter topic to the Kafka consumer",
                        owner="Arjun Mehta",
                        project="Atlas Payments",
                        source_excerpt="Arjun will add bounded retries and a dead-letter topic to the Kafka consumer before the next load test.",
                        source_section="Section 4",
                    )
                ],
                facts=[
                    FactExtraction(
                        content="The synchronous design reached a latency knee near 450 transactions per second.",
                        category="performance",
                        people=["Priya Nair", "Arjun Mehta"],
                        projects=["Atlas Payments"],
                        systems=["Kafka", "Payments API", "Fraud service", "Audit service"],
                        source_excerpt="Synchronous calls between payment, fraud, and audit services reached a latency knee at approximately 450 transactions per second.",
                        source_section="Section 2",
                    ),
                    FactExtraction(
                        content="Priya Nair owns the Atlas Payments project.",
                        category="ownership",
                        people=["Priya Nair"],
                        projects=["Atlas Payments"],
                        source_excerpt="Priya Nair owns the Atlas Payments project.",
                        source_section="Section 4",
                    ),
                ],
            ),
        ),
        (
            "03-authentication-handoff.md",
            MeetingMetadata(
                title="Authentication handoff",
                meeting_date=date(2026, 10, 6),
                participants=["Arjun Mehta", "Riya Sharma", "Sana Iqbal"],
                project_name="Atlas Payments",
                source_name="03-authentication-handoff.md",
            ),
            TranscriptExtraction(
                people=[
                    PersonExtraction(
                        name="Arjun Mehta",
                        role="Platform engineer",
                        team="Payments",
                        attended=True,
                        expertise_in=["OAuth2", "Identity Gateway"],
                        source_excerpt="Arjun Mehta is the authentication and OAuth2 subject-matter expert.",
                    ),
                    PersonExtraction(
                        name="Riya Sharma",
                        role="Backend engineer",
                        team="Payments",
                        attended=True,
                        new_hire=True,
                        works_on=["Atlas Payments"],
                        source_excerpt="Riya Sharma will document the gateway-to-payment identity claims.",
                    ),
                    PersonExtraction(
                        name="Sana Iqbal",
                        role="Identity engineer",
                        team="Platform",
                        attended=True,
                        source_excerpt="Arjun Mehta, Riya Sharma, and Sana Iqbal attended the Atlas Payments authentication handoff.",
                    ),
                ],
                projects=[
                    ProjectExtraction(
                        name="Atlas Payments",
                        description="Payment processing project.",
                        systems=["OAuth2", "Identity Gateway", "Payments API"],
                        source_excerpt="The Payments API depends on the Identity Gateway for authenticated requests.",
                    )
                ],
                systems=[
                    SystemExtraction(
                        name="OAuth2",
                        description="Access-token protocol used by the identity gateway.",
                        source_excerpt="The team confirmed that the Identity Gateway validates OAuth2 access tokens; the Payments API receives the validated identity and must not validate tokens a second time.",
                    ),
                    SystemExtraction(
                        name="Identity Gateway",
                        description="Validates OAuth2 access tokens.",
                        source_excerpt="The team confirmed that the Identity Gateway validates OAuth2 access tokens; the Payments API receives the validated identity and must not validate tokens a second time.",
                    ),
                    SystemExtraction(
                        name="Payments API",
                        description="Consumes gateway-validated identity claims.",
                        source_excerpt="The team confirmed that the Identity Gateway validates OAuth2 access tokens; the Payments API receives the validated identity and must not validate tokens a second time.",
                    ),
                ],
                decisions=[
                    DecisionExtraction(
                        summary="Validate OAuth2 tokens at the Identity Gateway",
                        status="confirmed",
                        rationale="The gateway validates access tokens once and passes the validated identity to the Payments API, avoiding duplicate validation.",
                        project="Atlas Payments",
                        systems=["OAuth2", "Identity Gateway", "Payments API"],
                        supersedes="Validate access tokens inside the Payments API",
                        source_excerpt="The team confirmed that the Identity Gateway validates OAuth2 access tokens; the Payments API receives the validated identity and must not validate tokens a second time.",
                        source_section="Section 2",
                    )
                ],
                tasks=[
                    TaskExtraction(
                        description="Document gateway-to-payment identity claims and review with Arjun",
                        owner="Riya Sharma",
                        project="Atlas Payments",
                        source_excerpt="Riya Sharma will document the gateway-to-payment identity claims and review the handoff with Arjun before enabling the integration.",
                        source_section="Section 4",
                    )
                ],
                facts=[
                    FactExtraction(
                        content="The Payments API depends on the Identity Gateway for authenticated requests.",
                        category="dependency",
                        people=["Arjun Mehta", "Riya Sharma", "Sana Iqbal"],
                        projects=["Atlas Payments"],
                        systems=["Identity Gateway", "Payments API"],
                        source_excerpt="The Payments API depends on the Identity Gateway for authenticated requests.",
                        source_section="Section 3",
                    )
                ],
            ),
        ),
    ]


def load_demo_data() -> int:
    settings.transcript_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for filename, metadata, extraction in _fixtures():
        source_path = SAMPLE_DIR / filename
        content = source_path.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()
        meeting_id = graph_store.meeting_id_for(content_hash)
        destination = settings.transcript_dir / f"{content_hash[:20]}_{filename}"
        if not destination.exists():
            shutil.copyfile(source_path, destination)
        graph_store.upsert_node(
            "Meeting",
            meeting_id,
            {
                "title": metadata.title,
                "meeting_date": metadata.meeting_date,
                "participants": metadata.participants,
                "project_name": metadata.project_name,
                "source_name": metadata.source_name,
                "content_hash": content_hash,
                "storage_name": destination.name,
                "extraction_status": "pending",
                "synthetic": True,
                "demo_mode": True,
            },
        )
        graph_store.persist_extraction(meeting_id, metadata, extraction)
        graph_store.set_meeting_status(meeting_id, "processed")
        count += 1
    return count


def main():
    count = load_demo_data()
    print(f"Loaded {count} deterministic synthetic meetings into graph '{settings.falkordb_graph}'.")


if __name__ == "__main__":
    main()
