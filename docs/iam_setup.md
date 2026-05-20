# IAM Setup Guide

This guide covers how to create an AWS IAM user (or role) with the permissions OpenDevOps Agent needs, and how to plug the credentials into your environment.

---

## Credential options

| Method | When to use |
|---|---|
| **IAM user + access key** | Self-hosted server, Docker, Railway, Render, local dev without AWS CLI profiles |
| **Named profile** (`~/.aws/credentials`) | Local dev with AWS CLI already configured |
| **IAM role** | EC2 / ECS / Lambda — attach the role to the instance/task, no keys needed |

For a typical self-hosted deployment, create an IAM user and paste the keys into `.env`.

---

## Step 1 — Create the IAM user

1. Open **IAM → Users → Create user** in the AWS console
2. Username: `opendevops-agent` (or any name you prefer)
3. Select **"Attach policies directly"**
4. Create and attach **both** customer-managed policies from [Step 2](#step-2--iam-policies) below
5. Open the user → **Security credentials → Create access key**
6. Choose **"Other"** as the use case
7. Copy the **Access key ID** and **Secret access key** — you won't see the secret again

If you only want the chat interface and manual investigations (no event-driven monitoring), attach only **Policy 1** and skip Policy 2.

---

## Step 2 — IAM policies

Two policies keep the least-privilege boundary clean:

- **Policy 1 (Operational)** — read access across all resources, plus runtime SQS queue polling on the specific event queue. Required for all OpenDevOps features.
- **Policy 2 (Setup)** — write actions scoped to `opendevops-*` resources only. Required only if you use the Settings → AWS Configuration setup wizard to create SQS/EventBridge/CloudWatch infrastructure.

### Policy 1 — OpenDevOpsAgentOperational

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadAll",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:DescribeAlarms",
        "cloudwatch:DescribeAlarmHistory",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:GetMetricData",
        "cloudwatch:ListMetrics",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:FilterLogEvents",
        "logs:GetLogEvents",
        "logs:StartQuery",
        "logs:StopQuery",
        "logs:GetQueryResults",
        "cloudtrail:LookupEvents",
        "cloudtrail:GetTrailStatus",
        "ecs:ListClusters",
        "ecs:DescribeClusters",
        "ecs:ListServices",
        "ecs:DescribeServices",
        "ecs:ListTasks",
        "ecs:DescribeTasks",
        "lambda:ListFunctions",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "rds:DescribeDBInstances",
        "rds:DescribeEvents",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "sts:GetCallerIdentity",
        "sqs:ListQueues",
        "sqs:GetQueueUrl",
        "sqs:GetQueueAttributes",
        "events:ListRules",
        "events:DescribeRule",
        "events:ListTargetsByRule"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SQSConsume",
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility"
      ],
      "Resource": "arn:aws:sqs:*:*:opendevops-agent-events"
    }
  ]
}
```

### Policy 2 — OpenDevOpsAgentSetup

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SQSSetup",
      "Effect": "Allow",
      "Action": [
        "sqs:CreateQueue",
        "sqs:DeleteQueue",
        "sqs:SetQueueAttributes",
        "sqs:SendMessage"
      ],
      "Resource": "arn:aws:sqs:*:*:opendevops-*"
    },
    {
      "Sid": "EventBridgeSetup",
      "Effect": "Allow",
      "Action": [
        "events:PutRule",
        "events:PutTargets",
        "events:RemoveTargets",
        "events:DeleteRule"
      ],
      "Resource": "arn:aws:events:*:*:rule/opendevops-*"
    },
    {
      "Sid": "CloudWatchAlarmSetup",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricAlarm",
        "cloudwatch:DeleteAlarms"
      ],
      "Resource": "arn:aws:cloudwatch:*:*:alarm:opendevops-*"
    }
  ]
}
```

### What each block does

| Block | Policy | Purpose |
|---|---|---|
| `ReadAll` | Operational | Read access across CloudWatch, logs, CloudTrail, ECS, Lambda, EC2, RDS, IAM, STS, SQS, EventBridge — used by all investigation tools and bash-based AWS CLI calls |
| `SQSConsume` | Operational | Polls `opendevops-agent-events` at runtime for incoming EventBridge events |
| `SQSSetup` | Setup | Creates and tears down the SQS queue and DLQ; sends test events via the pipeline test script |
| `EventBridgeSetup` | Setup | Creates and tears down the 9 EventBridge rules that forward AWS events to SQS |
| `CloudWatchAlarmSetup` | Setup | Creates and tears down the aggregate `opendevops-lambda-errors-aggregate` CloudWatch alarm |

**Why reads use `*`:** The agent can issue arbitrary AWS CLI commands via its bash tool. Scoping reads to specific resource ARNs would silently break any investigation that touches a resource not on the allowlist. Write actions are scoped to `opendevops-*` because the app only creates infrastructure under that prefix and nothing else.

### Minimal policy (investigation only, no event monitoring)

If you only want the chat interface and manual investigations — no automatic event detection — attach only **Policy 1** (`ReadAll` + `SQSConsume`). The `SQSConsume` statement is harmless if you never create the queue.

---

## Step 3 — Add credentials to `.env`

```bash
# Option A — explicit keys (server, Docker, CI)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# Option B — named profile (local dev)
AWS_PROFILE=opendevops-agent
AWS_REGION=us-east-1
```

For Option B, add a profile to `~/.aws/credentials`:

```ini
[opendevops-agent]
aws_access_key_id = AKIA...
aws_secret_access_key = ...
```

---

## Step 4 — Verify in the setup wizard

After starting the app, the setup wizard's **Step 3 (Permission Check)** calls each service with a lightweight read and shows a pass/fail result for:

| Service | Required |
|---|---|
| CloudWatch | Yes |
| Lambda | Yes |
| SQS | Yes |
| EventBridge | Yes |
| ECS | No |
| RDS | No |
| EC2 | No |
| IAM / STS | No |
| CloudTrail | No |

Required services must pass for event monitoring to work. Optional services are used when available — missing permissions will simply return empty results for that service.

---

## Using an IAM role instead of a user

If running on EC2, ECS, or Lambda, attach the same policies to the instance/task role instead. Remove `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_PROFILE` from `.env` — the SDK picks up the role automatically via the instance metadata service.
