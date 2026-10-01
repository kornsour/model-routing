"""Hidden grader: DEPLOY_RUNNER_CLASS conversion (exp06 stratum A, harvested brief).

Evaluates each job's runs-on expression over a grid of contexts with a
small GitHub-expression interpreter, so a guard counts as preserved when it
still gates the self-hosted branch, whatever its spelling.
"""

import itertools
import json
import re
from pathlib import Path

import yaml

ROOT = Path.cwd()
SPEC = json.loads('{"orig": {"Copperline/.github-private/.github/workflows/neon-preview.yml": "name: neon-preview\\non:\\n  pull_request:\\n    types: [opened, synchronize, closed]\\npermissions:\\n  contents: read\\n  id-token: write\\njobs:\\n  branch:\\n    # Holds a Neon API key: routed by DEPLOY_RUNNER_CLASS so it lands on the\\n    # ephemeral pool (runner destroyed after one job) or GitHub-hosted, never\\n    # on the persistent pool.\\n    runs-on: ${{ fromJSON(vars.DEPLOY_RUNNER_CLASS == \'ephemeral\' && vars.USE_SELF_HOSTED_RUNNER == \'true\' && github.event.repository.private && \'[\\"self-hosted\\",\\"Linux\\",\\"container\\"]\' || vars.DEPLOY_RUNNER_CLASS == \'self-hosted\' && vars.USE_SELF_HOSTED_RUNNER == \'true\' && github.event.repository.private && \'[\\"self-hosted\\",\\"Linux\\"]\' || \'[\\"ubuntu-latest\\"]\') }}\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - run: ./tools/neon-branch.sh \\"${{ github.event.pull_request.number }}\\"\\n", "Copperline/binwise/.github/workflows/aws-deploy-staging.yml": "name: AWS deploy (staging)\\non:\\n  push:\\n    branches: [main]\\n  workflow_dispatch:\\npermissions:\\n  contents: read\\n  id-token: write\\nconcurrency:\\n  group: aws-deploy-staging.yml-${{ github.repository }}\\n  cancel-in-progress: false\\njobs:\\n  deploy:\\n    # DELIBERATELY GitHub-hosted, NOT routed through USE_SELF_HOSTED_RUNNER.\\n    # This job assumes the production staging deploy role via OIDC; a persistent\\n    # self-hosted runner could keep that token around between jobs.\\n    runs-on: ubuntu-latest # allow-bare-runner: holds production AWS credentials\\n    environment: staging\\n    if: github.ref == \'refs/heads/main\'\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - uses: aws-actions/configure-aws-credentials@b47578312673ae6fa5b5096b330d9fbac3d116df # v4.2.1\\n        with:\\n          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}\\n          aws-region: us-east-2\\n      - run: ./scripts/deploy-aws.sh staging\\n", "Copperline/binwise/.github/workflows/aws-deploy.yml": "name: AWS deploy\\non:\\n  push:\\n    branches: [main]\\n  workflow_dispatch:\\npermissions:\\n  contents: read\\n  id-token: write\\nconcurrency:\\n  group: aws-deploy.yml-${{ github.repository }}\\n  cancel-in-progress: false\\njobs:\\n  deploy:\\n    # DELIBERATELY GitHub-hosted, NOT routed through USE_SELF_HOSTED_RUNNER.\\n    # This job assumes the production AWS deploy role via OIDC; a persistent\\n    # self-hosted runner could keep that token around between jobs.\\n    runs-on: ubuntu-latest # allow-bare-runner: holds production AWS credentials\\n    environment: production\\n    if: github.ref == \'refs/heads/main\'\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - uses: aws-actions/configure-aws-credentials@b47578312673ae6fa5b5096b330d9fbac3d116df # v4.2.1\\n        with:\\n          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}\\n          aws-region: us-east-2\\n      - run: ./scripts/deploy-aws.sh production\\n", "Copperline/binwise/.github/workflows/ci.yml": "name: ci\\non:\\n  pull_request:\\n  push:\\n    branches: [main]\\njobs:\\n  ci:\\n    uses: Copperline/.github-private/.github/workflows/ci.yml@6c1d2a9e0f4b3c8d7e5a1f2b9c0d4e6a8b7f3c21 # main\\n", "Copperline/cohort/.github/workflows/aws-deploy.yml": "name: AWS deploy\\non:\\n  push:\\n    branches: [main]\\n  workflow_dispatch:\\npermissions:\\n  contents: read\\n  id-token: write\\nconcurrency:\\n  group: aws-deploy.yml-${{ github.repository }}\\n  cancel-in-progress: false\\njobs:\\n  deploy:\\n    # DELIBERATELY GitHub-hosted, NOT routed through USE_SELF_HOSTED_RUNNER.\\n    # This job assumes the production AWS deploy role via OIDC; a persistent\\n    # self-hosted runner could keep that token around between jobs.\\n    runs-on: ubuntu-latest # allow-bare-runner: holds production AWS credentials\\n    environment: production\\n    if: github.ref == \'refs/heads/main\'\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - uses: aws-actions/configure-aws-credentials@b47578312673ae6fa5b5096b330d9fbac3d116df # v4.2.1\\n        with:\\n          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}\\n          aws-region: us-east-2\\n      - run: ./scripts/deploy-aws.sh production\\n", "Copperline/cohort/.github/workflows/ci.yml": "name: ci\\non:\\n  pull_request:\\n  push:\\n    branches: [main]\\njobs:\\n  ci:\\n    uses: Copperline/.github-private/.github/workflows/ci.yml@6c1d2a9e0f4b3c8d7e5a1f2b9c0d4e6a8b7f3c21 # main\\n", "Copperline/echoform/.github/workflows/aws-deploy.yml": "name: AWS deploy\\non:\\n  push:\\n    branches: [main]\\n  workflow_dispatch:\\npermissions:\\n  contents: read\\n  id-token: write\\nconcurrency:\\n  group: aws-deploy.yml-${{ github.repository }}\\n  cancel-in-progress: false\\njobs:\\n  deploy:\\n    # DELIBERATELY GitHub-hosted, NOT routed through USE_SELF_HOSTED_RUNNER.\\n    # This job assumes the production AWS deploy role via OIDC; a persistent\\n    # self-hosted runner could keep that token around between jobs.\\n    runs-on: ubuntu-latest # allow-bare-runner: holds production AWS credentials\\n    environment: production\\n    if: github.ref == \'refs/heads/main\'\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - uses: aws-actions/configure-aws-credentials@b47578312673ae6fa5b5096b330d9fbac3d116df # v4.2.1\\n        with:\\n          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}\\n          aws-region: us-east-2\\n      - run: ./scripts/deploy-aws.sh production\\n", "Copperline/echoform/.github/workflows/ci.yml": "name: ci\\non:\\n  pull_request:\\n  push:\\n    branches: [main]\\njobs:\\n  ci:\\n    uses: Copperline/.github-private/.github/workflows/ci.yml@6c1d2a9e0f4b3c8d7e5a1f2b9c0d4e6a8b7f3c21 # main\\n", "Copperline/echoform/.github/workflows/provision-support-group.yml": "name: Provision support group\\non:\\n  workflow_dispatch:\\n    inputs:\\n      confirm:\\n        description: Type the repository name to confirm\\n        required: true\\npermissions:\\n  contents: read\\n  id-token: write\\njobs:\\n  provision:\\n    # Defense in depth: only a manual dispatch of this exact repository\'s main\\n    # branch may reach the self-hosted pool; anything else runs GitHub-hosted.\\n    runs-on: ${{ fromJSON(vars.USE_SELF_HOSTED_RUNNER == \'true\' && github.event_name == \'workflow_dispatch\' && github.repository == \'Copperline/echoform\' && github.event.repository.private && github.ref == \'refs/heads/main\' && \'[\\"self-hosted\\",\\"Linux\\",\\"X64\\",\\"wsl\\"]\' || \'[\\"ubuntu-latest\\"]\') }}\\n    environment: production\\n    if: inputs.confirm == github.event.repository.name\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - uses: google-github-actions/auth@ba79af03959ebeac9769e648f473a284504d9193 # v2.1.10\\n        with:\\n          workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}\\n          service_account: ${{ vars.WORKSPACE_SA_EMAIL }}\\n      - run: node scripts/provision-support-group.mjs\\n", "Copperline/gatefit/.github/workflows/ci.yml": "name: ci\\non:\\n  pull_request:\\n  push:\\n    branches: [main]\\njobs:\\n  ci:\\n    uses: Copperline/.github-private/.github/workflows/ci.yml@6c1d2a9e0f4b3c8d7e5a1f2b9c0d4e6a8b7f3c21 # main\\n", "Copperline/gatefit/.github/workflows/sst-deploy.yml": "name: SST deploy\\non:\\n  workflow_dispatch:\\npermissions:\\n  contents: read\\n  id-token: write\\njobs:\\n  deploy:\\n    # Defense in depth: dispatch-only, this repository, main only.\\n    runs-on: ${{ fromJSON(vars.USE_SELF_HOSTED_RUNNER == \'true\' && github.event_name == \'workflow_dispatch\' && github.repository == \'Copperline/gatefit\' && github.event.repository.private && github.ref == \'refs/heads/main\' && \'[\\"self-hosted\\",\\"Linux\\",\\"X64\\",\\"wsl\\"]\' || \'[\\"ubuntu-latest\\"]\') }}\\n    environment: production\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - uses: aws-actions/configure-aws-credentials@b47578312673ae6fa5b5096b330d9fbac3d116df # v4.2.1\\n        with:\\n          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}\\n          aws-region: us-east-2\\n      - run: pnpm sst deploy --stage production\\n", "Copperline/mise/.github/workflows/catalog-production-sync.yml": "name: Catalog production sync\\non:\\n  schedule:\\n    - cron: \'15 6 * * *\'\\n  workflow_dispatch:\\npermissions:\\n  contents: read\\n  id-token: write\\nconcurrency:\\n  group: catalog-production-sync.yml-${{ github.repository }}\\n  cancel-in-progress: false\\njobs:\\n  deploy:\\n    # DELIBERATELY GitHub-hosted, NOT routed through USE_SELF_HOSTED_RUNNER.\\n    # This job assumes the production catalog sync role via OIDC; a persistent\\n    # self-hosted runner could keep that token around between jobs.\\n    runs-on: ubuntu-latest # allow-bare-runner: holds production AWS credentials\\n    environment: production\\n    if: github.ref == \'refs/heads/main\'\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - run: node scripts/catalog-sync.mjs --env production\\n        env:\\n          CATALOG_API_TOKEN: ${{ secrets.CATALOG_API_TOKEN }}\\n", "Copperline/mise/.github/workflows/ci.yml": "name: ci\\non:\\n  pull_request:\\n  push:\\n    branches: [main]\\njobs:\\n  ci:\\n    uses: Copperline/.github-private/.github/workflows/ci.yml@6c1d2a9e0f4b3c8d7e5a1f2b9c0d4e6a8b7f3c21 # main\\n", "Copperline/mise/.github/workflows/deploy-production.yml": "name: Deploy production\\non:\\n  push:\\n    branches: [main]\\n  workflow_dispatch:\\npermissions:\\n  contents: read\\n  id-token: write\\nconcurrency:\\n  group: deploy-production.yml-${{ github.repository }}\\n  cancel-in-progress: false\\njobs:\\n  build:\\n    runs-on: ${{ fromJSON(vars.USE_SELF_HOSTED_RUNNER == \'true\' && github.event.repository.private && \'[\\"self-hosted\\",\\"Linux\\"]\' || \'[\\"ubuntu-latest\\"]\') }}\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - run: pnpm install --frozen-lockfile && pnpm build\\n  deploy:\\n    # DELIBERATELY GitHub-hosted, NOT routed through USE_SELF_HOSTED_RUNNER.\\n    # This job assumes the production AWS deploy role via OIDC; a persistent\\n    # self-hosted runner could keep that token around between jobs.\\n    runs-on: ubuntu-latest # allow-bare-runner: holds production AWS credentials\\n    needs: build\\n    environment: production\\n    if: github.ref == \'refs/heads/main\'\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - uses: aws-actions/configure-aws-credentials@b47578312673ae6fa5b5096b330d9fbac3d116df # v4.2.1\\n        with:\\n          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}\\n          aws-region: us-east-2\\n      - run: ./scripts/deploy-aws.sh production\\n", "Copperline/mise/.github/workflows/ingredient-storage-production-sync.yml": "name: Ingredient storage sync\\non:\\n  schedule:\\n    - cron: \'45 6 * * *\'\\n  workflow_dispatch:\\npermissions:\\n  contents: read\\n  id-token: write\\nconcurrency:\\n  group: ingredient-storage-production-sync.yml-${{ github.repository }}\\n  cancel-in-progress: false\\njobs:\\n  deploy:\\n    # DELIBERATELY GitHub-hosted, NOT routed through USE_SELF_HOSTED_RUNNER.\\n    # This job assumes the production storage sync role via OIDC; a persistent\\n    # self-hosted runner could keep that token around between jobs.\\n    runs-on: ubuntu-latest # allow-bare-runner: holds production AWS credentials\\n    environment: production\\n    if: github.ref == \'refs/heads/main\'\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - run: node scripts/storage-sync.mjs --env production\\n", "Copperline/packlight/.github/workflows/aws-deploy.yml": "name: AWS deploy\\non:\\n  push:\\n    branches: [main]\\n  workflow_dispatch:\\npermissions:\\n  contents: read\\n  id-token: write\\nconcurrency:\\n  group: aws-deploy.yml-${{ github.repository }}\\n  cancel-in-progress: false\\njobs:\\n  migrate:\\n    # DELIBERATELY GitHub-hosted, NOT routed through USE_SELF_HOSTED_RUNNER.\\n    # Runs production migrations with the database URL secret.\\n    runs-on: ubuntu-latest # allow-bare-runner: holds the production database URL\\n    environment: production\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - run: pnpm db:deploy\\n        env:\\n          DATABASE_URL: ${{ secrets.DATABASE_URL }}\\n  deploy:\\n    # DELIBERATELY GitHub-hosted, NOT routed through USE_SELF_HOSTED_RUNNER.\\n    # This job assumes the production AWS deploy role via OIDC; a persistent\\n    # self-hosted runner could keep that token around between jobs.\\n    runs-on: ubuntu-latest # allow-bare-runner: holds production AWS credentials\\n    needs: migrate\\n    environment: production\\n    if: github.ref == \'refs/heads/main\'\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - uses: aws-actions/configure-aws-credentials@b47578312673ae6fa5b5096b330d9fbac3d116df # v4.2.1\\n        with:\\n          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}\\n          aws-region: us-east-2\\n      - run: ./scripts/deploy-aws.sh production\\n", "Copperline/packlight/.github/workflows/ci.yml": "name: ci\\non:\\n  pull_request:\\n  push:\\n    branches: [main]\\njobs:\\n  ci:\\n    uses: Copperline/.github-private/.github/workflows/ci.yml@6c1d2a9e0f4b3c8d7e5a1f2b9c0d4e6a8b7f3c21 # main\\n", "Copperline/platewise/.github/workflows/aws-deploy.yml": "name: AWS deploy\\non:\\n  push:\\n    branches: [main]\\n  workflow_dispatch:\\npermissions:\\n  contents: read\\n  id-token: write\\nconcurrency:\\n  group: aws-deploy.yml-${{ github.repository }}\\n  cancel-in-progress: false\\njobs:\\n  deploy:\\n    # DELIBERATELY GitHub-hosted, NOT routed through USE_SELF_HOSTED_RUNNER.\\n    # This job assumes the production AWS deploy role via OIDC; a persistent\\n    # self-hosted runner could keep that token around between jobs.\\n    runs-on: ubuntu-latest # allow-bare-runner: holds production AWS credentials\\n    environment: production\\n    if: github.ref == \'refs/heads/main\'\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - uses: aws-actions/configure-aws-credentials@b47578312673ae6fa5b5096b330d9fbac3d116df # v4.2.1\\n        with:\\n          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}\\n          aws-region: us-east-2\\n      - run: ./scripts/deploy-aws.sh production\\n", "Copperline/platewise/.github/workflows/ci.yml": "name: ci\\non:\\n  pull_request:\\n  push:\\n    branches: [main]\\njobs:\\n  ci:\\n    uses: Copperline/.github-private/.github/workflows/ci.yml@6c1d2a9e0f4b3c8d7e5a1f2b9c0d4e6a8b7f3c21 # main\\n", "Copperline/platewise/.github/workflows/provision-workspace-domain.yml": "name: Provision workspace domain\\non:\\n  workflow_dispatch:\\n    inputs:\\n      confirm:\\n        description: Type the repository name to confirm\\n        required: true\\npermissions:\\n  contents: read\\n  id-token: write\\njobs:\\n  provision:\\n    # Defense in depth: only a manual dispatch of this exact repository\'s main\\n    # branch may reach the self-hosted pool; anything else runs GitHub-hosted.\\n    runs-on: ${{ fromJSON(vars.USE_SELF_HOSTED_RUNNER == \'true\' && github.event_name == \'workflow_dispatch\' && github.repository == \'Copperline/platewise\' && github.event.repository.private && github.ref == \'refs/heads/main\' && \'[\\"self-hosted\\",\\"Linux\\",\\"X64\\",\\"wsl\\"]\' || \'[\\"ubuntu-latest\\"]\') }}\\n    environment: production\\n    if: inputs.confirm == github.event.repository.name\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - uses: google-github-actions/auth@ba79af03959ebeac9769e648f473a284504d9193 # v2.1.10\\n        with:\\n          workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}\\n          service_account: ${{ vars.WORKSPACE_SA_EMAIL }}\\n      - run: node scripts/provision-domain.mjs\\n", "Copperline/trailhead/.github/workflows/ci.yml": "name: ci\\non:\\n  pull_request:\\n  push:\\n    branches: [main]\\njobs:\\n  ci:\\n    uses: Copperline/.github-private/.github/workflows/ci.yml@6c1d2a9e0f4b3c8d7e5a1f2b9c0d4e6a8b7f3c21 # main\\n", "Copperline/trailhead/.github/workflows/provision-support-group.yml": "name: Provision support group\\non:\\n  workflow_dispatch:\\n    inputs:\\n      confirm:\\n        description: Type the repository name to confirm\\n        required: true\\npermissions:\\n  contents: read\\n  id-token: write\\njobs:\\n  provision:\\n    # Defense in depth: only a manual dispatch of this exact repository\'s main\\n    # branch may reach the self-hosted pool; anything else runs GitHub-hosted.\\n    runs-on: ${{ fromJSON(vars.USE_SELF_HOSTED_RUNNER == \'true\' && github.event_name == \'workflow_dispatch\' && github.repository == \'Copperline/trailhead\' && github.event.repository.private && github.ref == \'refs/heads/main\' && \'[\\"self-hosted\\",\\"Linux\\",\\"X64\\",\\"wsl\\"]\' || \'[\\"ubuntu-latest\\"]\') }}\\n    environment: production\\n    if: inputs.confirm == github.event.repository.name\\n    steps:\\n      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0\\n      - uses: google-github-actions/auth@ba79af03959ebeac9769e648f473a284504d9193 # v2.1.10\\n        with:\\n          workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}\\n          service_account: ${{ vars.WORKSPACE_SA_EMAIL }}\\n      - run: node scripts/provision-support-group.mjs\\n"}, "a": ["Copperline/mise/.github/workflows/deploy-production.yml", "Copperline/mise/.github/workflows/catalog-production-sync.yml", "Copperline/mise/.github/workflows/ingredient-storage-production-sync.yml", "Copperline/binwise/.github/workflows/aws-deploy.yml", "Copperline/packlight/.github/workflows/aws-deploy.yml", "Copperline/platewise/.github/workflows/aws-deploy.yml", "Copperline/echoform/.github/workflows/aws-deploy.yml", "Copperline/cohort/.github/workflows/aws-deploy.yml"], "b": {"Copperline/trailhead/.github/workflows/provision-support-group.yml": "Copperline/trailhead", "Copperline/platewise/.github/workflows/provision-workspace-domain.yml": "Copperline/platewise", "Copperline/echoform/.github/workflows/provision-support-group.yml": "Copperline/echoform", "Copperline/gatefit/.github/workflows/sst-deploy.yml": "Copperline/gatefit"}}')
CANON = (
    "${{ fromJSON(vars.DEPLOY_RUNNER_CLASS == 'ephemeral' && vars.USE_SELF_HOSTED_RUNNER == 'true' "
    "&& github.event.repository.private && '[\"self-hosted\",\"Linux\",\"container\"]' || "
    "vars.DEPLOY_RUNNER_CLASS == 'self-hosted' && vars.USE_SELF_HOSTED_RUNNER == 'true' && "
    "github.event.repository.private && '[\"self-hosted\",\"Linux\"]' || '[\"ubuntu-latest\"]') }}"
)
EPHEMERAL = ["self-hosted", "Linux", "container"]
HOSTED = ["ubuntu-latest"]


