"""Satori task-plan parser, adapted from the MIT-licensed upstream project.

Upstream:
  https://github.com/VIDA-NYU/satori-assistance
  pipelines/task/task_planner_pipeline.py::parse_xml_to_dict
Commit inspected: dd09f303043cd90a9e486518bf9878f301f14677

The original copyright and MIT license are retained in LICENSE-SATORI.
"""

import xml.etree.ElementTree as ET


def parse_xml_to_dict(xml_data):
    """Convert Satori's XML task-plan representation into a JSON-ready dict."""
    root = ET.fromstring(xml_data)
    desired_task = root.findtext("DesiredTask") or ""
    task_plan = {"desired_task": desired_task, "steps": [], "objects": []}

    steps_node = root.find("Steps")
    if steps_node is not None:
        for step in steps_node.findall("Step"):
            step_data = {
                "is_start": step.attrib.get("isStart") == "true",
                "content": step.findtext("StepContent") or "",
                "checkpoints": [],
                "step_check_prompts": [],
            }
            checkpoints = step.find("Checkpoints")
            if checkpoints is not None:
                for checkpoint in checkpoints.findall("Checkpoint"):
                    step_data["checkpoints"].append(
                        {
                            "instruction": checkpoint.findtext("Instruction") or "",
                            "blip_prompt": checkpoint.findtext("BlipPrompt") or "",
                        }
                    )
            status_prompts = step.find("StepStatusCheckPrompts")
            if status_prompts is not None:
                step_data["step_check_prompts"] = [
                    prompt.text or "" for prompt in status_prompts.findall("Prompt")
                ]
            task_plan["steps"].append(step_data)

    objects_node = root.find("Objects")
    if objects_node is not None:
        task_plan["objects"] = [node.text or "" for node in objects_node.findall("Object")]
    return task_plan
