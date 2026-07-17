import os
import sys

os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")

print("python", sys.version)
print("trying import paddle...")
import paddle

print("ok", paddle.__version__)
