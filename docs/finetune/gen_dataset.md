# sensevoice 模型微调
## 数据集准备
首先创建train.jsonl和val.jsonl 
eg  
{"key": "audio_00000", "source": "/home/devuser/workspace/asr/dataset/data/audio_files/audio_00000.wav", "source_len": 316, "target": "这个月筑阳站重过载有无异常", "target_len": 13, "text_language": "<|zh|>", "emo_target": "<|NEUTRAL|>", "event_target": "<|Speech|>", "with_or_wo_itn": "<|withitn|>"}  
其中source_len为音频文件的长度，单位为10毫秒，target_len为目标文本的长度，单位为字符数。 
字段需一致保证数据集能后正确加载   
## 微调脚本设置
微调脚本为finetune.sh，其中主要参数为：
显卡设置  
- 参数设置  
显式的设置数据集格式为“SenseVoiceCTCDataset”  
避免使用batch_type为example而是使用batch_type为token  
参考workspace\asr\FunASR-main\examples\industrial_data_pretraining\sense_voice\README_zh.md