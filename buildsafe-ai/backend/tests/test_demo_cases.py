from __future__ import annotations

import os
import unittest

os.environ["GEMINI_ENABLED"] = "false"
os.environ["DEBUG_TRACE_ENABLED"] = "false"

from fastapi.testclient import TestClient

from app.main import app


class DemoScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def post_json(self, path: str, payload: dict) -> dict:
        response = self.client.post(path, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def assertContainsKeyword(self, values: list[str], *keywords: str) -> None:
        haystack = " ".join(values).lower()
        self.assertTrue(
            any(keyword.lower() in haystack for keyword in keywords),
            msg=f"Expected one of {keywords!r} in {values!r}",
        )

    def assertNotContainsKeyword(self, values: list[str], *keywords: str) -> None:
        haystack = " ".join(values).lower()
        for keyword in keywords:
            self.assertNotIn(keyword.lower(), haystack)

    def action_plan_payload(self, request: dict, result: dict) -> dict:
        return {
            "task_description": request["task_description"],
            "task_intent": result["task_intent"],
            "task_category": result["task_category"],
            "risk_level": result["risk_level"],
            "risk_score": result["risk_score"],
            "user_skill_level": request["user_skill_level"],
            "available_tools": request["available_tools"],
            "required_tools": result["required_tools"],
            "required_materials": result["required_materials"],
            "required_ppe": result["required_ppe"],
            "safety_warnings": result["safety_warnings"],
            "recommended_professional_category": result["recommended_professional_category"],
            "followup_answers": request["answers_to_followups"],
        }

    def test_1_hanging_painting_is_not_confused_with_room_painting(self) -> None:
        plan = self.post_json(
            "/api/llm/plan-followups",
            {
                "task_description": "I want to hang a new painting in my bedroom.",
                "known_answers": {},
            },
        )
        self.assertEqual(plan["task_intent"], "hanging_wall_decor")
        self.assertEqual(plan["task_category"], "carpentry")
        self.assertEqual(len(plan["follow_up_questions"]), 2)
        self.assertContainsKeyword(plan["follow_up_questions"], "heavy", "weight")
        self.assertContainsKeyword(
            plan["follow_up_questions"],
            "wall made of",
            "drill",
            "adhesive",
            "wall material",
        )

        request = {
            "task_description": "I want to hang a new painting in my bedroom.",
            "user_skill_level": "beginner",
            "available_tools": ["measuring tape", "level"],
            "location_type": "house",
            "urgency": "low",
            "budget_range": "not specified",
            "answers_to_followups": {
                "How heavy is the painting and what are its approximate dimensions?": "lightweight frame about 2kg",
                "What material is the bedroom wall made of, and will you drill or use adhesive hooks?": "painted drywall, adhesive hooks",
            },
        }
        result = self.post_json("/api/assess-task", request)
        self.assertEqual(result["task_intent"], "hanging_wall_decor")
        self.assertIn(result["risk_level"], {"Safe DIY", "DIY with supervision"})
        self.assertNotIn("drying", result["estimated_time"].lower())
        self.assertNotContainsKeyword(result["required_tools"], "roller", "brush", "tray")
        self.assertNotContainsKeyword(result["required_materials"], "wall paint", "paint", "primer", "drop cloth")

        action_plan = self.post_json("/api/action-plan", self.action_plan_payload(request, result))
        self.assertTrue(action_plan["allowed_to_show_steps"])
        self.assertIn(action_plan["plan_type"], {"safe_diy_plan", "supervised_plan"})
        step_text = " ".join(
            step["title"] + " " + step["description"] for step in action_plan["steps"]
        )
        self.assertContainsKeyword([step_text], "wall type", "rated fixing", "hang")
        self.assertContainsKeyword(
            action_plan["stop_conditions"],
            "heavy",
            "hidden wiring",
            "hidden utilities",
            "ladder",
            "wall material",
        )

    def test_2_bedroom_painting_returns_painting_recommendations(self) -> None:
        request = {
            "task_description": "I want to paint my bedroom.",
            "user_skill_level": "beginner",
            "available_tools": ["paint roller", "brush set", "paint tray"],
            "location_type": "house",
            "urgency": "low",
            "budget_range": "not specified",
            "answers_to_followups": {
                "Is there dampness, mold, or peeling paint on the surface?": "no",
                "What is your experience level with this kind of painting work?": "beginner",
            },
        }
        result = self.post_json("/api/assess-task", request)
        self.assertEqual(result["task_intent"], "wall_painting")
        self.assertEqual(result["task_category"], "Painting")
        self.assertContainsKeyword(result["required_tools"], "roller", "brush", "tray")
        self.assertContainsKeyword(result["required_materials"], "paint", "primer", "surface protection")
        self.assertIn("drying", result["estimated_time"].lower())
        self.assertIn(result["risk_level"], {"Safe DIY", "DIY with supervision"})

        action_plan = self.post_json("/api/action-plan", self.action_plan_payload(request, result))
        self.assertTrue(action_plan["allowed_to_show_steps"])
        self.assertIn(action_plan["plan_type"], {"safe_diy_plan", "supervised_plan"})
        step_text = " ".join(
            step["title"] + " " + step["description"] for step in action_plan["steps"]
        )
        self.assertContainsKeyword([step_text], "prepare", "clean", "primer", "paint", "ventilat")
        self.assertContainsKeyword(action_plan["stop_conditions"], "mold", "damp", "ventilat")

    def test_3_heavy_mirror_stays_wall_decor_and_avoids_paint_tools(self) -> None:
        result = self.post_json(
            "/api/assess-task",
            {
                "task_description": "I want to hang a heavy mirror on a tiled bathroom wall.",
                "user_skill_level": "beginner",
                "available_tools": ["measuring tape", "level", "drill"],
                "location_type": "house",
                "urgency": "low",
                "budget_range": "not specified",
                "answers_to_followups": {
                    "How heavy is the painting and what are its approximate dimensions?": "heavy mirror about 18kg",
                    "What material is the bedroom wall made of, and will you drill or use adhesive hooks?": "tiled bathroom wall, I need to drill",
                },
            },
        )
        self.assertEqual(result["task_intent"], "hanging_wall_decor")
        self.assertIn(result["task_category"], {"Carpentry / Assembly", "Tiling", "General DIY"})
        self.assertIn(result["risk_level"], {"DIY with supervision", "Professional recommended", "Professional required"})
        self.assertGreaterEqual(result["risk_score"], 25)
        self.assertContainsKeyword(result["required_materials"], "anchor", "wall plugs")
        self.assertIn("handyman", result["recommended_professional_category"].lower())
        self.assertNotContainsKeyword(result["required_tools"], "roller", "brush", "tray")

    def test_4_ceiling_fan_beginner_path_recommends_electrician(self) -> None:
        request = {
            "task_description": "I want to install a ceiling fan.",
            "user_skill_level": "beginner",
            "available_tools": ["voltage tester", "insulated screwdriver", "stable ladder"],
            "location_type": "house",
            "urgency": "low",
            "budget_range": "not specified",
            "answers_to_followups": {
                "Is there existing wiring and a fan-rated ceiling box already in place?": "yes",
                "What is your skill level with electrical work: beginner, intermediate, or expert?": "beginner",
            },
        }
        result = self.post_json("/api/assess-task", request)
        self.assertEqual(result["task_intent"], "ceiling_fan_installation")
        self.assertEqual(result["task_category"], "Electrical")
        self.assertEqual(result["risk_level"], "Professional recommended")
        self.assertContainsKeyword(result["required_tools"], "voltage tester", "insulated screwdriver", "ladder")
        self.assertIn("electrician", result["recommended_professional_category"].lower())

        action_plan = self.post_json("/api/action-plan", self.action_plan_payload(request, result))
        self.assertFalse(action_plan["allowed_to_show_steps"])
        self.assertEqual(action_plan["plan_type"], "preparation_checklist")
        checklist_text = " ".join(step["description"] for step in action_plan["steps"]).lower()
        self.assertNotIn("connect wires", checklist_text)
        self.assertNotIn("strip wire", checklist_text)
        self.assertNotIn("wire nut", checklist_text)
        self.assertContainsKeyword(action_plan["professional_questions"], "electrician", "wiring", "fan-rated")

    def test_5_wall_demolition_stays_conservative(self) -> None:
        request = {
            "task_description": "I want to break a wall between my kitchen and living room.",
            "user_skill_level": "beginner",
            "available_tools": ["hammer"],
            "location_type": "house",
            "urgency": "high",
            "budget_range": "not specified",
            "answers_to_followups": {
                "Do you know whether the wall is load-bearing?": "not sure",
                "Could there be wiring, plumbing, or gas lines inside the wall?": "not sure",
            },
        }
        result = self.post_json("/api/assess-task", request)
        self.assertEqual(result["task_intent"], "wall_demolition")
        self.assertIn(result["task_category"], {"Masonry / Demolition", "Structural"})
        self.assertIn(
            result["risk_level"],
            {"Professional required", "Dangerous / permit-required / do not attempt"},
        )
        professional = result["recommended_professional_category"].lower()
        self.assertTrue(
            "structural engineer" in professional
            or "mason" in professional
            or "contractor" in professional
        )
        explanation = result["explanation"].lower()
        self.assertNotIn("step 1", explanation)
        self.assertNotIn("step-by-step", explanation)

        action_plan = self.post_json("/api/action-plan", self.action_plan_payload(request, result))
        self.assertFalse(action_plan["allowed_to_show_steps"])
        self.assertEqual(action_plan["plan_type"], "professional_only_checklist")
        self.assertIn(
            "Do not attempt this task without a qualified professional",
            action_plan["safety_notice"],
        )
        checklist_text = " ".join(
            [*action_plan["prerequisites"], *(step["description"] for step in action_plan["steps"])]
        )
        self.assertContainsKeyword([checklist_text], "photos", "measurements", "drawings", "load-bearing")
        self.assertContainsKeyword(action_plan["stop_conditions"], "hidden", "utilities", "load-bearing")

    def test_6_light_bulb_keeps_followups_short_and_avoids_budget(self) -> None:
        plan = self.post_json(
            "/api/llm/plan-followups",
            {
                "task_description": "I want to replace a light bulb.",
                "known_answers": {},
            },
        )
        self.assertEqual(plan["task_intent"], "light_bulb_replacement")
        self.assertLessEqual(len(plan["follow_up_questions"]), 2)
        self.assertLessEqual(len(plan["follow_up_questions"]), 1)
        self.assertNotIn("budget", " ".join(plan["follow_up_questions"]).lower())

        request = {
            "task_description": "I want to replace a light bulb.",
            "user_skill_level": "beginner",
            "available_tools": ["clean cloth"],
            "location_type": "house",
            "urgency": "low",
            "budget_range": "not specified",
            "answers_to_followups": {
                "Are you only replacing a standard bulb, or does this involve wiring or the light fitting?": "standard bulb only",
            },
        }
        result = self.post_json("/api/assess-task", request)
        self.assertEqual(result["task_intent"], "light_bulb_replacement")
        self.assertEqual(result["risk_level"], "Safe DIY")

        action_plan = self.post_json("/api/action-plan", self.action_plan_payload(request, result))
        self.assertTrue(action_plan["allowed_to_show_steps"])
        self.assertEqual(action_plan["plan_type"], "safe_diy_plan")
        self.assertContainsKeyword(
            action_plan["stop_conditions"],
            "fixture",
            "exposed wiring",
            "too high",
        )

    def test_7_leaking_pipe_questions_and_risk_escalation(self) -> None:
        plan = self.post_json(
            "/api/llm/plan-followups",
            {
                "task_description": "I want to fix a leaking pipe.",
                "known_answers": {},
            },
        )
        self.assertEqual(plan["task_intent"], "plumbing_leak_repair")
        questions_text = " ".join(plan["follow_up_questions"]).lower()
        self.assertIn("electrical", questions_text)
        self.assertTrue("minor" in questions_text or "hidden" in questions_text or "main line" in questions_text)

        safer_result = self.post_json(
            "/api/assess-task",
            {
                "task_description": "I want to fix a leaking pipe.",
                "user_skill_level": "intermediate",
                "available_tools": ["adjustable wrench", "bucket"],
                "location_type": "house",
                "urgency": "medium",
                "budget_range": "not specified",
                "answers_to_followups": {
                    "Is the leak near electrical outlets, switches, or appliances?": "no",
                    "Is this a minor visible joint leak, or a hidden or main line leak?": "minor visible joint leak",
                },
            },
        )
        riskier_result = self.post_json(
            "/api/assess-task",
            {
                "task_description": "I want to fix a leaking pipe.",
                "user_skill_level": "intermediate",
                "available_tools": ["adjustable wrench", "bucket"],
                "location_type": "house",
                "urgency": "medium",
                "budget_range": "not specified",
                "answers_to_followups": {
                    "Is the leak near electrical outlets, switches, or appliances?": "yes",
                    "Is this a minor visible joint leak, or a hidden or main line leak?": "hidden or main line leak",
                },
            },
        )
        self.assertEqual(safer_result["task_intent"], "plumbing_leak_repair")
        self.assertEqual(riskier_result["task_intent"], "plumbing_leak_repair")
        self.assertGreater(riskier_result["risk_score"], safer_result["risk_score"])
        self.assertGreaterEqual(
            riskier_result["risk_score_breakdown"]["total"],
            safer_result["risk_score_breakdown"]["total"],
        )
        self.assertIn("plumber", riskier_result["recommended_professional_category"].lower())


if __name__ == "__main__":
    unittest.main()