# ----------------------------------------------------------------- evaluator
_TOKEN = re.compile(r"\s*(\|\||&&|==|!=|!|\(|\)|,|'(?:[^']|'')*'|[A-Za-z_][\w.\-]*|-?\d+)")


def _tokens(src):
    pos, out = 0, []
    src = src.strip()
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m:
            raise ValueError(f"cannot parse expression at {src[pos:pos + 20]!r}")
        out.append(m.group(1))
        pos = m.end()
    return out


def _lookup(path, ctx):
    value = ctx
    for part in path.split("."):
        value = value.get(part, "") if isinstance(value, dict) else ""
    return value


def _truthy(v):
    return bool(v) and v != "false" if not isinstance(v, str) else v != ""


def _eq(a, b):
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    return a == b


def evaluate(expr, ctx):
    toks = _tokens(expr)
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take():
        pos[0] += 1
        return toks[pos[0] - 1]

    def primary():
        t = take()
        if t == "(":
            v = or_()
            assert take() == ")"
            return v
        if t == "!":
            return not _truthy(primary())
        if t.startswith("'"):
            return t[1:-1].replace("''", "'")
        if t in ("true", "false"):
            return t == "true"
        if peek() == "(":
            take()
            args = [] if peek() == ")" else [or_()]
            while peek() == ",":
                take()
                args.append(or_())
            assert take() == ")"
            if t.lower() == "fromjson":
                return json.loads(args[0])
            raise ValueError(f"unsupported function {t}")
        return _lookup(t, ctx)

    def cmp_():
        left = primary()
        while peek() in ("==", "!="):
            op = take()
            right = primary()
            left = _eq(left, right) if op == "==" else not _eq(left, right)
        return left

    def and_():
        left = cmp_()
        while peek() == "&&":
            take()
            right = cmp_()
            left = right if _truthy(left) else left
        return left

    def or_():
        left = and_()
        while peek() == "||":
            take()
            right = and_()
            left = left if _truthy(left) else right
        return left

    value = or_()
    assert pos[0] == len(toks), f"trailing tokens in {expr!r}"
    return value


