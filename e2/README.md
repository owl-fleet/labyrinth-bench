# e2/ — frozen MMLU seed list

`mmlu_seed_list.json` is a stratified 150-item subset of MMLU, frozen before any run that uses it (the generating script, selection seed, and dataset revision are pinned in the file's `meta` block and in `make_mmlu_seed_list.py`).

**Attribution:** the questions are from MMLU — Hendrycks et al. (2021), *Measuring Massive Multitask Language Understanding* — redistributed under the MIT license via the Hugging Face dataset `cais/mmlu` (revision pinned in `meta.dataset_revision`).
