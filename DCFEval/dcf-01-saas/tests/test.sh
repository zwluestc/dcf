#!/bin/sh
set -eu
python3 /tests/grade.py /work/output.xlsx /tests/answers.json /logs/verifier/details.json
