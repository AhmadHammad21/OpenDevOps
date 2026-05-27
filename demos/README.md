# OpenDevOps Agent — Demo Scenarios

Reproducible cloud incidents for demoing / recording the agent. Each script breaks something in
**your** cloud account in a controlled, reversible way; you then point the agent at it and watch it
investigate. Everything is read-only on the agent side, and every script has a `teardown` action.

| Cloud | Folder | Scenarios |
|---|---|---|
| **AWS** | [`aws/`](./aws) | Lambda throttling/errors, CloudWatch alarms, bad deploys, ECS image pull, DynamoDB throttle, IAM regression, VPC egress — 9 cases |
| **Azure** | [`azure/`](./azure) | VM deallocated, App Service 5xx (port mismatch), AKS CrashLoopBackOff — 3 cases |

See each folder's `README.md` for prerequisites, the scenario index, and exact run commands:
- **AWS:** [`demos/aws/README.md`](./aws/README.md) — boto3 scripts (`uv run python demos/aws/<script>.py setup`)
- **Azure:** [`demos/azure/README.md`](./azure/README.md) — `az` CLI scripts (`python demos/azure/<script>.py setup`)

> ⚠️ **These create real cloud resources.** Most cases are a few cents, but the ECS (AWS) and AKS
> (Azure) cases run managed compute that bills while up. **Always run `teardown`** when done, and use
> a sandbox / dev subscription.

## Recording GIFs / short demos

Tips for capturing crisp, small demo GIFs (OBS → trim → ffmpeg palette) live in the
[AWS README](./aws/README.md#recording-gifs--short-demos) — they apply to both clouds. The key shot
either way: the streaming response + the tool-call inspector expanding to reveal which `aws`/`az`/
`kubectl` calls ran, ending on the structured root-cause block.
