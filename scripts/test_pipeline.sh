#!/usr/bin/env bash
# test_pipeline.sh — spin up a real Lambda that errors, push it through the monitoring pipeline.
#
# Usage:
#   bash scripts/test_pipeline.sh                        # run test
#   bash scripts/test_pipeline.sh --region=eu-west-1    # override region
#   bash scripts/test_pipeline.sh --invocations=10      # more errors
#   bash scripts/test_pipeline.sh --cleanup FUNCTION ROLE  # tear down after test

set -euo pipefail

# ── colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
die()  { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

# ── cleanup mode ─────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--cleanup" ]]; then
  FUNCTION_NAME="${2:-}"; ROLE_NAME="${3:-}"
  [[ -z "$FUNCTION_NAME" || -z "$ROLE_NAME" ]] && die "Usage: $0 --cleanup FUNCTION_NAME ROLE_NAME"
  REGION="${AWS_REGION:-us-east-1}"
  warn "Deleting Lambda: $FUNCTION_NAME"
  aws lambda delete-function --function-name "$FUNCTION_NAME" --region "$REGION" 2>/dev/null && log "Lambda deleted" || warn "Already gone"
  warn "Deleting IAM role: $ROLE_NAME"
  aws iam detach-role-policy --role-name "$ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" 2>/dev/null || true
  aws iam delete-role --role-name "$ROLE_NAME" 2>/dev/null && log "Role deleted" || warn "Already gone"
  log "Cleanup done."
  exit 0
fi

# ── config ────────────────────────────────────────────────────────────────────
REGION="${AWS_REGION:-us-east-1}"
INVOCATIONS=5

for arg in "$@"; do
  case $arg in
    --region=*)      REGION="${arg#*=}" ;;
    --invocations=*) INVOCATIONS="${arg#*=}" ;;
  esac
done

SUFFIX=$(date +%s)
FUNCTION_NAME="opendevops-test-error-${SUFFIX}"
ROLE_NAME="opendevops-test-role-${SUFFIX}"

# ── find SQS queue URL ────────────────────────────────────────────────────────
QUEUE_URL=""
if [[ -f "data/init.json" ]]; then
  QUEUE_URL=$(python3 -c "import json; d=json.load(open('data/init.json')); print(d.get('sqs_queue_url',''))" 2>/dev/null || echo "")
fi
if [[ -z "$QUEUE_URL" ]]; then
  QUEUE_URL="${SQS_QUEUE_URL:-}"
fi
if [[ -z "$QUEUE_URL" ]]; then
  die "No SQS queue URL found. Run 'Create Infrastructure' in Settings → AWS Configuration first."
fi

log "Region    : $REGION"
log "Queue     : $QUEUE_URL"
log "Function  : $FUNCTION_NAME"
echo ""

# ── create IAM role ────────────────────────────────────────────────────────────
log "Creating IAM execution role..."
TRUST_POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

ROLE_ARN=$(aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document "$TRUST_POLICY" \
  --query 'Role.Arn' \
  --output text)

aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

log "Role ARN  : $ROLE_ARN"
log "Waiting 10s for IAM role to propagate..."
sleep 10

# ── create Lambda ZIP ─────────────────────────────────────────────────────────
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

cat > "$TMP_DIR/index.py" << 'PYEOF'
import random

ERRORS = [
    "Connection pool exhausted: all 100 connections in use by active queries",
    "DynamoDB ProvisionedThroughputExceededException on table 'orders' — read capacity 0/500 RCU remaining",
    "Downstream service timeout: payments-service did not respond within 29000ms",
    "Redis READONLY error: connected to replica — write commands not accepted",
    "JWT verification failed: token expired 3601s ago (iat=1715000000)",
    "Unhandled exception: Cannot read property 'userId' of undefined at processOrder:47",
    "Out of memory: Lambda allocated 128 MB, peak usage 129 MB — increase memory limit",
]

def handler(event, context):
    error = random.choice(ERRORS)
    raise RuntimeError(f"[TEST FAILURE] {error}")
PYEOF

(cd "$TMP_DIR" && zip -q function.zip index.py)

# ── deploy Lambda ─────────────────────────────────────────────────────────────
log "Deploying Lambda function..."
aws lambda create-function \
  --function-name "$FUNCTION_NAME" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler index.handler \
  --zip-file "fileb://$TMP_DIR/function.zip" \
  --region "$REGION" \
  --timeout 10 \
  --output text > /dev/null

aws lambda wait function-active \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION"

log "Lambda deployed."

# ── invoke it to generate real errors + CloudWatch logs ───────────────────────
log "Invoking $INVOCATIONS times to generate real errors..."
for i in $(seq 1 "$INVOCATIONS"); do
  aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --payload '{"test": true}' \
    --invocation-type RequestResponse \
    --region "$REGION" \
    /tmp/lambda-out.json > /dev/null 2>&1 || true
  printf "  invocation %d/%d\n" "$i" "$INVOCATIONS"
done

log "Errors written to CloudWatch Logs: /aws/lambda/$FUNCTION_NAME"
echo ""

# ── push real event to SQS ────────────────────────────────────────────────────
# Uses the real function name so the agent can look up actual CloudWatch logs.
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

EVENT=$(cat << EOF
{
  "source": "aws.cloudwatch",
  "detail-type": "CloudWatch Alarm State Change",
  "time": "${NOW}",
  "region": "${REGION}",
  "detail": {
    "alarmName": "${FUNCTION_NAME}-errors",
    "state": {
      "value": "ALARM",
      "reason": "Threshold Crossed: ${INVOCATIONS} error datapoints in the last 1 minute (threshold: 1)."
    },
    "configuration": {
      "metrics": [{
        "metricStat": {
          "metric": {
            "namespace": "AWS/Lambda",
            "name": "Errors",
            "dimensions": {"FunctionName": "${FUNCTION_NAME}"}
          },
          "period": 60,
          "stat": "Sum"
        }
      }]
    }
  }
}
EOF
)

log "Sending event to SQS..."
MSG_ID=$(aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body "$EVENT" \
  --region "$REGION" \
  --query 'MessageId' \
  --output text)

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Pipeline triggered${NC}"
echo "  MessageId : $MSG_ID"
echo "  Function  : $FUNCTION_NAME"
echo "  Real logs : CloudWatch → /aws/lambda/$FUNCTION_NAME"
echo "  Monitoring: http://localhost/monitoring"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
warn "The agent will pull REAL CloudWatch logs from that function."
warn "Investigation takes ~30–90s. Watch the Monitoring page."
echo ""
echo -e "To clean up when done:"
echo -e "  ${YELLOW}bash scripts/test_pipeline.sh --cleanup $FUNCTION_NAME $ROLE_NAME${NC}"
