#!/bin/bash
set -e
pip install -q "paddlepaddle==3.0.0"
python -c "import paddle; print('ok', paddle.__version__)"
