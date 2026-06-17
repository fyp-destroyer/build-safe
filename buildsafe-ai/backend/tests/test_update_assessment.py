from __future__ import annotations

import os
import unittest
from typing import Any

os.environ["GEMINI_ENABLED"] = "false"
os.environ["DEBUG_TRACE_ENABLED"] = "false"

from fastapi.testclient import TestClient

from app.main import app


class UpdateAssessmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def post_update(self, update_message: str) -> dict[str, Any]:
        response = self.client.post(
            "/api/update-assessment",
            json={
                "session_id": "session-update-test",
                "previous_assessment": {
                    "task_intent": "hanging_wall_decor",
                    "task_category": "Carpentry / Assembly",
                    "risk_level": "Safe DIY",
                    "risk_score": 20,
                    "required_tools": ["measuring tape", "level", "pencil", "hammer"],
                    "required_materials": [
                        "picture hooks",
                        "screws",
                        "wall plugs or anchors",
                        "adhesive strips for lightweight frames",
                        "hanging wire if needed",
                    ],
                    "required_ppe": ["safety glasses if drilling", "gloves optional"],
                    "estimated_time": "15-60 minutes depending on wall type and artwork size",
                    "recommended_professional_category": (
                        "No professional usually required for standard wall decor; consider a handyman "
                        "or carpenter if the item is heavy or the wall is tiled, concrete, or uncertain"
                    ),
                    "safety_warnings": [],
                },
                "task_description": "I want to hang a painting in my bedroom.",
                "task_intent": "hanging_wall_decor",
                "task_category": "Carpentry / Assembly",
                "previous_answers": {
                    "How heavy is the painting and what are its approximate dimensions?": "about 1 kg",
                    "What material is the bedroom wall made of, and will you drill or use adhesive hooks?": "drywall, drilling",
                },
                "update_message": update_message,
                "current_user_context": {
                    "user_skill_level": "beginner",
                    "available_tools": ["measuring tape", "level"],
                },
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def find_update(self, response: dict[str, Any], field: str) -> dict[str, Any]:
        updates = response["change_summary"]["detected_updates"]
        for update in updates:
            if update["field"] == field:
                return update
        self.fail(f"Expected field {field!r} in updates {updates!r}")

    def test_detects_weight_update(self) -> None:
        result = self.post_update("Actually, it weighs 2 kg.")
        update = self.find_update(result, "painting_weight")

        self.assertEqual(update["new_value"], "2 kg")
        self.assertEqual(update["old_value_if_known"], "about 1 kg")
        self.assertIn("risk_score", result["change_summary"]["changed_sections"])
        self.assertIn("materials", result["change_summary"]["changed_sections"])
        self.assertIn("safety_warnings", result["change_summary"]["changed_sections"])
        self.assertIn("task_intent", result["change_summary"]["unchanged_sections"])
        self.assertIn("task_category", result["change_summary"]["unchanged_sections"])
        self.assertIn("basic_tools", result["change_summary"]["unchanged_sections"])
        self.assertGreater(
            result["change_summary"]["risk_score_change"]["new_score"],
            result["change_summary"]["risk_score_change"]["old_score"],
        )
        self.assertEqual(result["updated_assessment"]["task_intent"], "hanging_wall_decor")
        tools_text = " ".join(result["updated_assessment"]["required_tools"]).lower()
        materials_text = " ".join(result["updated_assessment"]["required_materials"]).lower()
        self.assertNotIn("paint roller", tools_text)
        self.assertNotIn("primer", materials_text)
        self.assertNotIn("drying", result["updated_assessment"]["estimated_time"].lower())
        self.assertEqual(result["debug_trace"]["parser_source"], "fallback")

    def test_detects_wall_material_update(self) -> None:
        result = self.post_update("The wall is concrete.")
        update = self.find_update(result, "wall_material")

        self.assertEqual(update["new_value"], "concrete")
        self.assertIn("basic_tools", result["change_summary"]["changed_sections"])
        self.assertIn("materials", result["change_summary"]["changed_sections"])
        self.assertIn("estimated_time", result["change_summary"]["changed_sections"])
        self.assertIn("masonry drill bit", result["updated_assessment"]["required_tools"])
        self.assertIn("concrete", " ".join(result["updated_assessment"]["required_materials"]).lower())

    def test_detects_attachment_method_update(self) -> None:
        result = self.post_update("I will use adhesive strips instead of drilling.")
        update = self.find_update(result, "attachment_method")

        self.assertEqual(update["new_value"], "adhesive strips")
        self.assertEqual(update["old_value_if_known"], "drilling")
        self.assertIn("materials", result["change_summary"]["changed_sections"])
        self.assertIn("safety_warnings", result["change_summary"]["changed_sections"])
        self.assertIn("task_intent", result["change_summary"]["unchanged_sections"])
        self.assertIn("adhesive strips rated", " ".join(result["updated_assessment"]["required_materials"]).lower())

    def test_detects_possible_hidden_wiring(self) -> None:
        result = self.post_update("There may be wiring behind the wall.")
        update = self.find_update(result, "hidden_utilities")

        self.assertIn("wiring", update["new_value"])
        self.assertTrue(result["requires_more_information"])
        self.assertLessEqual(len(result["follow_up_questions"]), 1)
        self.assertIn("safety_warnings", result["change_summary"]["changed_sections"])
        self.assertIn("professional_recommendation", result["change_summary"]["changed_sections"])
        self.assertGreater(
            result["change_summary"]["risk_score_change"]["new_score"],
            result["change_summary"]["risk_score_change"]["old_score"],
        )
        self.assertTrue(result["change_summary"]["risk_level_change"]["changed"])

    def test_detects_damaged_electrical_item(self) -> None:
        result = self.post_update("The holder is damaged and I can see wires.")
        update = self.find_update(result, "electrical_damage")

        self.assertIn("damaged holder", update["new_value"])
        self.assertIn("exposed wires", update["new_value"])
        self.assertIn("professional_recommendation", result["change_summary"]["changed_sections"])
        self.assertEqual(result["updated_assessment"]["recommended_professional_category"], "Licensed electrician")


if __name__ == "__main__":
    unittest.main()
