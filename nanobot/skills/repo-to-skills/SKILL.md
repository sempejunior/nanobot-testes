---
name: repo-to-skills
description: "Analyze a GitHub repository or local codebase and generate reusable agent skills from its features and behaviors. Use when the user provides a repo URL or code and asks to learn from, replicate, extract skills from, or understand what a codebase does."
metadata: {"nanobot":{"requires":{"bins":["git"]}}}
---

# Repo to Skills

Analyze a codebase and generate agent skills that replicate its key behaviors.

## Workflow

### 1. Acquire the code

Read the workspace path from the "Your workspace is at:" line in the system prompt. Build a working directory path: `<workspace>/.repo-analysis/repo-<timestamp>` where `<timestamp>` is a Unix epoch second value.

**Important:** Each `exec` call runs in an isolated shell — variables do not persist between calls. Resolve the full literal path once (e.g. `/home/user/.nanobot/workspace/.repo-analysis/repo-1717000000`) and reuse that exact string in every subsequent `exec` call. Do not rely on `$REPO_DIR` across calls.

```bash
mkdir -p <REPO_DIR>
```

**From a GitHub URL:**

```bash
git clone --depth 1 --single-branch <url> <REPO_DIR>/src
```

If the clone fails with an authentication error (private repo), ask the user for a GitHub personal access token (classic PAT with `repo` scope, or fine-grained with read access). Then clone with the token embedded in the URL:

```bash
git clone --depth 1 --single-branch https://<token>@github.com/owner/repo.git <REPO_DIR>/src
```

Token safety:
- Advise the user to create a short-lived token and revoke it after use.
- Never pass the raw token to `save_memory`.
- Never echo or log the token in output.

**From a local directory:** skip cloning, use the provided path directly as SRC_DIR.

### 2. Map the project structure

SRC_DIR is `<REPO_DIR>/src` (or the local path for local directories).

**Pass 1 -- File tree:**

```bash
find <SRC_DIR> -maxdepth 3 -type f -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/__pycache__/*' -not -path '*/vendor/*' -not -path '*/.venv/*' | head -100
```

Read key files if they exist: `README.md`, `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `pom.xml`, `Makefile`, `docker-compose.yml`.

**Pass 2 -- Size check:**

```bash
find <SRC_DIR> -type f \( -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.go" -o -name "*.rs" -o -name "*.java" \) -not -path '*/node_modules/*' -not -path '*/.git/*' | wc -l
```

If more than 200 source files, focus only on README, main entry point, and top-level module index files. Read at most 15-20 key files total. Skip test files and generated code.

**Pass 3 -- Feature identification:**

Read main entry points, route handlers, and module index files. For each distinct feature or behavior, note:
- Feature name (e.g., "PIX payment", "OTP verification", "webhook handler")
- Which files implement it
- External APIs or dependencies it uses
- Input/output contract

### 3. Generate skill drafts

For each identified feature, write a skill body following this structure:

```markdown
# <Feature Name>

<What this does and when to use it -- one paragraph. Written as instructions for an LLM agent, not as human documentation.>

## Steps

### 1. Setup
<scaffolding: directories, config files, dependency install commands>

### 2. Core logic
<the algorithm, data flow, API calls -- with simplified code examples from the repo>

### 3. Integration
<how to wire it in -- routes, event handlers, CLI commands, cron>

### 4. Verification
<how to test -- example inputs, expected outputs, curl commands>

## Key Patterns
- <Pattern with concise code example>

## Pitfalls
- <Edge case or common mistake found in the codebase>
```

When calling `save_skill`, pass these parameters:
- `skill_name`: lowercase hyphen-separated (e.g. `pix-payment`)
- `skill_description`: a sentence describing what the skill does AND when to trigger it -- this is the primary trigger mechanism, so be comprehensive (e.g. "Handle PIX payments via API. Use when the user asks to integrate PIX, generate QR codes, or process instant payments.")
- `skill_content`: the markdown body above -- do NOT include YAML frontmatter, it is added automatically

Guidelines:
- Keep each skill under 300 lines.
- Prefer simplified/cleaned-up code patterns over raw copy-paste.
- The skill should teach the pattern, not reproduce the exact code.
- Include actual API endpoints, data structures, and auth flows found in the repo.

### 4. Present for approval

Present skills to the user **one at a time**:

```
I analyzed the repository and found N features. Here are the skills:

---
Skill 1/N: <skill-name>
<description>

<full content -- truncated to first 40 lines if long, with "[... N more lines]">

Options:
1. Save this skill
2. Edit (tell me what to change)
3. Skip
---
```

Wait for the user to respond before showing the next skill.

- "save" / "yes" / "1" --> call `save_skill(skill_name=..., skill_description=..., skill_content=...)`
- "edit" / "2" --> apply requested changes, show updated version, ask again
- "skip" / "no" / "3" --> move to next skill
- "save all" --> save all remaining skills without further prompts

**Never save a skill without user confirmation.**

### 5. Cleanup

After all skills are presented, remove the working directory:

```bash
find <REPO_DIR> -delete
```

Use the literal REPO_DIR path from step 1.

### 6. Summary

```
Analysis complete:
- Repository: <url or path>
- Features found: N
- Skills saved: <list>
- Skills skipped: <list>
- Cleanup: done
```

Save a concise memory entry (never include tokens or credentials):

```
save_memory(fact="- Analyzed repo github.com/owner/repo: generated skills [skill-a, skill-b]")
```

## Edge Cases

**Large repos (>200 source files):** Read at most 15-20 key files. Prioritize README, entry points, and module indexes. Skip test files and generated code.

**Monorepos:** Detect via `packages/`, `apps/`, `services/`, or multiple manifest files (`package.json`, `go.mod`). Ask the user which package to analyze, or analyze the top-level packages as separate batches.

**Non-code repos:** If the repo has no source files, inform the user and offer to generate skills from documentation instead.

**Binary-heavy repos:** Skip binary files (images, compiled assets). Focus on source and config.

**Clone timeout:** If clone times out, suggest providing the code as a local directory instead.
