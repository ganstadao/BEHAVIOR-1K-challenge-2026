"""TAMP configuration and metadata."""

# Project metadata
PROJECT_NAME = "TAMP for BEHAVIOR-1K"
VERSION = "0.1.0"
AUTHOR = "LINJ0121"

# Default configurations
DEFAULT_LLM_MODEL = "gpt-4"
DEFAULT_LLM_TEMPERATURE = 0.7
DEFAULT_MAX_REPLANS = 2
DEFAULT_MAX_EXECUTION_ATTEMPTS = 3

# Action primitive mappings
AVAILABLE_ACTIONS = [
    "navigate_to",
    "grasp",
    "place_on_top",
    "place_inside",
    "open",
    "close",
    "toggle_on",
    "toggle_off",
    "release",
]

# Extended actions (if using full primitive set)
EXTENDED_ACTIONS = AVAILABLE_ACTIONS + [
    "soak_under",
    "soak_inside",
    "wipe",
    "cut",
    "place_near_heating_element",
]
