# Slurm命令使用大全

Slurm (Simple Linux Utility for Resource Management) 是高性能计算集群中最常用的作业调度系统。本指南涵盖常用命令、选项和最佳实践。

---

## 一、核心命令速查

| 命令 | 用途 | 常用场景 |
|------|------|----------|
| `sbatch` | 提交批处理作业 | 提交训练、仿真等长时间任务 |
| `srun` | 交互式运行或在作业中启动任务 | 快速测试、分布式任务启动 |
| `salloc` | 分配资源进行交互式会话 | 调试代码、交互式开发 |
| `scancel` | 取消作业 | 终止排队或运行中的作业 |
| `squeue` | 查看作业队列 | 检查作业状态 |
| `sinfo` | 查看集群节点信息 | 了解可用资源 |
| `sacct` | 查看历史作业信息 | 分析作业性能、排查问题 |
| `scontrol` | 查看/修改作业和节点详细信息 | 高级管理操作 |

---

## 二、sbatch - 批处理作业提交

### 2.1 基本用法

```bash
# 提交脚本
sbatch job_script.sh

# 从标准输入提交
sbatch <<EOF
#!/bin/bash
#SBATCH --job-name=test
#SBATCH --output=result.txt
echo "Hello Slurm"
EOF
```

### 2.2 常用选项

**基础配置**
```bash
#SBATCH --job-name=my_job          # 作业名称（显示在squeue中）
#SBATCH --output=output_%j.log     # 标准输出文件（%j = job ID）
#SBATCH --error=error_%j.log       # 标准错误文件
#SBATCH --chdir=/path/to/workdir   # 工作目录
```

**资源请求**
```bash
#SBATCH --nodes=2                  # 节点数
#SBATCH --ntasks=4                 # 任务总数
#SBATCH --ntasks-per-node=2        # 每节点任务数
#SBATCH --cpus-per-task=8          # 每任务CPU核心数
#SBATCH --mem=32G                  # 每节点内存（也可用 --mem-per-cpu）
#SBATCH --gres=gpu:2               # 通用资源（如GPU）
#SBATCH --gres=gpu:a100:2          # 指定GPU型号
```

**时间与队列**
```bash
#SBATCH --time=02:30:00            # 时限（格式：DD-HH:MM:SS 或 HH:MM:SS）
#SBATCH --partition=gpu            # 分区/队列名称
#SBATCH --qos=high                 # 服务质量（优先级）
```

**通知与依赖**
```bash
#SBATCH --mail-type=END,FAIL       # 邮件通知类型（BEGIN/END/FAIL/ALL）
#SBATCH --mail-user=user@email.com # 邮件地址
#SBATCH --dependency=afterok:12345 # 作业依赖（等12345成功后运行）
```

**高级选项**
```bash
#SBATCH --array=1-10               # 数组作业（提交10个类似任务）
#SBATCH --exclusive                # 独占节点
#SBATCH --constraint=rtx3090       # 节点特性约束
#SBATCH --account=project_name     # 计费账户
```

### 2.3 完整示例脚本

```bash
#!/bin/bash
#SBATCH --job-name=behavior_train
#SBATCH --output=logs/train_%j.out
#SBATCH --error=logs/train_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:2
#SBATCH --mem=64G
#SBATCH --time=48:00:00
#SBATCH --partition=gpu
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=your@email.com

# 加载环境
module load cuda/11.8
source ~/miniconda3/bin/activate behavior

# 设置环境变量
export OMNIGIBSON_HEADLESS=1
export CUDA_VISIBLE_DEVICES=0,1

# 打印作业信息
echo "Job ID: $SLURM_JOB_ID"
echo "Running on: $(hostname)"
echo "Start time: $(date)"

# 执行任务
cd /home/user/project/BEHAVIOR-1K
python -m OmniGibson.examples.train_agent \
    --config configs/my_config.yaml \
    --gpus 2

echo "End time: $(date)"
```

---

## 三、srun - 交互式运行

### 3.1 基本用法

```bash
# 简单运行命令
srun hostname

# 指定资源运行
srun --nodes=1 --ntasks=4 --cpus-per-task=2 python script.py

# 交互式shell（结合salloc使用更好）
srun --pty bash
```

