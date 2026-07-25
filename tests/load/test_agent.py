"""Locust load test for the agent chat endpoint.

Usage:
    pip install locust
    locust -f tests/load/test_agent.py --host=http://localhost:8000
"""

import json
import random

from locust import HttpUser, between, task

QUERIES = [
    "analyze my content strategy",
    "what should I post next",
    "how is my engagement trending",
    "what topics are performing best",
    "compare my performance with competitors",
    "what are the latest trends in AI content",
    "give me recommendations for next week",
    "what hook types work best for my audience",
    "analyze my posting frequency",
    "how can I improve my virality score",
    "what duration works best for my reels",
    "which content format should I focus on",
    "what is my best posting day",
    "analyze my audience interests",
    "summarize my content performance",
]


class AgentChatUser(HttpUser):
    wait_time = between(1, 5)

    def on_start(self) -> None:
        self.session_id = f"load-test-{random.randint(10000, 99999)}"

    @task(3)
    def chat_sync(self) -> None:
        query = random.choice(QUERIES)
        with self.client.post(
            "/agent/chat",
            json={"session_id": self.session_id, "message": query},
            headers={"Authorization": "Bearer test-token"},
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code in (503, 429):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def chat_stream(self) -> None:
        query = random.choice(QUERIES)
        with self.client.stream(
            "POST",
            "/agent/chat/stream",
            json={"session_id": self.session_id, "message": query},
            headers={"Authorization": "Bearer test-token"},
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                lines = []
                for line in resp.iter_lines():
                    if line.startswith("data: "):
                        lines.append(json.loads(line[6:]))
                if lines and lines[-1].get("event") == "complete":
                    resp.success()
                else:
                    resp.failure("Stream did not complete")
            elif resp.status_code in (503, 429):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def graph_info(self) -> None:
        with self.client.get(
            "/agent/graph",
            headers={"Authorization": "Bearer test-token"},
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def pipeline_health(self) -> None:
        with self.client.get(
            "/pipeline/health",
            headers={"Authorization": "Bearer test-token"},
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")