def runs_on(value, ctx):
    if isinstance(value, list):
        return value
    m = re.fullmatch(r"\s*\$\{\{(.*)\}\}\s*", value, re.S)
    if not m:
        return [value]
    result = evaluate(m.group(1), ctx)
    return result if isinstance(result, list) else [result]


def contexts(repo):
    for use, cls, private, event, repository, ref in itertools.product(
        ("true", "false", ""),
        ("ephemeral", "self-hosted", "hosted", ""),
        (True, False),
        ("workflow_dispatch", "push"),
        (repo, "Copperline/elsewhere"),
        ("refs/heads/main", "refs/heads/feature"),
    ):
        yield {
            "vars": {"USE_SELF_HOSTED_RUNNER": use, "DEPLOY_RUNNER_CLASS": cls},
            "github": {
                "event": {"repository": {"private": private}},
                "event_name": event,
                "repository": repository,
                "ref": ref,
            },
        }


# ----------------------------------------------------------------- helpers
def _jobs(text):
    return yaml.safe_load(text)["jobs"]


def _strip_runs_on(doc):
    for job in doc["jobs"].values():
        job.pop("runs-on", None)
    return doc


def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


def _pinned_jobs(path):
    return [name for name, job in _jobs(SPEC["orig"][path]).items() if job.get("runs-on") == "ubuntu-latest"]


