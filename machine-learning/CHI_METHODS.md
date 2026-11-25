# CHI / IMWUT 方法落地说明

本项目把“姿态识别模型”和“反馈交互策略”分开实现，避免把论文中的阈值规则误写成模型训练。

## 训练方法

- **EduSense（IMWUT / UbiComp 2019）**：论文用人体关键点两两之间的单位方向向量、尺度归一化距离和 MLP 完成坐/站、举手与上肢姿态分类。HealthVerse 按这一思路从 MediaPipe 33 点构造 456 维特征：髋中心归一化坐标、可见度、关节角、躯干方向，以及 13 个关键点的两两单位向量与距离。候选模型在训练/验证受试者上比较，再仅对冻结的未见受试者测试一次。
- **MultiPosture v1**：真实家庭环境中的 13 名参与者、4,800 个手工且经专家验证的坐姿骨架帧。原始视频因隐私未公开，公开的是 MediaPipe Pose Heavy 提取的三维坐标。HealthVerse 保持 `subject_id` 隔离，绝不把同一人的相邻帧随机分到训练和测试。
- **MediaPipe Pose Landmarker**：网页只在浏览器本地把摄像头或导入视频转换为 33 个关键点，再把同一套特征送进导出的真实训练模型。原始画面不进入模型文件，也不上传到服务器。

## CHI 反馈机制

- **Sitting Posture Recognition and Feedback: A Literature Review（CHI 2024）**：反馈应结合任务、环境、隐私和用户偏好；姿态变化本身有价值，系统不应把“始终挺直”当成唯一目标。因此页面输出“可能 / 等待更多证据 / 可忽略”的可撤销建议，而不是医疗判断。
- **PosProjector（CHI 2026）**：采用持续异常后再渐进反馈的设计。HealthVerse 只有在高置信度非中性上身姿态持续 5 秒后才显示建议；短暂动作只显示观察状态，避免单帧误报。
- **Slow Robots for Unobtrusive Posture Correction（CHI 2019）**：强调低打扰、缓慢介入。HealthVerse 不自动改变环境，只在证据稳定后建议用户自行确认或纠正。

## 当前可核验指标

- 上身分类器：冻结的 3 名未见受试者，Accuracy `0.98995`，Macro-F1 `0.98796`。
- 下身分类器：CHI/IMWUT 候选比较选出 ExtraTrees，在同一受试者隔离协议上 Accuracy `0.93467`，Macro-F1 `0.95975`；已替换旧 RandomForest（`0.91960` / `0.94403`）。
- 5 折 GroupKFold：上身 pooled Macro-F1 `0.97551`；下身 `0.93853`。
- 这些数字仅评价“关键点已经成功提取”的分类器；公开数据没有原视频，因而不能声称端到端人体检测覆盖率或医学有效性。

本轮新上身候选为 `0.98744` / `0.98127`，低于原部署上身模型，因此没有为了“看起来更新”而降级替换。浏览器最终组合是原上身 HGB + 改进后的下身 ExtraTrees。

100% 是优化方向，不是可以预设的结论。每次改动必须只根据训练/验证集选择；冻结测试集不得被反复用来调参。若未达到 100%，保留真实误差和失败实验，不用数据泄漏换取表面满分。

## 一手来源

- Krauter et al., *Sitting Posture Recognition and Feedback: A Literature Review*, CHI 2024, DOI: <https://doi.org/10.1145/3613904.3642657>
- Shin et al., *Slow Robots for Unobtrusive Posture Correction*, CHI 2019, DOI: <https://doi.org/10.1145/3290605.3300843>
- Ahuja et al., *EduSense: Practical Classroom Sensing at Scale*, IMWUT 2019, DOI: <https://doi.org/10.1145/3351229>, code: <https://github.com/edusense/edusense>
- MultiPosture v1 dataset: <https://doi.org/10.5281/zenodo.14230872>
- MediaPipe Pose Landmarker Web guide: <https://developers.google.com/mediapipe/solutions/vision/pose_landmarker/web_js>

