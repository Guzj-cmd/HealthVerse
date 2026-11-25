# HealthVerse 姿态模型训练与测试

本目录不是页面演示数据，而是一套可复现的模型训练、独立测试和导出管线。输入是 MediaPipe 的 33 个人体关键点；模型预测项目定义的姿态类别，例如 `upright`、`forward_head`、`lean_left`。类别必须来自具有授权和标注说明的数据集，或由参与者知情同意后采集。

## 数据格式

推荐 JSONL，每行一个样本：

```json
{"sample_id":"p01-0001","subject_id":"p01","label":"upright","source":"session-01","landmarks":[{"x":0.5,"y":0.2,"z":-0.1,"visibility":0.99}]}
```

`landmarks` 必须包含 33 点。CSV 也受支持，元数据列为 `sample_id,subject_id,label,source`，关键点列为 `x0,y0,z0,v0` 到 `x32,y32,z32,v32`。

## 采集真实数据

```powershell
python capture_dataset.py --source 0 --subject-id p01 --label upright --output data/posture.jsonl
python capture_dataset.py --source session.mp4 --subject-id p02 --label forward_head --output data/posture.jsonl
```

相邻视频帧高度相关，不能把帧随机拆到训练集和测试集。训练脚本按 `subject_id` 分组切分，任何受试者只会进入一个分区。

## 训练与独立测试

```powershell
python -m pip install -r requirements.txt
python train.py --data data/posture.jsonl --dataset-manifest data/posture.capture-metrics.json --config config.json --output runs/posture
```

脚本比较 Logistic Regression、Random Forest 和 Histogram Gradient Boosting，以验证集 Macro-F1 选择模型，然后只在未参与选择的测试集上判定达标。默认门槛：

- Accuracy ≥ 0.85
- Macro-F1 ≥ 0.80
- 每个类别 Recall ≥ 0.70
- 测试集至少包含 3 名从未参与开发的受试者
- 每个测试类别至少 30 个样本
- 关键点检测覆盖率 ≥ 0.90（在丢弃未检测帧之前统计）

分类门槛与端到端覆盖率分别报告。分类指标达标时写入
`classifier_status: classifier_passed`；没有原始视频逐帧检测清单时，覆盖率必须为
`pose_coverage_not_evaluated`，端到端状态必须为
`end_to_end_not_evaluated`，不能用已成功提取的 landmark 行反推覆盖率。
`export_model.py` 只允许导出端到端状态达标的模型。外部评估还会拒绝与训练/验证受试者重复的数据。阈值是本项目的部署门槛，不等同于医疗有效性。

特征除归一化关键点与关节角外，还实现了 EduSense 风格的关键点对单位方向与尺度归一化距离；候选模型包含其使用的 MLP 思路。测试报告把人体检测覆盖率与“已检测帧上的分类指标”分开，避免忽略漏检帧。

```powershell
python evaluate.py --model runs/posture/model.joblib --data data/external-test.jsonl
python export_model.py --run runs/posture --output runs/healthverse-pose-model.zip
```

每次训练会生成：`model.joblib`、`metrics.json`、`confusion_matrix.csv`、`training_history.json`、`splits.csv` 和 `model_card.md`。

## 按受试者的稳健性分析

对已有独立测试运行计算 95% 置信区间时，必须以 `subject_id` 为聚类单位重采样，禁止把高度相关的视频帧当作独立样本。下面的命令还会在全部受试者上执行 5 折 GroupKFold，报告每折指标及最差未见受试者组，并写入新的输出目录，拒绝覆盖已有结果：

```powershell
python robustness_analysis.py `
  --upper-data data/multiposture-upper.jsonl --upper-run runs/upper-v2-subject3 `
  --lower-data data/multiposture-lower.jsonl --lower-run runs/lower-v1-subject3 `
  --config config-subject3.json --output runs/robustness-v1 `
  --bootstrap-repeats 2000 --cv-folds 5 --seed 20261125
```

输出包括 `robustness.json`、`cluster_bootstrap_ci.csv`、`groupkfold_folds.csv` 和 `ROBUSTNESS.md`。MultiPosture 输入是已成功提取的 landmark 表，因此 pose coverage 固定报告为 N/A；本分析只评价“关键点可用条件下”的分类器。

## 工程测试与 benchmark 的区别

```powershell
$env:PYTHONPATH = "."
python -m unittest discover -s tests -v
```

单元测试只检查特征、分组切分和阈值逻辑，不能作为准确率证据。只有使用注明来源、许可、标签和独立测试分区的真实数据运行 `train.py` 后，输出指标才可报告为 benchmark 结果。
