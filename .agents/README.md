# Local agent skills

The project-specific workflows in `skills/design-research/`, `skills/subtask-review/`, and `skills/superpowers/` are versioned with this repository.

Install vendor-maintained skills locally after cloning. Their sources and hashes are recorded in `../skills-lock.json`.

```sh
npx skills add runpod/skills --yes
npx skills add coderabbitai/skills --yes
```

Do not commit the downloaded vendor folders. They are intentionally ignored so a pull request stays reviewable and uses the current upstream guidance.
