"""
README for TAMP (Task and Motion Planning) for BEHAVIOR-1K

A modern TAMP implementation using LLM-based high-level planning
and action primitives for low-level execution.
"""

# TAMP for BEHAVIOR-1K

A modular Task and Motion Planning (TAMP) system for BEHAVIOR-1K that uses LLMs for high-level symbolic planning and OmniGibson's action primitives for low-level execution.

## Architecture

```
Task (BDDL) → LLM Planner → Subgoal Plan → Primitive Executor → Robot Actions
     ↓              ↓              ↓                ↓
  Symbolic      Generate       Ground to        Execute in
   State        Subgoals      Primitives       Simulation
```

### Key Components

1. **Core** (`tamp/core/`):
   - `symbols.py`: Symbolic predicates, atoms, and states
   - `subgoal.py`: High-level subgoal and plan representations

2. **Planners** (`tamp/planners/`):
   - `base.py`: Abstract planner interface
   - `llm_planner.py`: LLM-based subgoal generation
   - Easily extensible: add search-based, hybrid, or custom planners

3. **Executors** (`tamp/executors/`):
   - `base.py`: Abstract executor interface
   - `primitive_executor.py`: Executes subgoals using OmniGibson primitives
   - Maps high-level actions to SymbolicSemanticActionPrimitives

4. **Utils** (`tamp/utils/`):
   - `bddl_utils.py`: BDDL parsing and state extraction

5. **Examples** (`tamp/examples/`):
   - `turning_on_radio.py`: Complete end-to-end example

## Installation

```bash
# Already installed if you have BEHAVIOR-1K setup
cd /home/msai/linj0121/project/BEHAVIOR-1K

# Install additional dependencies for LLM
pip install openai anthropic  # For LLM planners
```

## Quick Start

### 1. Run Basic Tests

```bash
# Test core components (no simulation required)
python tamp/tests/test_basic.py
```

### 2. Run Full Example (requires GPU)

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your-api-key"

# Run the turning_on_radio example
conda run -n behavior python tamp/examples/turning_on_radio.py
```

### 3. Use in Your Code

```python
from tamp.planners.llm_planner import LLMPlanner
from tamp.executors.primitive_executor import PrimitiveExecutor
from tamp.utils.bddl_utils import load_bddl_task, extract_initial_state, extract_goal_state

# Load task
conditions, scope = load_bddl_task("turning_on_radio")
initial_state = extract_initial_state(conditions)
goal_state = extract_goal_state(conditions)

# Create planner
planner = LLMPlanner(model="gpt-4", api_key="your-key")

# Generate plan
plan = planner.plan(
    task_description="Turn on the radio",
    initial_state=initial_state,
    goal_state=goal_state,
    available_objects=["radio_receiver.n.01_1", "table.n.02_1"],
    available_actions=["navigate_to", "toggle_on"],
)

# Execute plan
executor = PrimitiveExecutor(env, robot)
for subgoal in plan.subgoals:
    success = yield from executor.execute_subgoal(subgoal)
    if not success:
        # Replan on failure
        plan = planner.replan(plan, current_state, failure_info)
```

## Design Principles

### 1. Modularity
- Each component (planner, executor, state representation) is independent
- Easy to swap LLM models, add new planners, or change executors

### 2. Extensibility
- Abstract base classes define clear interfaces
- Add your own planner by inheriting from `BasePlanner`
- Add your own executor by inheriting from `BaseExecutor`

### 3. Observability
- All components log their actions and results
- Execution history tracks success/failure rates
- Plans are serializable for analysis

### 4. LLM-First
- Uses modern LLMs for planning instead of traditional search
- Prompts are designed for few-shot learning
- Easy to add domain knowledge via prompt engineering

## Extending the System

### Add a New Planner

```python
from tamp.planners.base import BasePlanner

class MyPlanner(BasePlanner):
    def plan(self, task_description, initial_state, goal_state, ...):
        # Your planning logic here
        subgoals = [...]
        return SubgoalPlan(subgoals, task_description)
    
    def replan(self, original_plan, current_state, failure_info):
        # Your replanning logic
        return new_plan
```

### Add a New Executor

```python
from tamp.executors.base import BaseExecutor

class MyExecutor(BaseExecutor):
    def execute_subgoal(self, subgoal):
        # Your execution logic
        yield from my_custom_primitives.execute(subgoal)
        return success
    
    def can_execute(self, subgoal):
        return subgoal.action_type in my_supported_actions
```

### Customize LLM Prompts

Edit `llm_planner.py`:
- `_build_planning_prompt()`: Main planning prompt
- `_format_action_schemas()`: Action descriptions
- `_get_few_shot_examples()`: Few-shot examples

## Comparison with Traditional TAMP

| Aspect | Traditional (PDDLStream) | This System (LLM-based) |
|--------|-------------------------|------------------------|
| High-level planner | A* search, FastForward | LLM generates subgoals |
| Domain knowledge | Explicit PDDL actions | Implicit in LLM + few-shot |
| Scalability | Limited by search space | Scales with LLM capability |
| Interpretability | Full symbolic trace | Natural language reasoning |
| Failure handling | Backtracking | LLM replanning with feedback |

## Directory Structure

```
tamp/
├── __init__.py                 # Package initialization
├── core/                       # Core data structures
│   ├── symbols.py             # Predicates, atoms, states
│   └── subgoal.py             # Subgoals and plans
├── planners/                   # Planning algorithms
│   ├── base.py                # Abstract interface
│   └── llm_planner.py         # LLM-based planner
├── executors/                  # Execution engines
│   ├── base.py                # Abstract interface
│   └── primitive_executor.py  # OmniGibson primitives
├── utils/                      # Utilities
│   └── bddl_utils.py          # BDDL parsing
├── examples/                   # Example scripts
│   └── turning_on_radio.py    # Full example
└── tests/                      # Unit tests
    └── test_basic.py          # Basic component tests
```

## TODOs and Future Work

### Short-term
- [ ] Test on more BEHAVIOR-1K tasks
- [ ] Add better error handling and recovery
- [ ] Implement state observation from simulation
- [ ] Add continuous parameter sampling for place actions

### Medium-term
- [ ] Add search-based planner for comparison
- [ ] Implement hybrid LLM + search planner
- [ ] Add learning from execution feedback
- [ ] Support multi-step lookahead and backtracking

### Long-term
- [ ] Fine-tune smaller LLMs on planning data
- [ ] Integrate with motion planning (CuRobo)
- [ ] Add support for partial observability
- [ ] Multi-agent planning and coordination

## References

- **TANDEM**: Task and Motion Planning with As-Needed Demonstrations (inspiration for LLM planning)
- **BEHAVIOR-1K**: Benchmark for embodied AI on 1000+ household tasks
- **OmniGibson**: Physics simulation engine for robotics

## License

Same as BEHAVIOR-1K (see parent directory)

## Authors

LINJ0121, with guidance from Tom Silver and BEHAVIOR-1K team

## Contact

See parent repository for contact information.