### 3.2 在sbatch脚本内使用

```bash
#!/bin/bash
#SBATCH --nodes=2
#SBATCH --ntasks=8

# 并行启动多个任务
srun --ntasks=8 python distributed_training.py

# 分步骤执行
srun --ntasks=1 python preprocess.py
srun --ntasks=8 python train.py
srun --ntasks=1 python evaluate.py
```

---

## 四、salloc - 交互式资源分配

### 4.1 基本用法

```bash
# 分配资源并启动shell
salloc --nodes=1 --gres=gpu:1 --time=2:00:00

# 分配后会进入子shell，可以：
hostname              # 查看分配的节点
srun python test.py   # 运行任务
exit                  # 释放资源
```

### 4.2 实用场景

```bash
# GPU交互式调试
salloc --gres=gpu:1 --cpus-per-task=8 --mem=32G --time=4:00:00
srun --pty bash  # 进入分配的节点
nvidia-smi       # 检查GPU

# 快速测试
salloc --nodes=1 --time=30:00 srun python quick_test.py
```

---

## 五、作业管理命令

### 5.1 squeue - 查看作业队列

```bash
# 查看所有作业
squeue

# 查看自己的作业
squeue -u $USER

# 详细格式
squeue -l

# 自定义输出格式
squeue -o "%.18i %.9P %.8j %.8u %.2t %.10M %.6D %R"

# 查看特定作业
squeue -j 12345

# 查看特定分区
squeue -p gpu

# 持续监控（每2秒刷新）
watch -n 2 'squeue -u $USER'
```

**作业状态代码**
- `PD` (PENDING): 排队等待
- `R` (RUNNING): 运行中
- `CG` (COMPLETING): 完成中
- `CD` (COMPLETED): 已完成
- `F` (FAILED): 失败
- `CA` (CANCELLED): 已取消
- `TO` (TIMEOUT): 超时

### 5.2 scancel - 取消作业

```bash
# 取消单个作业
scancel 12345

# 取消多个作业
scancel 12345 12346 12347

# 取消自己的所有作业
scancel -u $USER

# 取消特定名称的作业
scancel --name=my_job

# 取消特定状态的作业
scancel -u $USER --state=PENDING  # 只取消排队中的

# 取消数组作业的特定任务
scancel 12345_5  # 取消数组作业12345的第5个任务
```

### 5.3 scontrol - 作业/节点控制

```bash
# 查看作业详细信息
scontrol show job 12345

# 查看节点信息
scontrol show node node01

# 修改作业时限（需要权限）
scontrol update JobId=12345 TimeLimit=10:00:00

# 挂起/恢复作业（需要权限）
scontrol suspend 12345
scontrol resume 12345

# 保持作业（防止被抢占）
scontrol hold 12345
scontrol release 12345
```

---

## 六、作业历史与统计

### 6.1 sacct - 作业会计信息

```bash
# 查看今天的作业
sacct

# 查看指定日期范围
sacct -S 2024-01-01 -E 2024-01-31

# 查看特定作业
sacct -j 12345

# 详细信息
sacct -j 12345 --format=JobID,JobName,Partition,State,Elapsed,MaxRSS,MaxVMSize

# 常用格式
sacct --format=JobID,JobName,State,Start,End,Elapsed,NodeList,AllocCPUs,MaxRSS,ExitCode

# 只看失败的作业
sacct --state=FAILED

# 导出为CSV
sacct --format=JobID,JobName,State,Elapsed,MaxRSS -P --delimiter=',' > jobs.csv
```

### 6.2 有用的格式字段

```bash
JobID          # 作业ID
JobName        # 作业名称
Partition      # 分区
State          # 最终状态
ExitCode       # 退出码
Elapsed        # 运行时长
Start          # 开始时间
End            # 结束时间
NodeList       # 使用的节点
AllocCPUs      # 分配的CPU数
MaxRSS         # 最大常驻内存
MaxVMSize      # 最大虚拟内存
```

---

## 七、集群信息查询

### 7.1 sinfo - 节点与分区信息

