#!/bin/sh
set -eu
python3 /tests/grade.py /work/answer.json /tests/gold.json /logs/verifier