# ----------------------------------------------------------------- tests
def test_only_runner_selection_and_comments_changed():
    for path, original in SPEC["orig"].items():
        now = (ROOT / path).read_text()
        assert _strip_runs_on(yaml.safe_load(now)) == _strip_runs_on(yaml.safe_load(original)), (
            f"{path}: something other than runs-on changed"
        )


def test_files_nobody_owns_are_untouched():
    owned = set(SPEC["a"]) | set(SPEC["b"])
    for path, original in SPEC["orig"].items():
        if path not in owned:
            assert (ROOT / path).read_text() == original, f"{path} is not yours to edit"


def test_case_a_uses_the_canonical_expression_verbatim():
    for path in SPEC["a"]:
        jobs = _jobs((ROOT / path).read_text())
        for name in _pinned_jobs(path):
            assert _norm(str(jobs[name]["runs-on"])) == _norm(CANON), f"{path}:{name} runs-on is not the canonical expression"


def test_case_a_markers_removed_and_comment_rewritten():
    for path in SPEC["a"]:
        text = (ROOT / path).read_text()
        assert "allow-bare-runner" not in text, f"{path} still carries an allow-bare-runner marker"
        assert "DELIBERATELY GitHub-hosted" not in text, f"{path} still says the job is deliberately GitHub-hosted"
        comments = " ".join(line for line in text.splitlines() if line.strip().startswith("#"))
        assert "DEPLOY_RUNNER_CLASS" in comments or "ephemeral" in comments.lower(), (
            f"{path}: the comment above runs-on does not explain the new routing"
        )