```bash
# 查看所有分区
sinfo

# 详细格式
sinfo -l

# 查看特定分区
sinfo -p gpu

# 查看节点详情
sinfo -N -l

# 按状态过滤
sinfo -t idle    # 空闲节点
sinfo -t alloc   # 已分配节点
sinfo -t down    # 宕机节点

# 自定义格式
sinfo -o "%20P %5D %14F %10m %11l %N"
# 输出：分区名 节点数 节点状态 内存 时间限制 节点列表
```

### 7.2 sstat - 运行中作业的实时统计

```bash
# 查看运行中作业的资源使用
sstat -j 12345

# 指定统计项
sstat -j 12345 --format=AveCPU,AveRSS,MaxRSS,AveVMSize
```

---

## 八、高级功能

### 8.1 数组作业（Array Jobs）

批量提交相似任务：

```bash
#!/bin/bash
#SBATCH --job-name=batch_sim
#SBATCH --array=1-100          # 提交100个任务
#SBATCH --output=logs/sim_%A_%a.out  # %A=数组ID, %a=任务索引
#SBATCH --time=1:00:00

# 使用 $SLURM_ARRAY_TASK_ID 区分不同任务
python simulate.py --seed $SLURM_ARRAY_TASK_ID
```

**管理数组作业**
```bash
# 提交时限制并发数
#SBATCH --array=1-100%10  # 最多同时运行10个

# 取消数组作业的某些任务
scancel 12345_50-60  # 取消第50-60个任务
```

### 8.2 作业依赖（Job Dependencies）

```bash
# 提交第一个作业
JOB1=$(sbatch --parsable preprocess.sh)

# 等第一个成功后才运行第二个
sbatch --dependency=afterok:$JOB1 train.sh

# 无论成功失败都运行
sbatch --dependency=afterany:$JOB1 cleanup.sh

# 等多个作业都完成
sbatch --dependency=afterok:$JOB1:$JOB2 postprocess.sh
```

**依赖类型**
- `after:jobid` - 在指定作业启动后开始
- `afterok:jobid` - 在指定作业成功完成后
- `afternotok:jobid` - 在指定作业失败后
- `afterany:jobid` - 在指定作业结束后（无论成败）

### 8.3 作业步（Job Steps）

在一个作业内执行多个步骤：

```bash
#!/bin/bash
#SBATCH --nodes=2
#SBATCH --ntasks=8

# 第一步：数据准备
srun --ntasks=1 --job-name=prep python prepare_data.py

# 第二步：分布式训练
srun --ntasks=8 --job-name=train python distributed_train.py

# 第三步：评估
srun --ntasks=1 --job-name=eval python evaluate.py
```

---

## 九、环境变量

Slurm自动设置的有用环境变量：

### 9.1 作业相关
```bash
$SLURM_JOB_ID            # 作业ID
$SLURM_JOB_NAME          # 作业名称
$SLURM_SUBMIT_DIR        # 提交目录
$SLURM_JOB_NODELIST      # 分配的节点列表
$SLURM_ARRAY_TASK_ID     # 数组任务索引
$SLURM_ARRAY_JOB_ID      # 数组作业ID
```

### 9.2 资源相关
```bash
$SLURM_NNODES            # 节点数
$SLURM_NTASKS            # 任务总数
$SLURM_CPUS_PER_TASK     # 每任务CPU数
$SLURM_MEM_PER_NODE      # 每节点内存（MB）
$SLURM_GPUS              # GPU总数
$SLURM_GPUS_ON_NODE      # 本节点GPU数
```

### 9.3 节点相关
```bash
$SLURM_NODEID            # 当前节点在作业中的索引
$SLURM_LOCALID           # 当前进程在节点上的ID
$SLURM_PROCID            # 当前进程在作业中的全局ID
$SLURMD_NODENAME         # 当前节点名称
```

**使用示例**
```bash
#!/bin/bash
#SBATCH --nodes=2
#SBATCH --gres=gpu:2

echo "Job ID: $SLURM_JOB_ID"
echo "Nodes: $SLURM_JOB_NODELIST"
echo "GPUs: $SLURM_GPUS"

# 设置每个任务看到的GPU
export CUDA_VISIBLE_DEVICES=$SLURM_LOCALID
```

