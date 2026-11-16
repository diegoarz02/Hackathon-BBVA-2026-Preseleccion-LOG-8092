#!/bin/bash
cd "$(dirname "$0")"
until python optimize2.py grid,random,sobol,tpe,cmaes 60 >> ../outputs/cache/optimize2_run.log 2>&1; do echo "REINTENTO $(date)" >> ../outputs/cache/optimize2_run.log; sleep 20; done
echo DONE_ALL >> ../outputs/cache/optimize2_run.log
