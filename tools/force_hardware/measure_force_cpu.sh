#!/usr/bin/env bash
# Read-only controlled-state CPU sampling. The operator changes MPC state manually.
set -euo pipefail

host=${1:-akai-force}
samples=${2:-60}
interval=${3:-1}
warmup=${4:-15}
output=${5:-"force-cpu-qa-$(date -u +%Y%m%dT%H%M%SZ).csv"}
[[ $host =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "invalid SSH host alias" >&2; exit 2; }
for number in "$samples" "$interval" "$warmup"; do
  [[ $number =~ ^[0-9]+$ ]] || { echo "sample count, interval and warmup must be integers" >&2; exit 2; }
done
(( samples >= 10 && interval >= 1 && warmup >= 5 )) || { echo "use at least 10 samples, 1 second interval and 5 seconds warmup" >&2; exit 2; }
[[ ! -e $output ]] || { echo "output already exists: $output" >&2; exit 2; }

printf 'state,sample,mpc_cpu_pct,system_idle_pct\n' > "$output"
states=(bypass hall_reverb 8_voice_chor pitch_shift)
for state in "${states[@]}"; do
  echo "Set the same MPC project, playback loop, routing and level; select state: $state"
  read -r -p "When steady playback is running, press Enter to sample $state (Ctrl-C cancels): " _
  echo "Sampling $state: warmup ${warmup}s, then ${samples} samples at ${interval}s."
  ssh "$host" sh -s -- "$samples" "$interval" "$warmup" <<'REMOTE' |
set -eu
samples=$1
interval=$2
warmup=$3
top -b -n "$((samples + warmup))" -d "$interval" |
awk -v warmup="$warmup" '
  /^CPU:/ { idle=""; for (i=1;i<=NF;i++) if ($i=="idle") idle=$(i-1) }
  /\/usr\/bin\/MPC/ {
    cpu=$7
    if (cpu!="" && idle!="") {
      gsub("%", "", cpu); gsub("%", "", idle); snapshot++
      if (snapshot>warmup) print snapshot-warmup "," cpu "," idle
      cpu=""; idle=""
    }
  }
'
REMOTE
  while IFS=, read -r sample cpu idle; do
    [[ -n $sample && -n $cpu && -n $idle ]] || continue
    printf '%s,%s,%s,%s\n' "$state" "$sample" "$cpu" "$idle" >> "$output"
  done
done
echo "Wrote read-only CPU samples to $output"
echo "Rows recorded: $(( $(wc -l < "$output") - 1 ))"
