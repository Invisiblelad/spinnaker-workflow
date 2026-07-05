# End-to-end: GitHub → Jenkins → Docker → Spinnaker → Kubernetes (GitOps manifests)

## What's in this folder

```
app/                    Sample Flask app + Dockerfile
Jenkinsfile             Builds, pushes the image, writes a properties file
k8s/manifest.yaml       The live manifest Spinnaker deploys from (fetched from GitHub)
spinnaker/pipeline.json Full Spinnaker pipeline definition (trigger + artifact-sourced deploy stage)
```

## How the pieces connect

1. You push code (and any changes to `k8s/manifest.yaml`) to GitHub.
2. A webhook triggers the Jenkins job.
3. Jenkins builds the Docker image, pushes it, and writes `image-info.properties`
   with the exact image/tag it just built, then archives it as a build artifact.
4. Spinnaker's Jenkins trigger reads that properties file and exposes it as
   `${trigger['properties']['KEY']}` inside the pipeline.
5. The Deploy Manifest stage fetches `k8s/manifest.yaml` **directly from your
   GitHub repo** (via its raw URL) instead of using an inline copy — this is
   the GitOps pattern. Any manifest change is just a Git commit; no need to
   touch the pipeline config itself.
6. Spinnaker evaluates the `${trigger['properties']['FULL_IMAGE']}` expression
   inside the fetched YAML at deploy time, substituting in the image Jenkins
   just pushed.

## One-time setup: enable the HTTP artifact account in Clouddriver

Spinnaker needs an artifact account capable of fetching plain HTTP(S) URLs
(raw.githubusercontent.com counts as this, since it's a public, unauthenticated
URL). Check if it's already enabled:

```bash
kubectl get cm clouddriver-4gh29tfd77 -n spinnaker -o yaml | grep -A10 artifacts
```

If nothing shows up, add it. Patch Clouddriver's ConfigMap to include:

```yaml
artifacts:
  http:
    enabled: true
    accounts:
      - name: no-auth-http-account
```

Example patch command (merge this into whatever Clouddriver's existing
`clouddriver.yml` content is — check the current ConfigMap first so you don't
overwrite the Kubernetes account config already in there):

```bash
kubectl get cm clouddriver-4gh29tfd77 -n spinnaker -o yaml
```

Add the `artifacts:` block above alongside the existing `kubernetes:` block,
then:

```bash
kubectl rollout restart deployment clouddriver -n spinnaker
```

Verify:
```bash
curl -sk -b cookies.txt "https://<url>/api/v1/artifacts/credentials" | jq
```
Should list `no-auth-http-account` with type `http`.

## Setup steps

### 1. Push this code to a GitHub repo

Keep this exact layout — `Jenkinsfile` at the repo root, `app/` and `k8s/` as
subdirectories (the pipeline's artifact reference assumes this path).

### 2. Update the raw URL in the pipeline

In `spinnaker/pipeline.json`, replace:
```
https://raw.githubusercontent.com/YOUR_GITHUB_ORG/YOUR_REPO/main/k8s/manifest.yaml
```
with your actual GitHub org/repo/branch.

### 3. Configure the GitHub webhook

Repo → Settings → Webhooks → Add webhook
- Payload URL: `http://<url>/github-webhook/`
- Content type: `application/json`
- Event: Just the push event

### 4. Create the Jenkins job

- New Item → Pipeline
- Pipeline → Definition: "Pipeline script from SCM"
- SCM: Git, point at your repo + credentials
- Script Path: `Jenkinsfile`
- Build Triggers: check "GitHub hook trigger for GITScm polling"

### 5. Add Docker registry credentials in Jenkins

Manage Jenkins → Credentials → System → Global credentials → Add Credentials
- Kind: Username with password
- ID: `docker-registry-creds` (must match the Jenkinsfile)

Edit the Jenkinsfile's `REGISTRY` and `IMAGE_NAME` to match your actual registry.

### 6. Create the `demo` namespace

```bash
kubectl create namespace demo
```

### 7. Create the Spinnaker application

In Deck: Applications → Create Application → name it `demoapp`.

### 8. Import the pipeline

```bash
curl -sk -b cookies.txt -X POST \
  https://<url>/api/v1/pipelines \
  -H "Content-Type: application/json" \
  -d @spinnaker/pipeline.json
```

### 9. Update the trigger's job name

Change `"job": "demo-app-build"` in the pipeline JSON to match your actual
Jenkins job name from step 4, then re-import (POST again — Spinnaker will
update the existing pipeline by name+application).

### 10. Test it

Push a commit → Jenkins builds and pushes an image → Spinnaker pipeline
auto-triggers → Deploy Manifest stage fetches the manifest fresh from GitHub
and applies it with the new image tag substituted in:

```bash
kubectl get pods -n demo
kubectl get deploy demo-app -n demo -o jsonpath='{.spec.template.spec.containers[0].image}'
```

## Why this is better than inline manifests

- **Manifest changes don't require touching the pipeline config** — just edit
  `k8s/manifest.yaml` and commit. Spinnaker always fetches the latest version
  from the branch/URL specified.
- **Version history lives in Git**, not buried in Spinnaker's pipeline history.
- **Code review works normally** — manifest changes go through the same PR
  process as application code.

## Notes

- `useDefaultArtifact: true` with no `usePriorArtifact`/trigger-matching means
  Spinnaker always fetches the *latest* version at the URL on every run. If you
  want to pin to a specific commit instead of always-latest `main`, point the
  URL at a specific commit SHA path instead of the branch name.
- If your GitHub repo is private, `raw.githubusercontent.com` URLs won't be
  publicly fetchable — you'd need a GitHub-specific artifact account with a
  token instead of the plain `http` account. Let me know if your repo is
  private and I'll adjust this.