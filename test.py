from pathlib import Path
import subprocess
import sys
import asyncio

script = Path(__file__).resolve().parent / "CommunicationsModule/CommunicationsProtocol/DatalinkLayer/TXFLOWG.py"
GNURADIO_ENV = "C:/ProgramData/radioconda/python.exe"



async def main():

    print("running main")
    proc = subprocess.Popen(
        [str(GNURADIO_ENV), str(script)],
        cwd=str(script.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    for line in proc.stdout:
        print(line, end="")


if __name__ == '__main__':
        asyncio.run(main())