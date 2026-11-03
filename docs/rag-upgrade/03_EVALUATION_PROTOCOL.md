# G6 评测预注册与人工标注规范

40 道复杂问题及 150 组 claim-span 候选由脚本明确生成，均为 CANDIDATE_ONLY，gold 为 null。不能视为已审核真实历史标签，也不是 150 个支持关系。当前独立标注者数=0，κ、人工分钟数、supported-claim precision、missed-conflict、false-corroboration、过度拒答和史实准确率均 BLOCKED，不能填 0 或 100%。

两位有古籍阅读能力的标注者分别记录 source edition、原文 Unicode span、SUPPORTS/CONTRADICTS/MENTIONS/INDETERMINATE、体裁、依赖组、问题可回答性；不看系统排序和另一人标注。第三位仲裁分歧；保留原标签、修订理由、时间和身份。禁止 LLM 自动标签进入 gold。版本冻结后才分开发/测试，避免同一原文改写跨集合泄露。

本轮实验分两部分：原 corpus 的 104 题名称诊断（旧词频余弦、中文归一化 BM25、稀疏 RRF）；40 道复杂候选在真实本地知识快照上的检索/拒答/延迟日志。前者的 MRR/Recall/nDCG 不代表历史 QA，后者没有 gold 时只报告实际返回与结构校验分母。不能跨两套集合比较准确率。

L→H→A 单因素门槛：固定来源快照、查询、k、检索次数和模型预算；Hybrid 至少需要独立测试集净收益和不降低引用支持率，当前 NO-GO（缺人工 gold，未运行 dense 模型）。Research single/fixed/adaptive 记录实际搜索次数，预算上限相同不等于实际成本相同，不在调用数不同的情况下宣称质量提升。J0 已实现；J1/J2/J3 未实测，Jev 无授权为 BLOCKED；J4 单次检索是无自适应基线。后续校准按简繁、异体、跨语言分层报告 ECE，vendor score 不作历史置信度。

与 AIS/ALCE 等工作只采用归属/引用评估理念，不声称原创算法。任务书中的 ConfRAG/EVIRAG 新论文尚需完整文献复核；不会仅据标题宣称研究创新。120 题扩展和双人 gold 是未完成项。
