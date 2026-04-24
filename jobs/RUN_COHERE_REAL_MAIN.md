Submit from the terminal/session where `COHERE_API_KEY` is set:

`sbatch --export=ALL jobs/cohere_real_model_main_20260424.sbatch`

Monitor:

`squeue -j <JOBID>`

`tail -f logs/slurm/cohere_real_main_<JOBID>.out`

`tail -f logs/slurm/cohere_real_main_<JOBID>.err`
