import os
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from tavily import TavilyClient

from app.config import llm

load_dotenv()

tavily_api_key = os.getenv("TAVILY_API_KEY")
if not tavily_api_key:
  raise ValueError("TAVILY_API_KEY is not set in your .env file.")

tavily_client = TavilyClient(api_key=tavily_api_key)


def get_web_results(user_question: str, max_results: int = 5):
  """Constructs targeted search queries to retrieve active, official BIS standards, QCOs, amendments, and detailed technical parameters."""
  # Append technical keywords if user explicitly asks for detailed engineering specs
  detail_keywords = ""
  lowered = user_question.lower()
  if any(
      k in lowered
      for k in [
          "detail",
          "specification",
          "thickness",
          "limit",
          "parameter",
          "test",
          "material",
          "requirement",
          "grade",
      ]
  ):
    detail_keywords = "material grades testing parameters requirements limits"

  search_query = (
      f"Bureau of Indian Standards BIS active latest revision amended IS"
      f" standard QCO {user_question} {detail_keywords}"
  ).strip()

  try:
    response = tavily_client.search(
        query=search_query,
        search_depth="advanced",
        max_results=max_results,
        include_domains=[
            "bis.gov.in",
            "standards.bis.gov.in",
            "manakonline.in",
            "crsbis.in",
            "pib.gov.in",
            "egazette.gov.in",
            "corpbiz.io",
            "alephindia.in",
        ],
    )
  except Exception as e:
    print(f"Tavily search error: {e}")
    return [], search_query

  results = response.get("results", [])
  cleaned_results = []

  for result in results:
    title = result.get("title", "").strip()
    url = result.get("url", "").strip()
    content = result.get("content", "").strip()

    if content:
      cleaned_results.append({"title": title, "url": url, "content": content})

  return cleaned_results, search_query


def format_web_context(results: list) -> str:
  if not results:
    return "No relevant information was retrieved from official BIS web sources."

  context_parts = []
  for i, result in enumerate(results, start=1):
    context_parts.append(
        f"SOURCE {i} ({result['title']}):\n"
        f"URL: {result['url']}\n"
        f"Content: {result['content']}\n"
    )

  return "\n".join(context_parts)


def format_chat_history(chat_history_list: list) -> str:
  """Converts Pydantic objects or dicts from chat_history into a clean string block.

  Takes the last 4 messages to preserve context without bloating the prompt.
  """
  if not chat_history_list:
    return "No prior conversation history."

  formatted = []
  for msg in chat_history_list:
    role = getattr(msg, "role", None) or (
        msg.get("role") if isinstance(msg, dict) else "User"
    )
    content = getattr(msg, "content", None) or (
        msg.get("content") if isinstance(msg, dict) else ""
    )
    role_label = "User" if str(role).lower() == "user" else "Assistant"
    formatted.append(f"{role_label}: {content}")

  return "\n".join(formatted[-4:])


# --- DYNAMIC & ADAPTIVE CONVERSATIONAL PROMPT TEMPLATE ---
prompt = PromptTemplate(
    template="""
You are "BIS Sahayak", an authentic, direct, and helpful AI consultant for the Bureau of Indian Standards (BIS).
Your goal is to guide manufacturers through a natural, step-by-step dialogue without sounding repetitive or robotic.

CRITICAL DIALOGUE RULES:
1. DYNAMIC OPENINGS (NO FIXED PREFIXES): NEVER start responses with fixed template phrases like "Don't worry", "That's a great product idea", "That's straightforward", or "According to...". Jump directly into the answer naturally and vary your phrasing every time.
2. ADAPTIVE DETAIL LEVEL:
   - For general/broad questions ("What standard applies to X?", "What is the IS code for Y?"): Keep answers concise (2-3 sentences max) to prevent info-dumping.
   - For explicit detail requests ("Tell me in detail", "What are the exact specifications/limits/thickness?", "What are the testing parameters?"): Extract and list all exact numeric specs, testing values, material grades, and parameters found in the WEB EVIDENCE.
3. ADAPTIVE TONE:
   - For factual queries: Answer directly with codes, specs, and metrics.
   - For complex/anxious concerns: Offer brief, grounded reassurance before answering.
4. GUIDING FOLLOW-UP QUESTION: End with a single, relevant follow-up question to keep the conversation moving forward (e.g., asking about production scale, factory location, or specific standard variant).
5. MATCH LANGUAGE: Match the user's language (English -> English, Devanagari Hindi -> Devanagari Hindi, Hinglish -> Hinglish).

PREVIOUS CHAT HISTORY:
{chat_history}

WEB EVIDENCE:
{context}

USER QUESTION:
{question}

ANSWER:
""",
    input_variables=["chat_history", "context", "question"],
)


def is_simple_greeting(question: str) -> bool:
  greetings = [
      "hi",
      "hello",
      "hey",
      "namaste",
      "good morning",
      "good evening",
      "haa",
      "haan",
  ]
  return question.strip().lower() in greetings


def ask_question(user_question: str, chat_history_list=None):
  if chat_history_list is None:
    chat_history_list = []

  if is_simple_greeting(user_question):
    greeting_reply = (
        "Namaste! I'm your BIS Sahayak assistant. What product or"
        " certification are you working on today? I'd love to help you get"
        " started!"
    )
    return greeting_reply, []

  results, search_query = get_web_results(user_question)
  web_context = format_web_context(results)
  formatted_history = format_chat_history(chat_history_list)

  final_prompt = prompt.invoke({
      "chat_history": formatted_history,
      "context": web_context,
      "question": user_question,
  })

  response = llm.invoke(final_prompt)
  answer = (
      response.content.strip()
      if hasattr(response, "content")
      else str(response).strip()
  )

  sources = []
  for result in results:
    url = result.get("url")
    if url and url not in sources:
      sources.append(url)

  return answer, sources