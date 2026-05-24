---
name: ecs-deployment-failure
description: Investigate an ECS service that won't stabilize — failed deployments, image pull errors, crashing or unhealthy tasks
---

## ECS Deployment Failure Investigation

### Step 1 — Locate the cluster and service

- Call `list_ecs_clusters()` first — never guess cluster names
- Call `list_ecs_services(cluster)` and look for services where `running` < `desired` or `pending` > 0

### Step 2 — Read the deployment state and events

Call `describe_ecs_service(cluster, service)`. This is the highest-signal step:

- `deployments[]` — a deployment with `status: PRIMARY` that never reaches `running == desired`, or a non-zero `failed` count, means tasks keep dying or won't start
- `events[]` — the service event log is plain English and usually names the cause directly. Scan for:
  - `CannotPullContainerError` / `unable to pull` → bad image tag, missing ECR permissions, or no network path to the registry
  - `unable to place a task because no container instance met requirements` → capacity / resource constraints (EC2 launch type)
  - `task failed container health checks` / `unhealthy` → app starts then fails its health check
  - `stopped` with an exit code → the container ran and crashed

### Step 3 — Read task logs

If tasks are starting then dying, get the stdout/stderr:

- The log group is usually `/ecs/<service-name>` — confirm with `describe_log_groups(prefix="/ecs/")`
- Call `get_ecs_task_logs(cluster, task_id, log_group)` for a recently stopped task
- Look for crash-on-boot errors: missing env var, failed DB connection, port binding failure, unhandled startup exception

### Step 4 — Check what changed

Call `lookup_cloudtrail_events(hours=2)` and filter for:

- `UpdateService` — desired count, task definition, or network config changed
- `RegisterTaskDefinition` — a new task def revision (new image tag, new env, changed CPU/memory)
- `CreateDeployment` (CodeDeploy) — a blue/green deploy that may be stuck or rolling back

Correlate the timestamp with when the service stopped being healthy.

### Step 5 — For pull/network failures, verify the path

If the events show `CannotPullContainerError`:

- Confirm the image tag actually exists in the registry: `run_bash_command("aws ecr describe-images --repository-name <repo>")`
- For Fargate tasks in private subnets, a registry pull needs `assignPublicIp: ENABLED` or a NAT/VPC endpoint — a missing egress path looks identical to a missing image

### Common Root Causes

| Cause | Signal | Fix |
|---|---|---|
| Bad / missing image tag | `CannotPullContainerError`, image not in `ecr describe-images` | Push the tag or roll the task def back to a known-good revision |
| No network path to registry | `CannotPullContainerError` on Fargate in a private subnet | Enable `assignPublicIp`, add a NAT gateway, or add ECR/S3 VPC endpoints |
| App crashes on boot | Task `stopped` with non-zero exit; stack trace in task logs | Fix the startup error (env var, DB connection, port) |
| Failing health checks | Events show `unhealthy`; tasks cycle | Fix the health check path/grace period, or the app's readiness |
| Insufficient capacity (EC2) | `no container instance met requirements` | Scale the ASG, reduce task CPU/memory, or add capacity provider |
| Execution role missing ECR perms | `CannotPullContainerError` with AccessDenied | Attach `AmazonECSTaskExecutionRolePolicy` to the execution role |

### Mitigation Steps (read-only — document for human action)

1. **Bad deploy:** roll the service back to the previous task definition revision (`update-service --task-definition <family>:<prev-revision>`)
2. **Image pull:** push the correct tag, or fix the subnet/egress so the registry is reachable
3. **Crash on boot:** ship a fix for the startup error surfaced in task logs; redeploy
4. **Health checks:** widen the health-check grace period if the app is slow to start, or correct the health-check endpoint
5. After any fix, watch `describe_ecs_service` until a single PRIMARY deployment reaches `running == desired`
