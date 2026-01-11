#!/bin/bash

workspace=`pwd`

# 【修改点1】启用单卡
export CUDA_VISIBLE_DEVICES="0"
gpu_num=1

# 路径配置
data_root="/home/devuser/workspace/asr/dataset/grid_device_finetune/audio_data"
train_data="${data_root}/train.jsonl"
val_data="${data_root}/val.jsonl"

# 【关键配置1】model_dir 保持指向原始底模（为了加载 tokenizer 和配置文件）
model_dir="/home/devuser/.cache/modelscope/models/iic/SenseVoiceSmall"

# 【关键配置2】新增 init_param，指向 v2 训练出的最佳权重
# 注意：这里使用了你 ls 命令中显示的路径，请确保路径完全正确
init_param="/home/devuser/workspace/asr/FunASR-main/examples/industrial_data_pretraining/sense_voice/outputs/sensevoice_finetune_v2/model.pt.best"

# 输出目录改为 v3
output_dir="./outputs/sensevoice_finetune_v3"
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

echo "🚀 启动单卡训练 (DDP) - 基于 v2 权重继续微调..."
echo "📦 基础配置: ${model_dir}"
echo "📦 加载权重: ${init_param}"

torchrun $DISTRIBUTED_ARGS \
../../../funasr/bin/train_ds.py \
++model="${model_dir}" \
++init_param="${init_param}" \
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