---

## 十、常见问题与最佳实践

### 10.1 资源请求优化

**❌ 常见错误**
```bash
# 请求过多资源导致长时间排队
#SBATCH --nodes=10 --time=72:00:00 --gres=gpu:8

# 请求不足导致OOM或超时
#SBATCH --mem=4G --time=10:00
```

**✅ 最佳实践**
```bash
# 1. 先用小规模测试估算资源需求
#SBATCH --nodes=1 --time=30:00 --mem=8G

# 2. 根据测试结果调整
# 查看实际使用：sacct -j <jobid> --format=MaxRSS,Elapsed

# 3. 预留20%余量
# 如果测试用了40G内存，请求48G

# 4. 时间限制稍长于预期
# 如果预计6小时，请求7-8小时
```

### 10.2 输出文件管理

```bash
# 使用作业ID和数组索引避免覆盖
#SBATCH --output=logs/job_%A_%a.out
#SBATCH --error=logs/job_%A_%a.err

# 按日期组织
#SBATCH --output=logs/%x_%j_%D.log  # %x=作业名, %D=日期

# 创建输出目录
mkdir -p logs
```

### 10.3 检查点与重启

```bash
#!/bin/bash
#SBATCH --time=24:00:00

# 定期保存检查点
python train.py --checkpoint-dir=/path/to/checkpoints

# 作业超时前自动重新提交
# （需要在代码中实现检查点保存）
if [ -f checkpoint.pth ]; then
    python train.py --resume checkpoint.pth
else
    python train.py
fi
```

### 10.4 调试技巧

**查看作业失败原因**
```bash
# 1. 查看状态和退出码
sacct -j 12345 --format=State,ExitCode

# 2. 查看详细信息
scontrol show job 12345

# 3. 检查日志文件
tail -100 error_12345.err

# 4. 查看节点日志（如果有权限）
ssh node01 "tail /var/log/slurm/slurmd.log"
```

**交互式调试**
```bash
# 分配资源后登录节点
salloc --nodes=1 --gres=gpu:1
srun --pty bash

# 在节点上手动运行命令调试
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

### 10.5 监控与日志

**实时查看日志**
```bash
# 作业运行时查看输出
tail -f output_12345.log

# 多个作业
tail -f logs/job_*.out
```

**资源使用监控**
```bash
# 查看运行中作业的实时统计
watch -n 5 'sstat -j 12345 --format=AveCPU,AveRSS,MaxRSS'

# 使用scontrol查看详细信息
scontrol show job 12345 | grep -E 'RunTime|TimeLimit|Nodes'
```

---

## 十一、实用脚本与技巧

### 11.1 批量提交脚本

```bash
#!/bin/bash
# batch_submit.sh - 批量提交不同参数的作业

for lr in 0.001 0.0001 0.00001; do
    for batch_size in 32 64 128; do
        sbatch <<EOF
#!/bin/bash
#SBATCH --job-name=train_lr${lr}_bs${batch_size}
#SBATCH --output=logs/lr${lr}_bs${batch_size}_%j.log
#SBATCH --gres=gpu:1
#SBATCH --time=12:00:00

python train.py --lr $lr --batch-size $batch_size
EOF
    done
done
```

### 11.2 作业状态总结

```bash
#!/bin/bash
# job_summary.sh - 显示作业状态摘要

echo "=== 我的作业状态 ==="
echo "运行中: $(squeue -u $USER -t RUNNING | wc -l)"
echo "排队中: $(squeue -u $USER -t PENDING | wc -l)"
echo ""
echo "=== 最近完成的作业 ==="
sacct -u $USER -S $(date -d '1 day ago' +%Y-%m-%d) \
    --format=JobID,JobName,State,Elapsed,MaxRSS \
    | head -20
```

### 11.3 清理脚本

```bash
#!/bin/bash
# cleanup.sh - 清理旧的日志和临时文件

# 删除7天前的日志
find logs/ -name "*.log" -mtime +7 -delete

