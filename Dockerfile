FROM cellprofiler/cellprofiler:4.2.6

# Install Python3.7
RUN python -m pip install --upgrade pip && python -m pip install Cython

# ------------------------------------------------------------------------------
# Install Cytomine python client
RUN python -m pip install 'git+https://github.com/cytomine-uliege/Cytomine-python-client@v2.7.3' 

# ------------------------------------------------------------------------------
# Install BIAFLOWS utilities (annotation exporter, compute metrics, helpers,...)
RUN python -m pip install 'git+https://github.com/TorecLuik/biaflows-utilities@v0.10.0'

# ------------------------------------------------------------------------------
# Add repository files: wrapper, command and descriptor
RUN mkdir /app
ADD wrapper.py /app/wrapper.py
ADD FullMeasurementsNucleiCellAggregates.cppipe /app/my-wrapped-pipeline.cppipe
ADD descriptor.json /app/descriptor.json

ENTRYPOINT ["python","/app/wrapper.py"]
