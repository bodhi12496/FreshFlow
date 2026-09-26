# Update your existing FreshFlow repository

Download `FreshFlow-phase2.zip` to Downloads. Open the terminal in your existing
FreshFlow repository (the same folder used for your Phase 1 commit). Do not clone
another repository or run `git init`.

## 1. Extract and copy, including hidden files

```bash
unzip -o ~/Downloads/FreshFlow-phase2.zip -d ~/Downloads/FreshFlow-phase2 &&
cp -R ~/Downloads/FreshFlow-phase2/FreshFlow/. .
```

This copies the updated README, workflow, Phase 2 implementation, documentation
and result snapshots. The ZIP contains no `.git` directory, so your commit
history is preserved. It includes the Phase 1 files from your GitHub repository.
If you have edited those files since that commit, review your changes before
replacing them with the bundle.

## 2. Create a Python environment and install dependencies

Use Python 3.12:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If `python3 --version` shows another version and Python 3.12 is installed, use
`python3.12 -m venv .venv` for the environment-creation command instead.
On later terminal sessions, activate the environment again before running Phase 2.

## 3. Verify and run

```bash
python -m unittest -v
python phase2.py --smoke
python phase2.py
```

The full run prints progress for 24 folds, then its report. The smoke run is only
a quick integration check. Inspect the full output in `artifacts/phase2/report.md`.
If a command fails, resolve the error before committing.

## 4. Stage, review, commit and push

```bash
git diff --check
git add phase2.py test_phase2.py phase2_protocol.json requirements.txt README.md UPDATE_PHASE2.md .github/workflows/ci.yml docs reports
git --no-pager diff --cached --stat
git status
git commit -m "Add Phase 2 gradient boosting and paired forecast evaluation"
git push origin main
```

The `.venv/`, `artifacts/` and Python cache folders stay ignored. The committed
`reports/phase2/` snapshot contains the supplied full-run results; running the
script does not automatically replace that checked-in snapshot. If you change
the experiment, update its report snapshot deliberately and disclose the new
settings rather than presenting it as the original frozen experiment.
