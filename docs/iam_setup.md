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
4. Create and attach the inline policy below (see [Step 2](#step-2--iam-policy))
5. Open the user → **Security credentials → Create access key**
6. Choose **"Other"** as the use case
7. Copy the **Access key ID** and **Secret access key** — you won't see the secret again

---

## Step 2 — IAM policy

Create a **customer-managed policy** named `OpenDevOpsAgentPolicy` with this JSON:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOnlyInvestigation",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:DescribeAlarms",
        "cloudwatch:DescribeAlarmHistory",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:GetMetricData",
        "logs:DescribeLogGroups",
        "logs:FilterLogEvents",
        "logs:StartQuery",
        "logs:GetQueryResults",
        "cloudtrail:LookupEvents",
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
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EventMonitoringSetup",
      "Effect": "Allow",
      "Action": [
        "sqs:CreateQueue",
        "sqs:DeleteQueue",
        "sqs:GetQueueUrl",
        "sqs:GetQueueAttributes",
        "sqs:SetQueueAttributes",
        "sqs:ListQueues",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility",
        "sqs:SendMessage",
        "events:PutRule",
        "events:PutTargets",
        "events:ListRules",
        "events:RemoveTargets",
        "events:DeleteRule",
        "cloudwatch:PutMetricAlarm",
        "cloudwatch:DeleteAlarms"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SNSNotifications",
      "Effect": "Allow",
      "Action": [
        "sns:Publish",
        "sns:GetTopicAttributes"
      ],
      "Resource": "*"
    }
  ]
}
```

### What each block does

| Block | Purpose |
|---|---|
| `ReadOnlyInvestigation` | Read-only access to CloudWatch, CloudTrail, ECS, Lambda, EC2, RDS, IAM — used by the investigation agent tools |
| `EventMonitoringSetup` | Create/manage the SQS queue and EventBridge rules during the setup wizard; poll SQS at runtime for incoming events |
| `SNSNotifications` | Optional — publish alert summaries to an SNS topic after investigations; check topic attributes during permission check. Remove this block if you're not using SNS. |

### Minimal policy (investigation only, no event monitoring)

If you only want the chat interface and manual investigations — no automatic event detection — you can attach just the `ReadOnlyInvestigation` statement and skip the rest.

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
| SNS | No |
| CloudTrail | No |

Required services must pass for event monitoring to work. Optional services are used when available — missing permissions will simply return empty results for that service.

---

## Using an IAM role instead of a user

If running on EC2, ECS, or Lambda, attach the same policy to the instance/task role instead. Remove `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_PROFILE` from `.env` — the SDK picks up the role automatically via the instance metadata service.
