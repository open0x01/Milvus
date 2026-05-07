from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.core.config import settings
from src.core.logger import get_logger
from src.services.sqlite_store import memory_store

logger = get_logger(__name__)

SUMMARY_PROMPT = ChatPromptTemplate.from_template(
    "请逐步总结以下对话内容，生成一段简洁的中文摘要。"
    "保留关键信息：用户关注的问题、讨论的漏洞、重要的结论和建议。"
    "如果已有之前的摘要，请将新对话内容整合到已有摘要中。\n\n"
    "已有摘要:\n{existing_summary}\n\n"
    "新对话内容:\n{new_messages}\n\n"
    "整合后的摘要:"
)

EXTRACT_FACTS_PROMPT = ChatPromptTemplate.from_template(
    "请从以下对话中提取关键事实信息，以JSON格式返回。"
    "提取内容包括：用户个人信息（如姓名、身份等）、用户偏好、关注的漏洞、讨论的产品、重要结论等。\n\n"
    "对话内容:\n{messages}\n\n"
    "请返回JSON格式，例如:\n"
    '{{"user_name": "用户姓名（如果提到）", "user_preferences": ["偏好1", "偏好2"], "vulnerabilities_discussed": ["CVE-xxx"], "products_mentioned": ["产品名"], "key_conclusions": ["结论1"]}}'
)


