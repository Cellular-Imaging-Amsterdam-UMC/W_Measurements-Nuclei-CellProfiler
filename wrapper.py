import shutil
import sys
import os
from cytomine.models import Job
from subprocess import run
from biaflows import CLASS_SPTCNT
from biaflows.helpers import BiaflowsJob, prepare_data
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

    # Check if metric_channels is equal to the default value
    if bj.parameters.metric_channels == '1,2,3':
        print("Skipping channel modification since metric_channels is equal to the default value.")
    else:
        channel_settings = pipeline.modules()[4]  # Assuming channels are in module 4
        metric_channels = [int(ch) for ch in bj.parameters.metric_channels.split(',')] # split list
        num_channels = len(metric_channels) # total amount
        cur_channels = channel_settings.setting(20).get_value() # current configured
        print(f"Number of metric channels from parameters: {num_channels}")
        print(f"Current configured channels: {cur_channels}")
        # First, adjust the number of channels
        if num_channels > cur_channels:
            for _ in range(num_channels - cur_channels):
                channel_settings.add_channel()
            print(f"Added {num_channels - cur_channels} channels.")
        elif num_channels < cur_channels:
            for _ in range(cur_channels - num_channels):
                channel_settings.channels.remove(channel_settings.channels[-1])
            print(f"Removed {cur_channels - num_channels} channels.")
        # Then, set the values of the channels and their names
        images_list = []
        for i, value in enumerate(metric_channels):
            channel = channel_settings.channels[i]
            channel.channel_choice.set_value(value)
            channel_name = f'Channel{value}'
            channel.settings[2].set_value(channel_name)
            print(f"Set channel {i} to value {value} and name to '{channel_name}'.")
            images_list.append(channel_name)
        # Finally, adjust the images selected for measurement in Module MeasureObjectIntensity
        measure_object_intensity = pipeline.modules()[6]
        measure_object_intensity.images_list.set_value(images_list)

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
        timestamp = int(time.time() * 1000)
        try:            
            tmp_path += f"/{timestamp}"  # timestamp in ms
            os.mkdir(tmp_path)  # setup tmp
        except FileExistsError:
            timestamp = int(time.time() * 10000)
            tmp_path += f"/{timestamp}"  # timestamp in ms
            os.mkdir(tmp_path)  # setup tmp

        pipeline = "/app/FullMeasurementsNucleiCellAggregates.cppipe"
        # ---------------------------------------------------------------- #
        # ----------------- SETUP ARGS & PATHS // END ------------------- ##
        # ---------------------------------------------------------------- #

        # ---------------------------------------------------------------- #
        # ------------- RUN CELLPROFILER HEADLESS // START -------------- ##
        # ---------------------------------------------------------------- #
        # 2. Run CellProfiler pipeline
        bj.job.update(progress=25, statusComment="Launching workflow...")

        # If we want to allow parameters, we have to parse them into the pipeline here
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
        else:
            # Move the modified pipeline file from tmp_path to out_path
            mod_pipeline_basename = os.path.basename(mod_pipeline)
            mod_pipeline_unique_name = f"{mod_pipeline_basename[:-7]}_{timestamp}.cppipe"
            shutil.move(mod_pipeline, os.path.join(out_path, mod_pipeline_unique_name))
        # ---------------------------------------------------------------- #
        # ---------------- RUN CELLPROFILER HEADLESS // END ------------- ##
        # ---------------------------------------------------------------- #

        # ---------------------------------------------------------------- #
        # ------------------- BIAFLOWS BOILERPLATE // START ------------- ##
        # ---------------------------------------------------------------- #
        # 5. Pipeline finished
        bj.job.update(progress=100, status=Job.TERMINATED,
                      status_comment="Finished.")
        # ---------------------------------------------------------------- #
        # ------------------- BIAFLOWS BOILERPLATE // END --------------- ##
        # ---------------------------------------------------------------- #


if __name__ == "__main__":
    main(sys.argv[1:])
