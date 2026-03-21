# sourcing-command-deck

Private repo for the first runnable web entry of the buying-plan sourcing workflow.

## What it does
- Upload planning `.xlsx`
- Trigger existing sourcing workflow
- Poll job status
- Render a visual dashboard entry page

## Local run
```bash
python3 apps/server.py
```

Then open:
```text
http://127.0.0.1:8765
```

## Notes
This first version is intentionally lightweight and uses Python standard library only.
