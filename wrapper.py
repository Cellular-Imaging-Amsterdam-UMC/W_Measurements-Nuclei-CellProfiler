import sys
import os
from cytomine.models import Job
from subprocess import run
from biaflows import CLASS_SPTCNT
from biaflows.helpers import BiaflowsJob, prepare_data, upload_data, upload_metrics
import time
import cellprofiler_core.pipeline
import cellprofiler_core.preferences

cellprofiler_core.preferences.set_headless()

NUCLEI_MASK_KEY = "_Nuclei_Mask"
AGGREGATES_MASK_KEY = "_Aggregates_Mask"
CELLS_MASK_KEY = "_Cells_Mask"

NAMES_AND_TYPES_MODULE_INDEX = 2

MASK_INDICES = {
    14: NUCLEI_MASK_KEY,
    20: AGGREGATES_MASK_KEY,
    32: CELLS_MASK_KEY
}

PARAMETER_SUFFIXES = {
    NUCLEI_MASK_KEY: "nuclei_mask_suffix",
    AGGREGATES_MASK_KEY: "aggregates_mask_suffix",
    CELLS_MASK_KEY: "cells_mask_suffix"
}

def parse_cellprofiler_parameters(bj, cppipe, tmpdir):
    """
    Very specific implementation just for this pipeline.
    
    Here we 'translate' the commandline args from descriptor to cpppipe text.
    """
    print(bj.__dict__, cppipe, tmpdir)

    mod_cppipe = os.path.join(tmpdir, os.path.basename(cppipe))
    
    # Load the cppipe
    pipeline = cellprofiler_core.pipeline.Pipeline()
    pipeline.load(cppipe)
    
    # Override mask names in the names_and_types module
    names_and_types_module = pipeline.modules()[NAMES_AND_TYPES_MODULE_INDEX]
    
    # Loop through mask indices to update the values
    for index, mask_key in MASK_INDICES.items():
        pipeline_value = names_and_types_module.setting(index).get_value()
        param_suffix = getattr(bj.parameters, PARAMETER_SUFFIXES[mask_key])
        new_value = pipeline_value.replace(mask_key, param_suffix)
        print(f"Changing setting at index {index}: {pipeline_value} to {new_value}")
        names_and_types_module.setting(index).set_value(new_value)
        
    # Replace 'Channel number' settings with values from metric_channels
    # channel_settings = pipeline.modules()[4]  # Assuming channels are in module 4
    # metric_channels = [int(ch) for ch in bj.parameters.metric_channels.split(',')]
    # num_channels = len(metric_channels)
    # channel_settings.setting(20).set_value(num_channels)
    # channel_settings.channels
    # for i in range(num_channels):
    #     channel_settings.setting(21 + i * 7).set_value(str(metric_channels[i]))
    

    # Save the modified pipeline to a new file
    with open(mod_cppipe, 'w+') as dumpfile:
        pipeline.dump(dumpfile)

    return mod_cppipe


def main(argv):
    """Starting point for this CellProfiler workflow.

    Args:
        argv: all the given command line arguments

    Raises:
        ValueError: If CellProfiler pipeline failed

    """    
    base_path = "{}".format(os.getenv("HOME"))  # Mandatory for Singularity
    problem_cls = CLASS_SPTCNT
    # 0. Initialize Cytomine client and job if necessary and parse inputs
    with BiaflowsJob.from_cli(argv) as bj:
        # ---------------------------------------------------------------- #
        # ----------------- SETUP ARGS & PATHS // START ----------------- ##
        # ---------------------------------------------------------------- #
        bj.job.update(status=Job.RUNNING, progress=0,
                      statusComment="Initialisation...")
        # 1. Prepare data for workflow
        in_imgs, gt_imgs, in_path, gt_path, out_path, tmp_path = prepare_data(
            problem_cls, bj, is_2d=True, **bj.flags)
        
        # MAKE SURE TMP PATH IS UNIQUE
        try:
            tmp_path += f"/{int(time.time() * 1000)}"  # timestamp in ms
            os.mkdir(tmp_path)  # setup tmp
        except FileExistsError:
            tmp_path += f"/{int(time.time() * 10000)}"  # timestamp in ms
            os.mkdir(tmp_path)  # setup tmp

        pipeline = "/app/my-wrapped-pipeline.cppipe"
        # ---------------------------------------------------------------- #
        # ----------------- SETUP ARGS & PATHS // END ------------------- ##
        # ---------------------------------------------------------------- #

        # ---------------------------------------------------------------- #
        # ------------- RUN CELLPROFILER HEADLESS // START -------------- ##
        # ---------------------------------------------------------------- #
        # 2. Run CellProfiler pipeline
        bj.job.update(progress=25, statusComment="Launching workflow...")
        
        ## If we want to allow parameters, we have to parse them into the pipeline here
        mod_pipeline = parse_cellprofiler_parameters(bj, pipeline, tmp_path)
        # mod_pipeline = pipeline

        shArgs = [
            "cellprofiler", "-c", "-r", "-p", mod_pipeline,
            "-i", in_path, "-o", out_path, "-t", tmp_path,
        ]
        status = run(" ".join(shArgs), shell=True)

        if status.returncode != 0:
            err_desc = "Failed to execute the CellProfiler pipeline: {} (return code: {})".format(
                " ".join(shArgs), status.returncode)
            bj.job.update(progress=50, statusComment=err_desc)
            raise ValueError(err_desc)
        # ---------------------------------------------------------------- #
        # ---------------- RUN CELLPROFILER HEADLESS // END ------------- ##
        # ---------------------------------------------------------------- #

        # ---------------------------------------------------------------- #
        # ------------------- BIAFLOWS BOILERPLATE // START ------------- ##
        # ---------------------------------------------------------------- #
        # 3. Upload data to BIAFLOWS
        upload_data(problem_cls, bj, in_imgs, out_path, **bj.flags, monitor_params={
            "start": 60, "end": 90, "period": 0.1,
            "prefix": "Extracting and uploading polygons from masks"})

        # 4. Compute and upload metrics
        bj.job.update(
            progress=90, statusComment="Computing and uploading metrics...")
        upload_metrics(problem_cls, bj, in_imgs, gt_path,
                       out_path, tmp_path, **bj.flags)

        # 5. Pipeline finished
        bj.job.update(progress=100, status=Job.TERMINATED,
                      status_comment="Finished.")
        # ---------------------------------------------------------------- #
        # ------------------- BIAFLOWS BOILERPLATE // END --------------- ##
        # ---------------------------------------------------------------- #


if __name__ == "__main__":
    main(sys.argv[1:])
