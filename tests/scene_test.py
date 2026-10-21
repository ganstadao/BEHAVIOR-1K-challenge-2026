import omnigibson as og
from omnigibson.scenes import InteractiveTraversableScene

og.launch()

scene = InteractiveTraversableScene(
    scene_model="Rs_int",
)

print("== finish ==")