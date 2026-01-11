#!/bin/bash

workspace=`pwd`

# 【修改点1】启用单卡（你实际只用 0 号卡）
export CUDA_VISIBLE_DEVICES="0"
gpu_num=1

# 路径配置
data_root="/home/devuser/workspace/asr/dataset/data/train_grid_dataset_v2"
train_data="${data_root}/train_sensevoice.jsonl"
val_data="${data_root}/val_sensevoice.jsonl"

model_dir="/home/devuser/.cache/modelscope/models/iic/SenseVoiceSmall"
output_dir="./outputs/sensevoice_finetune_v2"
mkdir -p ${output_dir}
log_file="${output_dir}/log_ddp.txt"

# 分布式参数
DISTRIBUTED_ARGS="
    --nnodes 1 \
    --nproc_per_node $gpu_num \
    --node_rank 0 \
    --master_addr 127.0.0.1 \
    --master_port 26669
"

echo "🚀 启动单卡训练 (DDP)..."
echo "📦 使用显卡: ${CUDA_VISIBLE_DEVICES}"

torchrun $DISTRIBUTED_ARGS \
../../../funasr/bin/train_ds.py \
++model="${model_dir}" \
++train_data_set_list="${train_data}" \
++valid_data_set_list="${val_data}" \
\
++dataset="SenseVoiceCTCDataset" \
++dataset_conf.data_names='[source,target,text_language,emo_target,event_target,with_or_wo_itn]' \
\
++dataset_conf.max_source_length=500000 \
++dataset_conf.min_source_length=1 \
++dataset_conf.max_token_length=2000 \
++dataset_conf.min_token_length=1 \
\
++dataset_conf.batch_sampler="BatchSampler" \
++dataset_conf.batch_size=30000 \
++dataset_conf.batch_type="token" \
++train_conf.accum_grad=4 \
++train_conf.grad_clip=1.0 \
++dataset_conf.num_workers=4 \
\
++train_conf.max_epoch=20 \
++train_conf.log_interval=1 \
++train_conf.resume=false \
++train_conf.validate_interval=200 \
++train_conf.save_checkpoint_interval=1000 \
\
++train_conf.val_best_metric="loss" \
++train_conf.val_metric_mode="min" \
++train_conf.keep_nbest_models=10 \
++train_conf.keep_latest_models=10 \
++train_conf.avg_nbest_model=10 \
++train_conf.use_deepspeed=false \
++optim_conf.lr=0.00005 \
++output_dir="${output_dir}" 2>&1 | tee ${log_file}