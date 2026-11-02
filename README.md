# Investigate pyarrow, numpy and polars dependency problems

Test suite for two problems that broke the CI of
[RESKit PR #375](https://github.com/FZJ-IEK3-VSA/RESKit/pull/375) at the start of November 2026:

1. `ImportError: pyarrow requires NumPy 2.0 or newer, found 1.26.4` on the GitHub-hosted runners.
2. `Fatal Python error: Illegal instruction` while importing polars on the self-hosted runner.

The first one is a missing constraint in the conda-forge repodata and can be fixed with a repodata patch
([`repodata_patch/pyarrow.yaml`](repodata_patch/pyarrow.yaml)). It is investigated here.
The second one needs the self-hosted runner, so it is investigated in
[FZJ-IEK3-VSA/test_polars](https://github.com/FZJ-IEK3-VSA/test_polars).

## pyarrow-core 26.0.0 allows NumPy 1.x

- pyarrow 26.0.0 needs NumPy 2.0 or newer when numpy is installed. numpy itself stays optional.
  The check is in [`pyarrow/lib.pyx`](https://github.com/apache/arrow/blob/apache-arrow-26.0.0/python/pyarrow/lib.pyx#L40-L44)
  and was added on purpose ([apache/arrow#48473](https://github.com/apache/arrow/issues/48473)).
- The PyPI wheel cannot express "optional, but >=2.0 if installed", so it declares nothing
  ([apache/arrow#53954](https://github.com/apache/arrow/issues/53954)).
  conda can, with `constrains` (`run_constrained` in a recipe).
- conda-forge's pyarrow-core 26.0.0 still has `constrains: numpy >=1.23,<3`, the same as 25.x.
  All 53 builds (py311 to py315, linux-64, linux-aarch64, linux-ppc64le, osx-64, osx-arm64, win-64, build 0) are affected.
  The [pyarrow-feedstock recipe](https://github.com/conda-forge/pyarrow-feedstock/blob/main/recipe/meta.yaml) ignores numpy's
  run-export and hard-codes this line. The 26.0.0 update did not change it.
- So the solver pairs pyarrow 26.0.0 with NumPy 1.26.4, even when pyarrow is not pinned:

  ```shell
  mamba create --dry-run -n test python=3.12 pyarrow "numpy>=1.26.0,<=1.26.4" pandas
  # + numpy          1.26.4
  # + pyarrow        26.0.0
  # + pyarrow-core   26.0.0
  ```

  RESKit pins `numpy <=1.26.4` and gets pyarrow through `wisdem` → `wombat` → `pyarrow`.

**Fix:** change the constraint to `numpy >=2.0,<3`
- for the existing packages with the repodata patch in [`repodata_patch/pyarrow.yaml`](repodata_patch/pyarrow.yaml),
  to be appended to `recipe/patch_yaml/pyarrow.yaml` of
  [conda-forge-repodata-patches-feedstock](https://github.com/conda-forge/conda-forge-repodata-patches-feedstock).
  [`repodata_patch/show_diff_result.txt`](repodata_patch/show_diff_result.txt) is the output of the feedstock's
  `show_diff.py`: exactly the 53 pyarrow-core 26.0.0 records change, nothing else.
- for future builds in `run_constrained` of the pyarrow-feedstock recipe, see
  [`repodata_patch/pyarrow-feedstock.diff`](repodata_patch/pyarrow-feedstock.diff).

Dry-run solves (win-64) against a local channel with the patched repodata:

| Specs (with `python=3.12 pandas`) | Today | With the patch |
|---|---|---|
| `pyarrow "numpy>=1.26.0,<=1.26.4"` | pyarrow-core 26.0.0, broken | pyarrow-core 25.0.1 |
| `pyarrow=26.0.0 numpy=1.26.4` | pyarrow-core 26.0.0, broken | refused: `numpy >=2.0,<3` conflicts |
| `pyarrow numpy=2.5.4` | pyarrow-core 26.0.0 | pyarrow-core 26.0.0 |

## Test suite

Like [investigate_scipy_interpolate](https://github.com/julian-belina/investigate_scipy_interpolate), every job
creates a fresh conda-forge environment with `mamba create`, prints it with `mamba list` and runs a plain Python script.

| File | What it does |
|---|---|
| [`.github/workflows/test_pyarrow_numpy.yml`](.github/workflows/test_pyarrow_numpy.yml) | pyarrow × numpy × OS. Dry-run solve first: if the solver refuses the combination the job passes with a notice (the repodata constrains it). Otherwise install and run `test_pyarrow_numpy.py`. A red job means the solver accepts a broken combination. |
| [`test_pyarrow_numpy.py`](test_pyarrow_numpy.py) | Imports pyarrow, converts numpy ↔ arrow ↔ pandas. |
| [`repodata_patch/pyarrow.yaml`](repodata_patch/pyarrow.yaml) | Draft repodata patch for pyarrow-core 26.0.0. |

### Expected results

All 36 matrix cells solve on linux-64, osx-arm64 and win-64 (checked with dry runs).

Today the 6 jobs with numpy 1.26.4 and pyarrow `26.0.0` or `any` fail on every OS, because the solver picks
pyarrow-core 26.0.0. Once the repodata patch is live, `26.0.0` + `1.26.4` passes with the notice "solver refuses",
and `any` + `1.26.4` passes with pyarrow 25.0.1.