# 删除已完成作业的临时文件
for jobid in $(sacct -S $(date -d '1 week ago' +%Y-%m-%d) \
    --state=COMPLETED --format=JobID --noheader); do
    rm -rf /tmp/job_${jobid}
done
```

---

## 十二、不同场景的模板

### 12.1 单GPU训练

```bash
#!/bin/bash
#SBATCH --job-name=single_gpu
#SBATCH --output=logs/%x_%j.log
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --time=24:00:00

module load cuda/11.8
conda activate myenv

python train.py --config config.yaml
```

### 12.2 多GPU训练（单节点）

```bash
#!/bin/bash
#SBATCH --job-name=multi_gpu
#SBATCH --output=logs/%x_%j.log
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gres=gpu:4
#SBATCH --mem=128G
#SBATCH --time=48:00:00

module load cuda/11.8
conda activate myenv

# PyTorch DDP
python -m torch.distributed.launch \
    --nproc_per_node=4 \
    train.py --config config.yaml
```

### 12.3 多节点分布式训练

```bash
#!/bin/bash
#SBATCH --job-name=distributed
#SBATCH --output=logs/%x_%j.log
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:4
#SBATCH --mem=256G
#SBATCH --time=72:00:00

module load cuda/11.8
conda activate myenv

# 获取主节点地址
export MASTER_ADDR=$(scontrol show hostname $SLURM_JOB_NODELIST | head -n 1)
export MASTER_PORT=29500

# PyTorch DDP多节点
srun python train.py \
    --master-addr $MASTER_ADDR \
    --master-port $MASTER_PORT \
    --world-size $SLURM_NTASKS \
    --rank $SLURM_PROCID
```

### 12.4 Jupyter Notebook交互式

```bash
#!/bin/bash
#SBATCH --job-name=jupyter
#SBATCH --output=logs/jupyter_%j.log
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --time=8:00:00

module load cuda/11.8
conda activate myenv

# 获取节点IP和端口
NODE=$(hostname)
PORT=8888

echo "在本地终端运行以下命令建立SSH隧道："
echo "ssh -N -L ${PORT}:${NODE}:${PORT} $USER@login_node"
echo ""

# 启动Jupyter
jupyter notebook --no-browser --port=$PORT --ip=0.0.0.0
```

### 12.5 参数搜索数组作业

```bash
#!/bin/bash
#SBATCH --job-name=hyperparam_search
#SBATCH --output=logs/search_%A_%a.log
#SBATCH --array=0-99%20          # 100个任务，最多同时运行20个
#SBATCH --nodes=1
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --time=4:00:00

module load cuda/11.8
conda activate myenv

# 定义参数空间
learning_rates=(0.1 0.01 0.001 0.0001)
batch_sizes=(16 32 64 128 256)
optimizers=("adam" "sgd" "adamw" "rmsprop")

