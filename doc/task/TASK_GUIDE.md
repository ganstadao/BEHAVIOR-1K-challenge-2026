# 任务评估指南和故障排查

## 🔍 问题 1: opening_doors 无法输出结果

### 原因分析

你遇到的问题可能有以下几个原因：

#### 1. OpenPI-Comet 兼容性问题（主要原因）

从你的日志来看：
```
RuntimeError: Policy server did not become ready within 300s
```

**根本原因**: 
- 你使用的是 `comet_pt50_turning_on_radio` 配置
- 这个配置指向 openpi-comet，它需要 2025 Challenge 版本的 OmniGibson
- **openpi-comet 无法在标准 BEHAVIOR-1K 环境中运行**

#### 2. 任务名称问题

可能的错误：
- ❌ `opening_door` (单数)
- ✅ `opening_doors` (复数，正确)

### 解决方案

**使用标准 OpenPI 而不是 openpi-comet**:

```bash
# 正确的命令
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps doors_test \
    --set task.name=opening_doors

# 不要使用 comet 配置
# ❌ sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio ...
```

## 📋 可用任务列表

### 如何查看所有任务

```bash
# 查看所有可用任务
ls /home/msai/linj0121/project/BEHAVIOR-1K/bddl3/bddl/activity_definitions/

# 统计任务数量
ls /home/msai/linj0121/project/BEHAVIOR-1K/bddl3/bddl/activity_definitions/ | wc -l
```

### 推荐的任务（按难度分类）

#### 🟢 简单任务（推荐用于测试）

这些任务步骤简单，适合快速测试和调试：

```bash
# 1. turning_on_radio - 打开收音机
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test1 \
    --set task.name=turning_on_radio

# 2. turning_on_lamp - 打开台灯
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test2 \
    --set task.name=turning_on_lamp

# 3. opening_doors - 开门
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test3 \
    --set task.name=opening_doors

# 4. closing_doors - 关门
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test4 \
    --set task.name=closing_doors

# 5. turning_off_radio - 关闭收音机
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test5 \
    --set task.name=turning_off_radio
```

#### 🟡 中等难度任务

需要多步操作或物体交互：

```bash
# 6. cleaning_bathtub - 清洁浴缸
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test6 \
    --set task.name=cleaning_bathtub

# 7. washing_dishes - 洗碗
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test7 \
    --set task.name=washing_dishes

# 8. making_coffee - 煮咖啡
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test8 \
    --set task.name=making_coffee

# 9. watering_plants - 浇花
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test9 \
    --set task.name=watering_plants

# 10. folding_clothes - 叠衣服
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test10 \
    --set task.name=folding_clothes
```

#### 🔴 复杂任务

需要长时间执行和复杂操作：

```bash
# 11. preparing_meal - 准备餐食
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test11 \
    --set task.name=preparing_meal

# 12. cleaning_house - 清洁房屋
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test12 \
    --set task.name=cleaning_house

# 13. organizing_closet - 整理衣橱
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test13 \
    --set task.name=organizing_closet
```

## 🎯 快速验证任务是否存在

```bash
# 检查任务定义是否存在
check_task() {
    task_name=$1
    if [ -d "bddl3/bddl/activity_definitions/$task_name" ]; then
        echo "✓ Task exists: $task_name"
        ls "bddl3/bddl/activity_definitions/$task_name"
    else
        echo "✗ Task not found: $task_name"
    fi
}

# 使用方法
check_task opening_doors
check_task turning_on_radio
```

## 🔧 故障排查步骤

### 步骤 1: 确认使用正确的配置

**❌ 错误方式（会导致超时）**:
```bash
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio test
```

**✅ 正确方式**:
```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test
```

### 步骤 2: 检查任务名称

```bash
# 查看任务是否存在
ls bddl3/bddl/activity_definitions/ | grep doors

# 输出应该包含: opening_doors
```

### 步骤 3: 查看日志

```bash
# 1. 查看 SLURM 输出
tail -f logs/eval_<job_id>.out

# 2. 查看错误日志
tail -f logs/eval_<job_id>.err

# 3. 查看 policy server 日志
tail -f eval_logs/pi0.5/opening_doors/*/logs/policy_server.log

# 4. 查看评估日志
tail -f eval_logs/pi0.5/opening_doors/*/logs/omnigibson_eval.log
```

### 步骤 4: 检查是否生成结果

```bash
# 检查 JSON 结果
ls eval_logs/pi0.5/opening_doors/*/json/

# 检查视频
ls eval_logs/pi0.5/opening_doors/*/videos/

# 如果为空，查看日志找出原因
```

## 📊 批量测试推荐任务

### 创建任务列表文件

```bash
cat > recommended_tasks.txt << EOF
turning_on_radio
turning_on_lamp
opening_doors
closing_doors
turning_off_radio
EOF
```

### 批量提交

