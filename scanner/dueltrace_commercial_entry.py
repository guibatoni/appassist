"""Separate Windows entry point for commercial TEST builds only.

The Alpha keeps scanner/dueltrace_web_desktop.py and requires no license.
The private issuer and private signing key are NOT imported or bundled.
"""
from dueltrace_web_desktop import main


if __name__ == "__main__":
    main(commercial=True)
