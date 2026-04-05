@echo off
wsl -d Ubuntu -e bash -lc "source ~/.venvs/hunyuan/bin/activate && export VLLM_CACHE_ROOT=/home/mike/vllm_cache && mkdir -p /home/mike/vllm_cache && exec vllm serve tencent/HunyuanOCR --host 0.0.0.0 --port 8001 --served-model-name hunyuanocr --no-enable-prefix-caching --mm-processor-cache-gb 0 --gpu-memory-utilization 0.2 --max-model-len 360 --max-num-seqs 16 --max-num-batched-tokens 1024 --dtype auto --calculate-kv-scales --enable-chunked-prefill --generation-config vllm"
pause
