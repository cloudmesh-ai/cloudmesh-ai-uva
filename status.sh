#!/bin/bash

NODE="udc-an26-1"

echo "======================================"
echo " SLURM NODE REPORT: $NODE"
echo "======================================"

########################################
# NODE INFO (CPUs, Memory, GPUs)
########################################

NODE_INFO=$(scontrol show node "$NODE")

CFG_CPU=$(echo "$NODE_INFO" | grep -oP 'CPUTot=\K[0-9]+')
CFG_MEM_MB=$(echo "$NODE_INFO" | grep -oP 'RealMemory=\K[0-9]+')
CFG_GPU=$(echo "$NODE_INFO" | grep -oP 'Gres=.*gpu.*?:\K[0-9]+' | head -n1)

ALLOC_CPU=$(echo "$NODE_INFO" | grep -oP 'CPUAlloc=\K[0-9]+')
ALLOC_MEM_MB=$(echo "$NODE_INFO" | grep -oP 'AllocMem=\K[0-9]+')
ALLOC_GPU=$(echo "$NODE_INFO" | grep -oP 'AllocTRES=.*gres/gpu=\K[0-9]+' | head -n1)

# Defaults if empty
ALLOC_CPU=${ALLOC_CPU:-0}
ALLOC_MEM_MB=${ALLOC_MEM_MB:-0}
CFG_GPU=${CFG_GPU:-0}
ALLOC_GPU=${ALLOC_GPU:-0}

FREE_CPU=$((CFG_CPU - ALLOC_CPU))
FREE_MEM_MB=$((CFG_MEM_MB - ALLOC_MEM_MB))
FREE_GPU=$((CFG_GPU - ALLOC_GPU))

echo ""
echo "---- RESOURCE SUMMARY ----"
echo "CPUs:   used=$ALLOC_CPU / total=$CFG_CPU / free=$FREE_CPU"
echo "Mem:    used=$((ALLOC_MEM_MB/1024))GB / total=$((CFG_MEM_MB/1024))GB / free=$((FREE_MEM_MB/1024))GB"
echo "GPUs:   used=$ALLOC_GPU / total=$CFG_GPU / free=$FREE_GPU"

########################################
# INTEGRATED JOB LIST (STATUS + RESOURCES)
########################################

echo ""
echo "---- ACTIVE JOBS & RESOURCE ALLOCATION ----"
# Format: ID, User, State, Time, CPUs, Memory, GPUs/GRES
printf "%-10s %-12s %-5s %-10s %-5s %-10s %-15s\n" "JOBID" "USER" "ST" "TIME" "CPUS" "MEM" "GRES"
echo "--------------------------------------------------------------------------------"

squeue -w "$NODE" -h -o "%i %u %t %M %C %m %b" | while read JOBID USER ST TIME CPUS MEM GRES
do
    # Replace (null) with 'none' for cleaner output if no GRES
    GRES_VAL=${GRES:-"none"}
    printf "%-10s %-12s %-5s %-10s %-5s %-10s %-15s\n" "$JOBID" "$USER" "$ST" "$TIME" "$CPUS" "$MEM" "$GRES_VAL"
done

########################################
# PENDING JOBS (Waiting in Queue)
########################################

echo ""
echo "---- PENDING JOBS (Top 10) ----"
squeue -t PD -o "%.10i %.12u %.5t %.10M %.20R" | head -n 11


echo ""
echo "Done."