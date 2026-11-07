"""Set up a local hearthboard for the demo and run it: one project per team, a human lead for each team, a
supervisor (a global admin), and Overheard's own agent user, a member of every project it files into. Prints the
tokens and the two settings Overheard needs. Overheard is only a client of the board: this script is the setup.

    python tools/demo_board.py [--data DIR] [--port 43917]

Needs hearthboard 0.2.0 or later (projects): installed, or a checkout in HEARTHBOARD_SRC (default: ../hearthboard).
Run it again on the same --data and it reuses the board (the tokens are only shown when they're made)."""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("HEARTHBOARD_SRC", str(Path(__file__).resolve().parents[2] / "hearthboard")))
import hearthboard as hb  # noqa: E402

TEAMS = {"benefits-processing": "Benefits Processing", "records": "Records", "portal-it": "Portal/IT",
         "congressional-affairs": "Congressional Affairs", "legal": "Legal", "fraud": "Fraud", "outreach": "Outreach"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(Path.home() / ".local" / "share" / "overheard-board"))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=43917)
    a = ap.parse_args()
    if getattr(hb, "SCHEMA_VERSION", 0) < 11:
        sys.exit("needs hearthboard 0.2.0 or later (projects)")
    store = hb.Store(a.data)
    made = {}
    if not store.users():
        made["supervisor"] = store.add_user("supervisor", "human", "demo setup", global_admin=True)[1]
        made["overheard"] = store.add_user("overheard", "agent", "demo setup")[1]
        for slug, name in TEAMS.items():
            store.create_project({"name": name, "slug": slug, "description": f"{name}: Overheard files its "
                                                                              "proposals here."}, "supervisor")
            lead = f"{slug.split('-')[0]}-lead"
            made[lead] = store.add_user(lead, "human", "demo setup")[1]
            store.set_member(slug, lead, "admin", "supervisor")
            store.set_member(slug, "overheard", "member", "supervisor")
    url = f"http://{a.host}:{a.port}"
    if made:
        print("Tokens (shown once):")
        for name, tok in made.items():
            print(f"  {name:22} {tok}")
        print(f"\nRun Overheard against it:\n  export OVERHEARD_WORKFLOW_URL={url}\n"
              f"  export OVERHEARD_WORKFLOW_TOKEN={made['overheard']}\n  overheard serve\n")
    else:
        print(f"Reusing the board in {a.data} (its tokens were shown when it was set up).")
    srv = hb.make_server(a.host, a.port, a.data)
    print(f"hearthboard on {url} (Ctrl-C to stop)", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
