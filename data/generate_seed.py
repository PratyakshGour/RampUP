import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
DATA_FILES = (
	"client.json",
	"employees.json",
	"projects.json",
	"tasks.json",
	"resources.json",
	"decision.json",
)


def load_records() -> dict[str, list[dict[str, Any]]]:
	records = {}
	for filename in DATA_FILES:
		path = DATA_DIR / filename
		with path.open(encoding="utf-8") as seed_file:
			data = json.load(seed_file)
		if not isinstance(data, list):
			raise ValueError(f"{filename} must contain a JSON array")
		if any(not isinstance(record, dict) for record in data):
			raise ValueError(f"Every item in {filename} must be a JSON object")
		record_type = "decisions" if filename == "decision.json" else filename.removesuffix(".json")
		records[record_type] = data
	return records


def validate_records(records: dict[str, list[dict[str, Any]]]) -> None:
	ids_by_type = {}
	for record_type, items in records.items():
		ids = [item.get("id") for item in items]
		if any(not item_id for item_id in ids):
			raise ValueError(f"Every {record_type} record must have an id")
		if len(ids) != len(set(ids)):
			raise ValueError(f"Duplicate id found in {record_type}.json")
		ids_by_type[record_type] = set(ids)

	references = (
		("employees", "project_id", "projects"),
		("employees", "mentor_id", "employees"),
		("projects", "client_id", "client"),
		("tasks", "project_id", "projects"),
		("decisions", "made_by", "employees"),
		("decisions", "affects_project_id", "projects"),
		("decisions", "supersedes", "decisions"),
	)
	for source_type, field, target_type in references:
		for item in records[source_type]:
			reference = item.get(field)
			if reference is not None and reference not in ids_by_type[target_type]:
				raise ValueError(
					f"{source_type} record {item['id']} refers to unknown "
					f"{target_type} id {reference!r} in {field}"
				)

	task_ids = ids_by_type["tasks"]
	for task in records["tasks"]:
		for dependency in task.get("blocked_by", []):
			if dependency not in task_ids:
				raise ValueError(
					f"Task {task['id']} refers to unknown blocked_by id {dependency!r}"
				)

	resource_ids = ids_by_type["resources"]
	for resource in records["resources"]:
		for prerequisite in resource.get("prerequisite_ids", []):
			if prerequisite not in resource_ids:
				raise ValueError(
					f"Resource {resource['id']} refers to unknown prerequisite id "
					f"{prerequisite!r}"
				)


def main() -> None:
	records = load_records()
	validate_records(records)
	print("Seed data is valid:")
	for record_type, items in records.items():
		print(f"- {record_type}: {len(items)} records")


if __name__ == "__main__":
	main()