# 计算当前组合
n_lr=${#learning_rates[@]}
n_bs=${#batch_sizes[@]}
n_opt=${#optimizers[@]}

idx=$SLURM_ARRAY_TASK_ID
opt_idx=$((idx / (n_lr * n_bs)))
lr_idx=$(((idx / n_bs) % n_lr))
bs_idx=$((idx % n_bs))

lr=${learning_rates[$lr_idx]}
bs=${batch_sizes[$bs_idx]}
opt=${optimizers[$opt_idx]}

echo "Running with lr=$lr, batch_size=$bs, optimizer=$opt"

python train.py \
    --lr $lr \
    --batch-size $bs \
    --optimizer $opt \
    --output-dir results/${SLURM_ARRAY_JOB_ID}/${SLURM_ARRAY_TASK_ID}
```

---

## 十三、快速参考卡片

```
┌──────────────────────────────────────────────────────────────┐
│                    Slurm命令速查表                            │
├──────────────────────────────────────────────────────────────┤
│ 提交与运行                                                    │
│   sbatch script.sh          提交批处理作业                    │
│   srun command              运行命令                          │
│   salloc                    分配交互式资源                    │
│                                                               │
│ 作业管理                                                      │
│   squeue -u $USER           查看我的作业                      │
│   scancel 12345             取消作业                          │
│   scontrol show job 12345   查看作业详情                      │
│                                                               │
│ 历史与统计                                                    │
│   sacct -j 12345            查看作业信息                      │
│   sstat -j 12345            实时统计（运行中）                │
│                                                               │
│ 集群信息                                                      │
│   sinfo                     查看分区和节点                    │
│   sinfo -p gpu              查看GPU分区                       │
│                                                               │
│ 常用组合                                                      │
│   watch -n 2 'squeue -u $USER'     持续监控队列               │
│   sacct --format=JobID,State,Elapsed,MaxRSS  查看资源使用    │
│   scancel -u $USER --state=PENDING  取消所有排队作业          │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                  常用SBATCH选项速查                           │
├──────────────────────────────────────────────────────────────┤
│ 基础                                                          │
│   --job-name=NAME           作业名称                          │
│   --output=FILE             输出文件                          │
│   --time=HH:MM:SS           时间限制                          │
│   --partition=NAME          分区/队列                         │
│                                                               │
│ 资源                                                          │
│   --nodes=N                 节点数                            │
│   --ntasks=N                任务数                            │
│   --cpus-per-task=N         每任务CPU数                       │
│   --mem=SIZE                内存（如32G）                     │
│   --gres=gpu:N              GPU数量                           │
│                                                               │
│ 高级                                                          │
│   --array=1-100             数组作业                          │
│   --dependency=afterok:ID   依赖关系                          │
│   --mail-type=END           邮件通知                          │
└──────────────────────────────────────────────────────────────┘
```

---

## 十四、注意事项与常见陷阱

### ⚠️ 资源浪费
- **不要**请求远超实际需要的资源（降低队列优先级）
- **不要**长时间占用资源但不使用（影响其他用户）
- **建议**先小规模测试，再扩大资源请求

### ⚠️ 时间限制
- 作业超时会被强制终止（不会保存状态）
- 务必实现检查点机制保存进度
- 时间请求要预留余量（但不要过多）

### ⚠️ 内存OOM
- 查看历史作业的MaxRSS：`sacct -j <jobid> --format=MaxRSS`
- 请求内存应大于实际使用的20-30%
- 注意是每节点内存还是每任务内存

### ⚠️ GPU不可见
- 检查 `$CUDA_VISIBLE_DEVICES` 是否正确
- 某些集群需要显式设置：`export CUDA_VISIBLE_DEVICES=$SLURM_LOCALID`
- 使用 `nvidia-smi` 确认GPU状态

### ⚠️ 文件路径问题
- 使用绝对路径或在脚本中`cd`到工作目录
- 输出目录可能不自动创建，需要 `mkdir -p`
- 注意NFS挂载的延迟（不要频繁读写小文件）

### ⚠️ 环境变量
- Slurm作业的环境不继承登录shell的所有变量
- 需要在脚本中显式加载module和激活conda环境
- 使用 `module list` 和 `conda env list` 验证

### ⚠️ 依赖关系
- 依赖的作业失败会导致后续作业不运行
- 使用 `afterany` 而非 `afterok` 可以确保清理步骤总是运行
- 检查依赖链中每个作业的状态

### ⚠️ 数组作业
- 数组索引默认从0开始（也可以从1开始，看`--array`参数）
- 注意并发限制（`%N`），避免同时启动过多任务
- 输出文件使用`%A_%a`避免冲突

---

## 十五、进一步学习资源

- **官方文档**: https://slurm.schedmd.com/documentation.html
- **快速入门**: https://slurm.schedmd.com/quickstart.html
- **PDF速查表**: https://slurm.schedmd.com/pdfs/summary.pdf
- **Slurm教程**: https://slurm.schedmd.com/tutorials.html

**集群特定文档**
- 查看你所在集群的wiki或文档
- 运行 `man sbatch`、`man squeue` 等查看本地帮助
- 联系集群管理员了解本地配置和限制

---

**最后建议**：
1. 先在小规模测试，验证脚本正确性
2. 监控作业资源使用，优化资源请求
3. 使用日志和检查点，方便调试和恢复
4. 尊重共享资源，合理使用集群

祝使用愉快！🚀
