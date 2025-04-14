#!/bin/bash
nohup python -u run.py \
    --test_file ./data/tasks_test.jsonl \
    --api_key YOUR_OPENAI_API_KEY \
    --headless \
    --max_iter 15 \
    --max_attached_imgs 3 \
    --temperature 1 \
    --fix_box_color \
    --seed 42 > test_tasks.log &

python run.py --test_file ./data/tasks_test.jsonl --api_key "your_api_key" --max_iter 15 --max_attached_imgs 3 --temperature 1 --seed 42 --start_maximized --trajectory --error_max_reflection_iter 3