def test_case_b_guards_preserved_and_ephemeral_selected():
    for path, repo in SPEC["b"].items():
        jobs = _jobs((ROOT / path).read_text())
        for name, job in jobs.items():
            reached_ephemeral = False
            for ctx in contexts(repo):
                labels = runs_on(job["runs-on"], ctx)
                g = ctx["github"]
                guards = (
                    ctx["vars"]["USE_SELF_HOSTED_RUNNER"] == "true"
                    and g["event_name"] == "workflow_dispatch"
                    and g["repository"] == repo
                    and g["event"]["repository"]["private"]
                    and g["ref"] == "refs/heads/main"
                )
                if labels != HOSTED:
                    assert guards, f"{path}:{name} reaches {labels} without every original guard ({ctx})"
                    assert "wsl" not in labels, f"{path}:{name} still selects the persistent wsl pool"
                if guards and ctx["vars"]["DEPLOY_RUNNER_CLASS"] == "ephemeral":
                    assert labels == EPHEMERAL, f"{path}:{name} gives {labels} for an ephemeral dispatch"
                    reached_ephemeral = True
                if ctx["vars"]["DEPLOY_RUNNER_CLASS"] in ("", "hosted"):
                    assert labels == HOSTED, f"{path}:{name} leaves GitHub-hosted without DEPLOY_RUNNER_CLASS"
            assert reached_ephemeral
