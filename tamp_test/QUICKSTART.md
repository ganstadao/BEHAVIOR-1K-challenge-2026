# Quick Start Guide

## Prerequisites

1. **Activate conda environment**:
```bash
conda activate behavior
```

2. **Navigate to test directory**:
```bash
cd tamp_test
```

## Running the Test

### Simple run (single instance):
```bash
./run_test.sh
```

This will:
- Run evaluation on instance 301
- Use fixed skeleton: [navigate_to, press_button]
- Execute using OmniGibson action primitives
- Save results to `results/instance_301_result.json`

### Custom instance:
```bash
python eval/run_eval.py --config configs/turning_on_radio.yaml --instance 302
```

### Multiple instances:
```bash
for i in 301 302 303; do
    python eval/run_eval.py --config configs/turning_on_radio.yaml --instance $i
done
```

## Expected Output

```
======================================
TAMP Test: Turning On Radio
======================================

[TAMPEvaluator] Setting up environment...
[TAMPEvaluator] ✓ Environment created
[TAMPEvaluator] ✓ Planner created
[TAMPEvaluator] ✓ Executor created

[TAMPEvaluator] Generating skeleton...
Generated skeleton with 2 subgoals:
  1. navigate_to -> radio_receiver.n.01_1
  2. press_button -> radio_receiver.n.01_1

[SkeletonExecutor] Executing skeleton...

--- Subgoal 1/2 ---
Action: navigate_to
Target: radio_receiver.n.01_1
[PrimitiveWrapper] Executing navigate_to: radio_wjqvxz
[PrimitiveWrapper] ✓ Navigation successful
✓ Subgoal 1 completed in 45 steps

--- Subgoal 2/2 ---
Action: press_button
Target: radio_receiver.n.01_1
[PrimitiveWrapper] Executing press_button: radio_wjqvxz
[PrimitiveWrapper] Initial toggled state: False
[PrimitiveWrapper] Final toggled state: True
[PrimitiveWrapper] ✓ Button press successful
✓ Subgoal 2 completed in 12 steps

======================================
Evaluation Result (Instance 301)
======================================
✓ SUCCESS

Subgoals: 2/2
Total steps: 57

Goal status:
  Satisfied: [0]
  Unsatisfied: []
======================================
```

## Output Files

- `results/instance_301_result.json` - Detailed results in JSON
- `results/logs/eval_301.log` - Full execution log

## Troubleshooting

### Error: "No conda environment detected"
```bash
conda activate behavior
```

### Error: "Could not find radio object in object_scope"
The task instance might not be loaded correctly. Check that BDDL task is properly initialized.

### Error: "Navigation failed: motion planning failed"
This is a common failure. The robot couldn't find a valid path to the radio. This is expected in some instances due to:
- Obstacles blocking the path
- Object too far away
- Invalid starting position

### Error: "Toggle action did not change state"
The button press didn't work. Possible reasons:
- Robot not close enough
- Wrong interaction point
- Object doesn't support toggle

## Next Steps

1. **Analyze failures**: Check which subgoal failed and why
2. **Add more tasks**: Extend to other BEHAVIOR-1K tasks
3. **Compare with VLA**: Compare success rate with Pi0.5/GR00T
4. **Add replanning**: Implement failure recovery
