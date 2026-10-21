"""
LLM-based planner that generates subgoals using language models.

Inspired by TANDEM's approach but tailored for BEHAVIOR-1K.
Uses prompts to guide the LLM to generate executable subgoals.
"""

import json
import time
from typing import List, Dict, Any, Optional

from tamp.planners.base import BasePlanner, PlanningError
from tamp.core.subgoal import Subgoal, SubgoalPlan
from tamp.core.symbols import State, state_to_dict


class LLMPlanner(BasePlanner):
    """Planner that uses LLM to generate subgoals.

    Args:
        model: LLM model name (e.g., "gpt-4", "claude-3-5-sonnet")
        api_key: API key for the model
        temperature: Sampling temperature
        max_retries: Maximum retry attempts on parsing failures

    Example:
        >>> planner = LLMPlanner(model="gpt-4")
        >>> plan = planner.plan(
        ...     task_description="Turn on the radio",
        ...     initial_state=current_state,
        ...     goal_state=goal_state,
        ...     available_objects=["radio", "table"],
        ...     available_actions=["navigate_to", "toggle_on"]
        ... )
    """

    def __init__(
        self,
        model: str = "gpt-5.5",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 3,
        **kwargs
    ):
        super().__init__(kwargs)
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries

        # Initialize LLM client (lazy import to avoid dependency issues)
        self._client = None
        self._api_key = api_key

    def _get_client(self):
        """Lazy initialization of LLM client."""
        if self._client is None:
            if "gpt" in self.model.lower():
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url="https://cc-vibe.com/v1"
                )
            elif "claude" in self.model.lower():
                from anthropic import Anthropic
                self._client = Anthropic(
                    api_key=self._api_key,
                    base_url="https://cc-vibe.com/v1"
                )
            else:
                raise ValueError(f"Unsupported model: {self.model}")
        return self._client

    def plan(
        self,
        task_description: str,
        initial_state: State,
        goal_state: State,
        available_objects: List[str],
        available_actions: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> SubgoalPlan:
        """Generate a plan using LLM.

        The LLM receives:
        - Task description
        - Current state
        - Goal state
        - Available objects and actions
        - Action schemas with examples

        It returns a structured JSON plan with subgoals.
        """
        start_time = time.time()
        context = context or {}

        # Build the prompt
        prompt = self._build_planning_prompt(
            task_description,
            initial_state,
            goal_state,
            available_objects,
            available_actions,
            context,
        )

        # Query LLM with retries
        for attempt in range(self.max_retries):
            try:
                response = self._query_llm(prompt)
                plan = self._parse_response(response, task_description)

                # Log success
                self.planning_history.append({
                    "task": task_description,
                    "attempt": attempt + 1,
                    "success": True,
                    "plan_length": len(plan),
                    "time": time.time() - start_time,
                })

                return plan

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                if attempt == self.max_retries - 1:
                    # Log failure
                    self.planning_history.append({
                        "task": task_description,
                        "attempts": self.max_retries,
                        "success": False,
                        "error": str(e),
                        "time": time.time() - start_time,
                    })
                    raise PlanningError(f"Failed to parse LLM response after {self.max_retries} attempts: {e}")
                # Retry with error feedback
                prompt += f"\n\nPrevious attempt failed with error: {e}\nPlease fix the output format."

    def replan(
        self,
        original_plan: SubgoalPlan,
        current_state: State,
        failure_info: Dict[str, Any],
    ) -> SubgoalPlan:
        """Replan after a failure.

        Provides the LLM with:
        - Original plan
        - What failed and why
        - Current state
        - Request for a new plan
        """
        context = {
            "original_plan": original_plan.to_dict(),
            "failure": failure_info,
            "replanning": True,
        }

        # Extract goal from original plan (we need to reconstruct it)
        # For now, use empty goal - in practice, should be passed in
        goal_state = frozenset()

        # Extract available objects and actions from original plan
        available_objects = list(set(sg.target_object for sg in original_plan.subgoals))
        available_actions = list(set(sg.action_type for sg in original_plan.subgoals))

        return self.plan(
            task_description=original_plan.task_description,
            initial_state=current_state,
            goal_state=goal_state,
            available_objects=available_objects,
            available_actions=available_actions,
            context=context,
        )

    def _build_planning_prompt(
        self,
        task_description: str,
        initial_state: State,
        goal_state: State,
        available_objects: List[str],
        available_actions: List[str],
        context: Dict[str, Any],
    ) -> str:
        """Build the prompt for LLM planning."""

        initial_dict = state_to_dict(initial_state)
        goal_dict = state_to_dict(goal_state)

        prompt = f"""You are a robot task planner for household activities. Generate a step-by-step plan to accomplish the given task.

**Task**: {task_description}

**Current State**:
{json.dumps(initial_dict, indent=2)}

**Goal State**:
{json.dumps(goal_dict, indent=2)}

**Available Objects**: {', '.join(available_objects)}

**Available Actions**:
{self._format_action_schemas(available_actions)}

**Instructions**:
1. Break down the task into a sequence of subgoals
2. Each subgoal should be achievable by one action
3. Consider preconditions (e.g., must navigate before grasping)
4. Output ONLY valid JSON in the exact format below

**Output Format**:
{{
  "reasoning": "Brief explanation of your plan",
  "subgoals": [
    {{
      "description": "Natural language description",
      "action_type": "one of the available actions",
      "target_object": "object name from available objects",
      "parameters": {{}},
      "preconditions": ["state requirements before this action"],
      "effects": ["expected state changes after this action"]
    }}
  ]
}}

"""

        # Add context if replanning
        if context.get("replanning"):
            failure = context["failure"]
            prompt += f"""
**REPLANNING CONTEXT**:
The previous plan failed at step {failure.get('step', 'unknown')}:
- Failed action: {failure.get('action', 'unknown')}
- Error: {failure.get('error', 'unknown')}

Please generate a new plan that avoids this failure.

"""

        # Add few-shot examples
        prompt += self._get_few_shot_examples()

        return prompt

    def _format_action_schemas(self, actions: List[str]) -> str:
        """Format action schemas for the prompt."""
        schemas = {
            "navigate_to": "Move the robot to be near an object. Args: target_object",
            "grasp": "Pick up an object. Args: target_object. Precondition: near object, hands empty",
            "place_on_top": "Place held object on another object. Args: target_surface. Precondition: holding object",
            "place_inside": "Place held object inside container. Args: target_container. Precondition: holding object",
            "open": "Open an object (door, drawer, etc). Args: target_object",
            "close": "Close an object. Args: target_object",
            "toggle_on": "Turn on an object. Args: target_object",
            "toggle_off": "Turn off an object. Args: target_object",
            "release": "Release held object. Precondition: holding object",
        }

        result = []
        for action in actions:
            if action in schemas:
                result.append(f"  - {action}: {schemas[action]}")
        return "\n".join(result) if result else "\n".join(f"  - {a}" for a in actions)

    def _get_few_shot_examples(self) -> str:
        """Get few-shot examples for the prompt."""
        return """
**Example 1**: Turn on the radio
{{
  "reasoning": "Need to navigate to radio first, then toggle it on",
  "subgoals": [
    {{
      "description": "Navigate to the radio",
      "action_type": "navigate_to",
      "target_object": "radio_receiver.n.01_1",
      "parameters": {{}},
      "preconditions": [],
      "effects": ["near(robot, radio_receiver.n.01_1)"]
    }},
    {{
      "description": "Toggle on the radio",
      "action_type": "toggle_on",
      "target_object": "radio_receiver.n.01_1",
      "parameters": {{}},
      "preconditions": ["near(robot, radio_receiver.n.01_1)"],
      "effects": ["toggled_on(radio_receiver.n.01_1)"]
    }}
  ]
}}

Now generate the plan for the given task:
"""

    def _query_llm(self, prompt: str) -> str:
        """Query the LLM and return response."""
        client = self._get_client()

        if "gpt" in self.model.lower():
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )
            return response.choices[0].message.content

        elif "claude" in self.model.lower():
            response = client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text

        else:
            raise ValueError(f"Unsupported model: {self.model}")

    def _parse_response(self, response: str, task_description: str) -> SubgoalPlan:
        """Parse LLM response into a SubgoalPlan."""
        # Extract JSON from response (handle markdown code blocks)
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        # Parse JSON
        data = json.loads(response)

        # Create subgoals
        subgoals = []
        for sg_data in data["subgoals"]:
            subgoal = Subgoal(
                description=sg_data["description"],
                action_type=sg_data["action_type"],
                target_object=sg_data["target_object"],
                parameters=sg_data.get("parameters", {}),
                preconditions=sg_data.get("preconditions", []),
                effects=sg_data.get("effects", []),
            )
            subgoals.append(subgoal)

        return SubgoalPlan(
            subgoals=subgoals,
            task_description=task_description,
            reasoning=data.get("reasoning"),
        )
