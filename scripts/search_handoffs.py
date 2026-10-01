"""Print the audit trail for one marketplace order."""

import argparse
import json

from marketplace_handoff.handoff_service import HandoffLogbook
from marketplace_handoff.infrai_client import InfraiClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("order_id")
    args = parser.parse_args()
    entries = HandoffLogbook(InfraiClient()).audit(args.order_id)
    print(json.dumps([entry.model_dump() for entry in entries], indent=2))


if __name__ == "__main__":
    main()

