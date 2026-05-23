---
name: iam-permission-denied
description: Investigate AccessDenied / not-authorized errors — recently changed role policies, missing permissions, trust policy issues
---

## IAM Permission Denied Investigation

`AccessDenied` is almost always either (a) a permission that was never granted, or
(b) a permission that **changed**. The CloudTrail correlation is what turns a guess
into a root cause — always check what changed.

### Step 1 — Capture the exact denial from the logs

- `get_log_events(log_group="/aws/lambda/<fn>", filter_pattern="AccessDenied")` (or `?Denied` / `not authorized`)
- The error message names everything you need — read it precisely:
  - the **principal** ARN (`arn:aws:sts::<acct>:assumed-role/<role>/<session>`)
  - the **action** denied (e.g. `s3:ListBucket`, `dynamodb:PutItem`, `kms:Decrypt`)
  - the **resource** ARN it was acting on
- Note whether it's an explicit deny vs an implicit deny ("no identity-based policy allows")

### Step 2 — Identify the role and inspect its policies

- Pull the role name from the principal ARN in Step 1, or from `get_lambda_function_config(fn)` (the execution role)
- `get_iam_role_policies(role_name)` — list attached managed + inline policies
- Ask: does any policy grant the denied action on the denied resource? If the relevant policy is **absent**, that's the gap

### Step 3 — Check what changed (the key step)

`lookup_cloudtrail_events(hours=24)` (widen `hours` if the role was stable before), filter for:

- `DetachRolePolicy` — a managed policy was removed (very common regression)
- `DeleteRolePolicy` — an inline policy was deleted
- `PutRolePolicy` — an inline policy was rewritten (may have dropped a statement)
- `AttachRolePolicy` — a policy swapped for a narrower one
- `UpdateAssumeRolePolicy` — the trust policy changed (causes `AssumeRole` failures, not action denials)

Correlate the event timestamp with when `AccessDenied` first appeared in the logs. A
detach/put immediately before the first error is the root cause.

### Step 4 — Distinguish the denial type

- **Identity-based gap** → role simply lacks the action (fix: add it back to the role)
- **Resource policy deny** → e.g. an S3 bucket policy or KMS key policy denies the principal (check `run_bash_command("aws s3api get-bucket-policy --bucket <b>")` or `aws kms get-key-policy`)
- **Explicit deny / SCP / permissions boundary** → an org SCP or boundary blocks it even though the role allows it (deny always wins)
- **Trust policy** → `AssumeRole` itself fails; the service can't even obtain credentials

### Step 5 — Confirm scope

If a managed policy looks present but the action still denies, the resource ARN in
the policy may be too narrow (e.g. grants `arn:.../bucket` but not `arn:.../bucket/*`,
or `ListBucket` needs the bucket ARN while `GetObject` needs the object ARN).

### Common Root Causes

| Cause | Signal | Fix |
|---|---|---|
| Policy detached/deleted | `DetachRolePolicy`/`DeleteRolePolicy` in CloudTrail right before errors | Re-attach the policy (or restore the inline statement) |
| Inline policy rewritten | `PutRolePolicy` event; statement now missing | Restore the dropped statement |
| Never granted | No relevant allow in `get_iam_role_policies`; no recent change | Add a least-privilege policy for the action+resource |
| Resource-policy / KMS deny | Action allowed on role but bucket/key policy denies | Update the resource or key policy to allow the principal |
| Permissions boundary / SCP | Allow exists but still denied; org-level control | Adjust the boundary/SCP (org admin) |
| ARN scope too narrow | Policy present but resource/action mismatch | Broaden the resource ARN (e.g. add `/*` for object-level actions) |

### Mitigation Steps (read-only — document for human action)

1. **Regression (something detached/changed):** re-attach the exact policy named in the CloudTrail event — fastest, lowest-risk restore
2. **Never granted:** craft a least-privilege policy scoped to the denied action and resource ARN; attach to the role
3. **Resource policy:** add an allow for the principal in the bucket/key policy
4. **Boundary/SCP:** escalate to org/account admin — these can't be fixed at the role level
5. Verify: re-run the failing operation; confirm `AccessDenied` clears in the logs
