# W_Measurements-Nuclei-CellProfiler

Batch feature extraction for 2D fluorescence images using **CellProfiler 4.2.6**, designed for datasets that already have two pre-segmented object masks — one for nuclei and one for cells.

The workflow runs a headless CellProfiler pipeline (`FullMeasurementsNucleiCell.cppipe`) and writes per-object CSV tables containing morphology features (area, perimeter, shape descriptors, texture) and per-channel intensity statistics for every detected nucleus and cell.

## What you need

Before running this workflow you must have:

- **Input images** — 2D fluorescence images (TIFF or compatible) placed in the input folder.
- **A Nuclei mask per image** — a greyscale label image where each nucleus is a distinct integer value (e.g. produced by a prior segmentation workflow). The filename must share the same base name as the input image and end with the configured nuclei suffix (default: `_Nuclei_Mask`).
- **A Cell mask per image** — same convention, ending with the configured cells suffix (default: `_Cells_Mask`).

All three files (original image + both masks) must live in the same input folder.

## Outputs

Per-object CSV files are written to the output folder:

| CSV file | Contents |
|----------|----------|
| `Nuclei.csv` | One row per nucleus — shape, size, texture, intensity per channel |
| `Cells.csv` | One row per cell — shape, size, texture, intensity per channel |
| `Image.csv` | Per-image aggregate statistics |
| `Experiment.csv` | Run-level metadata |
| `*.cppipe` | Copy of the modified pipeline used (for reproducibility) |

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `nuclei_mask_suffix` | `_Nuclei_Mask` | Filename suffix that identifies nuclei mask images |
| `cells_mask_suffix` | `_Cells_Mask` | Filename suffix that identifies cell mask images |
| `metric_channels` | `1,2,3` | Comma-separated list of channel indices (1-based) to include in intensity measurements |

> **`metric_channels` note:** The default assumes a 3-channel RGB image. For a single-channel image use `1`; for a 4-channel image use `1,2,3,4`. Channel indices map directly to the channel order in your source image.

## BIOMERO compatibility

This workflow is [BIOMERO](https://github.com/NL-BioImaging/biomero)-compatible and can be launched from the OMERO web interface on a SLURM cluster. BIOMERO handles fetching input images and masks from OMERO, dispatching the job, and uploading the output CSVs back. To register it, follow the standard BIOMERO software-registration steps using the `descriptor.json` from this repository.

## Technical notes (for developers)

This workflow uses the [BIAFLOWS](https://biaflows.neubias.org/) framework:

- **Entry point:** `wrapper.py` — initialises a `BiaflowsJob`, modifies the `.cppipe` file at runtime to inject the configured suffixes and channel list, then runs CellProfiler headless.
- **Pipeline patching:** The `.cppipe` is loaded via `cellprofiler_core`; the `NamesAndTypes` module settings are updated in-memory with user-configured suffixes, and channel modules are added or removed to match `metric_channels`.
- **CSV post-processing:** A type-hint row is prepended to each output CSV so OMERO tables can infer column types on import.
- **Container base:** `cellprofiler/cellprofiler:4.2.6`
- **BIAFLOWS utilities:** [`biaflows-utilities@v0.10.0`](https://github.com/TorecLuik/biaflows-utilities)
