# Pre-push, Merge, and Release Plan

## Problem and approach

The data-model integration adds new behavior across OCR results, manual review,
batch processing, and Excel export. Before updating `main`, verify the branch
and worktree, run automated and realistic acceptance checks, confirm the
documentation and packaging contract, then use a pull request and passing CI.
After merge, prepare a feature release at version `1.1.0` and validate the
Windows release workflow before publishing its tag.

## Current-state notes

- The working tree was clean when inspected.
- Local `main` was 10 commits ahead of `origin/main`; the feature branch remote
  pointed at the same tip. Prefer a feature-branch pull request rather than
  pushing these commits directly to `main`. Recheck before proceeding.
- The full test suite had passed 66 tests in the preceding validation, but CI
  and Docker had not yet validated that commit.
- Docker was unavailable on the current Windows environment. Use the Docker
  GitHub Actions workflow or another Docker-enabled environment.
- Docker CI builds the image and checks CLI help and Tesseract, but does not
  run OCR on a PDF and verify the resulting workbook.
- `VERSION` was `1.0.5`; the planned feature release is `1.1.0`.

## Steps

1. **Confirm branch and diff safety**
   - Fetch and compare the feature tip with `origin/main`; verify the intended
     commits are included and no unrelated files, local data, credentials, or
     generated artifacts will be pushed.
   - Keep `main` protected until review and required checks pass.
2. **Run local automated checks**
   - Run the complete pytest suite from the project environment.
   - Verify headless CLI startup and inspect failures or warnings relevant to
     the model-based data flow.
3. **Perform feature acceptance checks**
   - With non-sensitive sample attendance PDFs and an explicit roster, verify
     the desktop workflow handles both confirmed and skipped review records.
   - Verify the headless workflow processes a PDF, produces a readable
     date-grouped workbook, and creates working source links.
   - Exercise missing-date and empty-input behavior and confirm errors are
     explicit rather than producing a misleading workbook.
4. **Review docs and packaging behavior**
   - Ensure user-facing documentation accurately describes model-based
     processing, headless roster requirements, dates, review state, and
     exported columns.
   - Confirm the Docker image does not rely on excluded repository data;
     supply the roster explicitly if it is not intentionally bundled.
   - Check the Windows executable workflow/package includes the runtime
     assets and data the new release requires.
5. **Push branch and open a pull request**
   - Push the feature branch, not directly to `main`.
   - Require Python CI and Docker build/smoke checks to pass on the PR.
   - Run a complete container batch against non-sensitive sample input in a
     Docker-enabled environment; verify the output workbook, since current
     Docker CI does not test a full OCR run.
   - Review and merge only after checks and acceptance results are satisfactory.
6. **Prepare and publish the feature release**
   - After merge, update `VERSION` to `1.1.0` and review release notes for the
     user-visible model integration and any known limitations.
   - Run the release workflow's tests and Windows executable build; test the
     generated executable and its roster/Tesseract requirements.
   - Push the `v1.1.0` tag only after the release artifact is verified; confirm
     the GitHub Release and uploaded executable.

## Considerations

- Avoid placing real student data in CI or shared artifacts; use synthetic or
  approved de-identified PDFs and rosters.
- The [model integration plan](./MODELS_INTEGRATION_PLAN.md) identifies known
  behavior that acceptance should cover: missing dates fail export, the headless
  CLI clears review crops, and skipped desktop-review records retain crops.
- Docker packaging and Windows PyInstaller packaging are separate targets and
  should each be validated independently.
