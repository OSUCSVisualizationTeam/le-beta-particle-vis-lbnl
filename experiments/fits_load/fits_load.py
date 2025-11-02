from ccdioutils import CCDCapture
import matplotlib.pyplot as plt
from sys import argv, stderr
from pathlib import Path


if __name__ == "__main__":
    kevFactor = 1.02857e-5
    input = Path(argv[1])
    if not input.exists():
        print(f"File {argv[1]} not found or not a file", file=stderr)
        exit(1)
    dumps = CCDCapture.load(input)
    for dump in dumps:
        data = kevFactor * dump.rawData()
        plt.matshow(data, cmap="Greys_r")
        print(f"HDU: {dump.info()}")
        plt.title(f"HDU: {dump.info().captureDate()}")
    plt.show()