```bash
bash tools/submit_batch.sh pi05_unlimited_steps baseline \
    $(cat recommended_tasks.txt)
```

### 监控所有作业

```bash
# 查看所有作业
squeue -u $USER

# 等待完成后批量分析
for task in $(cat recommended_tasks.txt); do
    echo "=== Analyzing $task ==="
    bash tools/analyze_results.sh latest pi0.5 $task
done
```

## 🎬 为什么没有输出 JSON 和视频

### 常见原因

#### 1. Policy Server 未启动成功
```bash
# 症状
RuntimeError: Policy server did not become ready within 300s

# 原因
- 使用了不兼容的 openpi-comet
- Checkpoint 路径错误
- GPU 内存不足

# 解决
使用标准 pi05 配置
```

#### 2. 评估提前终止
```bash
# 检查评估是否运行
grep -i "error\|exception" eval_logs/pi0.5/*/logs/omnigibson_eval.log

# 常见错误
- 任务名称错误
- 场景加载失败
- OmniGibson 崩溃
```

#### 3. 评估超时或卡住
```bash
# 症状
- 作业运行很久但没有输出
- CPU/GPU 使用率低

# 检查
squeue -j <job_id>
tail -f logs/eval_<job_id>.out

# 解决
- 限制步数: --set task.max_steps=500
- 检查是否卡在某个状态
```

#### 4. 文件权限问题
```bash
# 检查输出目录权限
ls -la eval_logs/

# 确保可写
chmod 755 eval_logs/
```

## ✅ 正确的评估流程

### 1. 快速测试（限制步数）

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps quick_test \
    --set task.name=opening_doors \
    --set task.max_steps=100 \
    --set task.write_video=false
```

### 2. 完整评估（不限步数）

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps full_eval \
    --set task.name=opening_doors
```

### 3. 监控运行

```bash
# 查看作业状态
squeue -u $USER

# 实时查看日志
tail -f logs/eval_<job_id>.out
```

### 4. 检查结果

```bash
# 等待作业完成后
bash tools/analyze_results.sh latest pi0.5 opening_doors
```

## 🔎 检查清单

评估前检查：
- [ ] 使用 `pi05_unlimited_steps` 配置（不是 comet）
- [ ] 任务名称正确（如 `opening_doors` 不是 `opening_door`）
- [ ] Checkpoint 路径正确
- [ ] GPU 可用

评估中检查：
- [ ] Policy server 成功启动（查看日志）
- [ ] OmniGibson 评估器运行（查看 GPU 使用率）
- [ ] 没有错误信息

评估后检查：
- [ ] JSON 结果存在 (`eval_logs/pi0.5/<task>/*/json/`)
- [ ] 视频文件存在 (`eval_logs/pi0.5/<task>/*/videos/`)
- [ ] 作业正常退出（exit code 0）

## 📝 调试命令合集

```bash
# 1. 查看可用任务
ls bddl3/bddl/activity_definitions/ | head -20

# 2. 搜索特定任务
ls bddl3/bddl/activity_definitions/ | grep -i door

# 3. 检查任务定义
ls -la bddl3/bddl/activity_definitions/opening_doors/

# 4. 查看最近的作业
squeue -u $USER

# 5. 查看作业日志
tail -f logs/eval_<job_id>.out

# 6. 查看评估结果
ls -lt eval_logs/pi0.5/

# 7. 分析特定任务
bash tools/analyze_results.sh latest pi0.5 opening_doors

# 8. 取消卡住的作业
scancel <job_id>
```

## 💡 最佳实践

1. **从简单任务开始**
   ```bash
   sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test \
       --set task.name=turning_on_radio
   ```

2. **先快速测试（限制步数）**
   ```bash
   --set task.max_steps=100
   ```

3. **确认成功后完整评估**
   ```bash
   --set task.max_steps=0  # 不限制
   ```

4. **批量评估时使用延迟**
   ```bash
   bash tools/submit_batch.sh pi05_unlimited_steps baseline task1 task2 task3
   # 脚本自动添加 2 秒延迟
   ```

5. **定期清理旧结果**
   ```bash
   # 只保留最近 5 次运行
   cd eval_logs/pi0.5/<task>/
   ls -t | tail -n +6 | xargs rm -rf
   ```

## 🎯 推荐开始方案

```bash
# 1. 先测试简单任务
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps radio_test \
    --set task.name=turning_on_radio \
    --set task.max_steps=100

# 2. 成功后测试 opening_doors
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps doors_test \
    --set task.name=opening_doors \
    --set task.max_steps=100

# 3. 都成功后进行完整评估
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps doors_full \
    --set task.name=opening_doors
```

---

**关键点**:
- ✅ 使用 `pi05_unlimited_steps` 配置
- ❌ 不要使用 `comet_pt50_turning_on_radio` 配置
- ✅ 任务名称: `opening_doors` (复数)
- ✅ 先快速测试，再完整评估
