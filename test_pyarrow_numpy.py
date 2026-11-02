"""Check that pyarrow imports and exchanges data with the installed numpy.

pyarrow 26 requires NumPy 2.0 or newer, but conda-forge's pyarrow-core 26.0.0
still declares `numpy >=1.23,<3`, so the solver pairs it with NumPy 1.x and
`import pyarrow` fails with
"ImportError: pyarrow requires NumPy 2.0 or newer, found 1.26.4".
"""

import sys

import numpy as np
import pandas as pd

print(f"python {sys.version.split()[0]}")
print(f"numpy {np.__version__}")
print(f"pandas {pd.__version__}")

import pyarrow as pa

print(f"pyarrow {pa.__version__}")

values = np.arange(10, dtype="float64")

# numpy -> arrow -> numpy
array = pa.array(values)
np.testing.assert_array_equal(array.to_numpy(), values)

# arrow -> pandas -> arrow
table = pa.table({"x": values})
frame = table.to_pandas()
pd.testing.assert_series_equal(frame["x"], pd.Series(values, name="x"))
assert pa.Table.from_pandas(frame).column("x").equals(table.column("x"))

print("pyarrow works with this numpy")