class MemoryService:
    def __init__(self):
        self._summary_llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE,
            temperature=0,
        )
        self.store = memory_store

    def _resolve_user_id(self, session_id: str, user_id: str = None) -> str:
        return user_id or session_id

    def _get_summary_namespace(self, session_id: str, user_id: str = None) -> tuple:
        uid = self._resolve_user_id(session_id, user_id)
        return (uid, "summary")

    def _get_facts_namespace(self, session_id: str, user_id: str = None) -> tuple:
        uid = self._resolve_user_id(session_id, user_id)
        return (uid, "facts")

    def _get_preferences_namespace(self, session_id: str, user_id: str = None) -> tuple:
        uid = self._resolve_user_id(session_id, user_id)
        return (uid, "preferences")

    def get_summary(self, session_id: str, user_id: str = None) -> str:
        namespace = self._get_summary_namespace(session_id, user_id)
        item = self.store.get(namespace, "conversation_summary")
        if item and item.value:
            return item.value.get("summary", "")
        return ""

    def save_summary(self, session_id: str, summary: str, user_id: str = None):
        namespace = self._get_summary_namespace(session_id, user_id)
        self.store.put(namespace, "conversation_summary", {"summary": summary})
        logger.info(f"Saved summary to store: user={str(namespace[0])[:8]}..., length={len(summary)}")

    def get_facts(self, session_id: str, user_id: str = None) -> dict:
        namespace = self._get_facts_namespace(session_id, user_id)
        item = self.store.get(namespace, "extracted_facts")
        if item and item.value:
            return item.value
        return {}

    def save_facts(self, session_id: str, facts: dict, user_id: str = None):
        namespace = self._get_facts_namespace(session_id, user_id)
        self.store.put(namespace, "extracted_facts", facts)
        logger.info(f"Saved facts to store: user={str(namespace[0])[:8]}...")

    def get_user_preferences(self, session_id: str, user_id: str = None) -> list:
        namespace = self._get_preferences_namespace(session_id, user_id)
        item = self.store.get(namespace, "user_preferences")
        if item and item.value:
            return item.value.get("preferences", [])
        return []

    def save_user_preferences(self, session_id: str, preferences: list, user_id: str = None):
        namespace = self._get_preferences_namespace(session_id, user_id)
        self.store.put(namespace, "user_preferences", {"preferences": preferences})

    def search_memories(self, session_id: str, query: str, limit: int = 5) -> list:
        namespace = self._get_facts_namespace(session_id)
        results = self.store.search(namespace, query=query, limit=limit)
        return [r.value for r in results]

    def delete_memory(self, session_id: str):
        self.store.delete_namespace(self._get_summary_namespace(session_id))
        self.store.delete_namespace(self._get_facts_namespace(session_id))
        self.store.delete_namespace(self._get_preferences_namespace(session_id))
        logger.info(f"Deleted all memories for session {session_id[:8]}...")

    def build_memory_context(
        self,
        session_id: str,
        recent_messages: list[dict],
        window_size: int = None,
        user_id: str = None,
    ) -> str:
        if not session_id:
            if not recent_messages:
                return ""
            return "\n".join(
                f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
                for m in recent_messages
            )

        if window_size is None:
            window_size = settings.MEMORY_WINDOW_SIZE

        parts = []

        if settings.MEMORY_SUMMARY_ENABLED:
            summary = self.get_summary(session_id, user_id)
            if summary:
                parts.append(f"[历史对话摘要]\n{summary}")
                logger.info(f"Using summary for user={str(user_id or session_id)[:8]}..., length={len(summary)}")

        facts = self.get_facts(session_id, user_id)
        if facts:
            facts_text = []
            if facts.get("user_name"):
                facts_text.append(f"用户姓名: {facts['user_name']}")
            if facts.get("vulnerabilities_discussed"):
                facts_text.append(f"讨论的漏洞: {', '.join(facts['vulnerabilities_discussed'])}")
            if facts.get("products_mentioned"):
                facts_text.append(f"提及的产品: {', '.join(facts['products_mentioned'])}")
            if facts.get("key_conclusions"):
                facts_text.append(f"关键结论: {'; '.join(facts['key_conclusions'])}")
            if facts_text:
                parts.append(f"[关键信息]\n" + "\n".join(facts_text))

        preferences = self.get_user_preferences(session_id, user_id)
        if preferences:
            parts.append(f"[用户偏好]\n" + "; ".join(preferences))

        window_messages = recent_messages[-window_size * 2:] if len(recent_messages) > window_size * 2 else recent_messages
        if window_messages:
            history_lines = []
            for msg in window_messages:
                role = "用户" if msg["role"] == "user" else "助手"
                history_lines.append(f"{role}: {msg['content']}")
            parts.append(f"[近期对话]\n" + "\n".join(history_lines))

        return "\n\n".join(parts)

    async def update_memory(
        self,
        session_id: str,
        messages: list[dict],
        window_size: int = None,
        user_id: str = None,
    ):
        if not session_id:
            logger.debug("No session_id, skipping memory update")
            return

        if window_size is None:
            window_size = settings.MEMORY_WINDOW_SIZE

        if settings.MEMORY_SUMMARY_ENABLED and len(messages) >= 2:
            await self._update_summary(session_id, messages, window_size, user_id)

        if len(messages) >= 2:
            await self._extract_facts(session_id, messages, user_id)

    async def _update_summary(
        self,
        session_id: str,
        messages: list[dict],
        window_size: int,
        user_id: str = None,
    ):
        existing_summary = self.get_summary(session_id, user_id)

        new_messages_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
            for m in messages
        )

        try:
            logger.info(f"Updating summary for session {session_id[:8]}..., messages={len(messages)}")
            prompt_value = SUMMARY_PROMPT.invoke({
                "existing_summary": existing_summary or "(无)",
                "new_messages": new_messages_text,
            })
            response = await self._summary_llm.ainvoke(prompt_value)
            new_summary = response.content if hasattr(response, 'content') else str(response)
            
            if new_summary.strip().startswith("<think"):
                import re
                match = re.search(r'</think\s*>\s*(.*)', new_summary, re.DOTALL)
                if match:
                    new_summary = match.group(1).strip()
            
            self.save_summary(session_id, new_summary.strip(), user_id)
            logger.info(f"Successfully updated summary for user={str(user_id or session_id)[:8]}...")
        except Exception as e:
            logger.error(f"Failed to update summary: {e}", exc_info=True)

    async def _extract_facts(self, session_id: str, messages: list[dict], user_id: str = None):
        recent_messages = messages[-4:] if len(messages) >= 4 else messages
        messages_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
            for m in recent_messages
        )

        try:
            prompt_value = EXTRACT_FACTS_PROMPT.invoke({"messages": messages_text})
            response = await self._summary_llm.ainvoke(prompt_value)
            content = response.content if hasattr(response, 'content') else str(response)
            
            import json
            import re
            
            if "<think" in content:
                match = re.search(r'</think\s*>\s*(.*)', content, re.DOTALL)
                if match:
                    content = match.group(1).strip()
            
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                facts = json.loads(json_match.group())
                existing_facts = self.get_facts(session_id, user_id)
                
                merged = self._merge_facts(existing_facts, facts)
                self.save_facts(session_id, merged, user_id)
                logger.info(f"Extracted facts for user={str(user_id or session_id)[:8]}...")
        except Exception as e:
            logger.debug(f"Fact extraction skipped: {e}")

    def _merge_facts(self, existing: dict, new: dict) -> dict:
        result = dict(existing)
        
        if "user_name" in new and new["user_name"]:
            result["user_name"] = new["user_name"]
        
        for key in ["user_preferences", "vulnerabilities_discussed", "products_mentioned", "key_conclusions"]:
            if key in new:
                existing_list = result.get(key, [])
                new_list = new[key] if isinstance(new[key], list) else [new[key]]
                merged = list(set(existing_list + new_list))
                result[key] = merged[:20]
        
        return result


memory_service = MemoryService()
